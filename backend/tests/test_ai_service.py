from __future__ import annotations

import json

import httpx
import pytest
from fastapi import HTTPException

from app.config import Settings
from app.models import (
    AiQuery,
    AuditEvent,
    Case,
    Event,
    Evidence,
    Finding,
    FindingEvidence,
)
from app.services import ai_service


def settings_for(**overrides) -> Settings:
    base = {
        "_env_file": None,
        "ai_provider": "none",
        "ai_max_retries": 0,
        "ai_redact_pii": False,
    }
    base.update(overrides)
    return Settings(**base)


def transport_for(handler):
    return httpx.MockTransport(handler)


def chat_response(content: str, usage: dict | None = None) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": content}}],
            "usage": usage or {"prompt_tokens": 10, "completion_tokens": 20},
        },
    )


def create_case_graph(db):
    case = Case(title="AI test case", description="Synthetic")
    db.add(case)
    db.flush()
    evidence = Evidence(
        case_id=case.id,
        original_filename="auth.log",
        stored_filename="auth.log",
        relative_path="evidence/auth.log",
        media_type="text/plain",
        size_bytes=10,
        sha256="a" * 64,
        processing_status="parsed",
        parser_name="auth_log",
    )
    db.add(evidence)
    db.flush()
    event = Event(
        case_id=case.id,
        evidence_id=evidence.id,
        event_type="auth.login",
        timestamp_raw="Oct 15 10:00:01",
        timestamp_confidence="inferred_year",
        source_filename="auth.log",
        source_locator="line:1",
        source_snippet="Failed password for root from 203.0.113.45",
        attributes_json={"username": "root", "source_ip": "203.0.113.45"},
        warnings_json=[],
        parser_name="auth_log",
        parser_version="2.0.0",
    )
    db.add(event)
    db.flush()
    finding = Finding(
        case_id=case.id,
        severity="medium",
        category="authentication",
        title="Authentication indicator",
        explanation="Failed logins were observed.",
        detection_method="deterministic_rule",
        confidence="medium",
        status="open",
        limitations="Threshold-based indicator.",
        alternative_explanations="User error or authorized testing.",
    )
    db.add(finding)
    db.commit()
    return case, evidence, event, finding


def test_resolve_provider_auto_prefers_commandcode():
    settings = settings_for(
        ai_provider="auto",
        COMMANDCODE_API_KEY="cc-key",
        TOKENHARBOR_API_KEY="th-key",
    )
    status = ai_service.resolve_provider(settings)
    assert status.configured is True
    assert status.provider == "commandcode"
    assert status.model == "deepseek/deepseek-v4.1-flash"
    assert status.api_key == "cc-key"


def test_resolve_provider_falls_back_to_tokenharbor():
    settings = settings_for(
        ai_provider="auto",
        COMMANDCODE_API_KEY="",
        TOKENHARBOR_API_KEY="th-key",
    )
    status = ai_service.resolve_provider(settings)
    assert status.configured is True
    assert status.provider == "tokenharbor"
    assert status.model == "deepseek-v4.1-flash:free"


def test_resolve_provider_without_keys_is_disabled():
    settings = settings_for(ai_provider="auto", COMMANDCODE_API_KEY="", TOKENHARBOR_API_KEY="")
    status = ai_service.resolve_provider(settings)
    assert status.configured is False
    assert status.provider == "none"


def test_provider_success_and_headers():
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization", "")
        captured["zdr"] = request.headers.get("x-cmd-zdr", "")
        body = json.loads(request.content)
        captured["model"] = body["model"]
        captured["max_tokens"] = body["max_tokens"]
        return chat_response("grounded answer", {"prompt_tokens": 5, "completion_tokens": 7})

    provider = ai_service.OpenAICompatibleProvider(
        name="commandcode",
        base_url="https://api.commandcode.ai/provider/v1",
        model="deepseek/deepseek-v4.1-flash",
        api_key="secret",
        timeout_seconds=5,
        max_retries=0,
        max_tokens=2048,
        zdr=True,
        transport=transport_for(handler),
    )

    result = __import__("asyncio").run(provider.complete("system", "user"))
    assert result.content == "grounded answer"
    assert result.provider == "commandcode"
    assert captured["authorization"] == "Bearer secret"
    assert captured["zdr"] == "1"
    assert captured["model"] == "deepseek/deepseek-v4.1-flash"
    assert captured["max_tokens"] == 2048
    assert result.usage["prompt_tokens"] == 5


def test_provider_length_truncation_is_reported():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "reasoning_content": "Long reasoning that consumed the budget.",
                        },
                        "finish_reason": "length",
                    }
                ],
                "usage": {"completion_tokens": 8192},
            },
        )

    provider = ai_service.OpenAICompatibleProvider(
        name="tokenharbor",
        base_url="https://tokenharbor.ai/v1",
        model="deepseek-v4.1-flash:free",
        api_key="key",
        timeout_seconds=5,
        max_retries=0,
        max_tokens=8192,
        transport=transport_for(handler),
    )
    with pytest.raises(ai_service.AIError) as error:
        __import__("asyncio").run(provider.complete("system", "user"))
    assert error.value.code == "truncated_response"
    assert "RED_THREAD_AI_MAX_TOKENS" in error.value.message


def test_provider_reasoning_only_is_reported():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "reasoning_content": "Reasoning without a final answer.",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"completion_tokens": 100},
            },
        )

    provider = ai_service.OpenAICompatibleProvider(
        name="tokenharbor",
        base_url="https://tokenharbor.ai/v1",
        model="deepseek-v4.1-flash:free",
        api_key="key",
        timeout_seconds=5,
        max_retries=0,
        max_tokens=8192,
        transport=transport_for(handler),
    )
    with pytest.raises(ai_service.AIError) as error:
        __import__("asyncio").run(provider.complete("system", "user"))
    assert error.value.code == "reasoning_only"


def test_provider_invalid_credentials():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "bad key"})

    provider = ai_service.OpenAICompatibleProvider(
        name="tokenharbor",
        base_url="https://tokenharbor.ai/v1",
        model="deepseek-v4.1-flash:free",
        api_key="bad",
        timeout_seconds=5,
        max_retries=0,
        transport=transport_for(handler),
    )
    with pytest.raises(ai_service.AIError) as error:
        __import__("asyncio").run(provider.complete("system", "user"))
    assert error.value.code == "invalid_credentials"
    assert error.value.status_code == 401


def test_provider_rate_limited():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "0"})

    provider = ai_service.OpenAICompatibleProvider(
        name="commandcode",
        base_url="https://api.commandcode.ai/provider/v1",
        model="deepseek/deepseek-v4.1-flash",
        api_key="key",
        timeout_seconds=5,
        max_retries=0,
        transport=transport_for(handler),
    )
    with pytest.raises(ai_service.AIError) as error:
        __import__("asyncio").run(provider.complete("system", "user"))
    assert error.value.code == "rate_limited"
    assert error.value.status_code == 429


def test_provider_retries_transient_rate_limit():
    calls = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return chat_response("ok after retry")

    provider = ai_service.OpenAICompatibleProvider(
        name="commandcode",
        base_url="https://api.commandcode.ai/provider/v1",
        model="deepseek/deepseek-v4.1-flash",
        api_key="key",
        timeout_seconds=5,
        max_retries=1,
        transport=transport_for(handler),
    )
    result = __import__("asyncio").run(provider.complete("system", "user"))
    assert result.content == "ok after retry"
    assert calls["count"] == 2


def test_provider_timeout():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=_request)

    provider = ai_service.OpenAICompatibleProvider(
        name="commandcode",
        base_url="https://api.commandcode.ai/provider/v1",
        model="deepseek/deepseek-v4.1-flash",
        api_key="key",
        timeout_seconds=5,
        max_retries=0,
        transport=transport_for(handler),
    )
    with pytest.raises(ai_service.AIError) as error:
        __import__("asyncio").run(provider.complete("system", "user"))
    assert error.value.code == "timeout"
    assert error.value.status_code == 504


def test_provider_malformed_json():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    provider = ai_service.OpenAICompatibleProvider(
        name="commandcode",
        base_url="https://api.commandcode.ai/provider/v1",
        model="deepseek/deepseek-v4.1-flash",
        api_key="key",
        timeout_seconds=5,
        max_retries=0,
        transport=transport_for(handler),
    )
    with pytest.raises(ai_service.AIError) as error:
        __import__("asyncio").run(provider.complete("system", "user"))
    assert error.value.code == "malformed_response"


def test_provider_empty_choices():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    provider = ai_service.OpenAICompatibleProvider(
        name="commandcode",
        base_url="https://api.commandcode.ai/provider/v1",
        model="deepseek/deepseek-v4.1-flash",
        api_key="key",
        timeout_seconds=5,
        max_retries=0,
        transport=transport_for(handler),
    )
    with pytest.raises(ai_service.AIError) as error:
        __import__("asyncio").run(provider.complete("system", "user"))
    assert error.value.code == "empty_response"


def test_citation_validation(db):
    case, evidence, event, finding = create_case_graph(db)
    context_ids = {
        "evidence": {evidence.id},
        "event": {event.id},
        "finding": {finding.id},
    }
    context_maps = {
        "event_locator": {event.id: event.source_locator},
        "evidence_locators": {evidence.id: {event.source_locator}},
    }
    citations = ai_service._validate_citations(
        db,
        case.id,
        [
            {"kind": "event", "id": event.id, "source_locator": "line:1"},
            {"kind": "event", "id": event.id, "source_locator": "line:99"},
            {"kind": "evidence", "id": evidence.id, "source_locator": "line:1"},
            {"kind": "finding", "id": finding.id},
            {"kind": "event", "id": "missing"},
        ],
        context_ids,
        context_maps,
    )
    assert len(citations) == 5
    assert citations[0]["verified"] is True
    assert citations[1]["verified"] is False
    assert citations[2]["verified"] is True
    assert citations[3]["verified"] is True
    assert citations[4]["verified"] is False
    assert citations[4]["warning"]


def test_extract_locators_handles_combined_and_plural_forms():
    assert ai_service._extract_locators(
        "chat_export.txt:line:15; upi_transaction_log.csv:row:19"
    ) == ["line:15", "row:19"]
    assert ai_service._extract_locators("chat_export.txt:lines 1,2,11") == [
        "line:1",
        "line:2",
        "line:11",
    ]
    assert ai_service._extract_locators(
        "payment_screenshot.png:bbox:58, 55, 554, 32"
    ) == ["bbox:58,55,554,32"]
    assert ai_service._extract_locators("descriptive only") == []


def test_citations_with_combined_and_plural_locators_are_verified(db):
    case, evidence, event, finding = create_case_graph(db)
    db.add(
        FindingEvidence(
            finding_id=finding.id,
            evidence_id=evidence.id,
            event_id=event.id,
            role="supporting_event",
            source_locator="line:1",
        )
    )
    db.flush()
    context_ids = {
        "evidence": {evidence.id},
        "event": {event.id},
        "finding": {finding.id},
    }
    context_maps = {
        "event_locator": {event.id: "line:1"},
        "evidence_locators": {evidence.id: {"line:1", "line:2"}},
        "finding_locators": {finding.id: {"line:1"}},
    }
    citations = ai_service._validate_citations(
        db,
        case.id,
        [
            {"kind": "finding", "id": finding.id, "source_locator": "auth.log:line:1"},
            {"kind": "finding", "id": finding.id, "source_locator": "auth.log:line:99"},
            {"kind": "finding", "id": finding.id, "source_locator": "descriptive only"},
            {"kind": "evidence", "id": evidence.id, "source_locator": "auth.log:lines 1,2"},
            {"kind": "event", "id": event.id, "source_locator": "auth.log:line:1 (description)"},
        ],
        context_ids,
        context_maps,
    )
    assert len(citations) == 5
    assert citations[0]["verified"] is True
    assert citations[1]["verified"] is False
    assert citations[1]["warning"]
    assert citations[2]["verified"] is True
    assert citations[2]["warning"]
    assert citations[3]["verified"] is True
    assert citations[4]["verified"] is True


def test_ask_ai_without_provider_returns_503(db):
    case, _, _, _ = create_case_graph(db)
    settings = settings_for(ai_provider="none")
    with pytest.raises(HTTPException) as error:
        __import__("asyncio").run(
            ai_service.ask_ai(db, case.id, "What happened?", settings)
        )
    assert error.value.status_code == 503


def test_ask_ai_end_to_end_with_valid_and_invalid_citations(db):
    case, evidence, event, finding = create_case_graph(db)
    content = json.dumps(
        {
            "answer": "The authentication log shows failed logins.",
            "citations": [
                {"kind": "event", "id": event.id, "source_locator": event.source_locator},
                {"kind": "evidence", "id": evidence.id, "source_locator": event.source_locator},
                {"kind": "finding", "id": finding.id},
                {"kind": "event", "id": "invented-id"},
            ],
            "uncertainties": ["The year is inferred."],
            "alternative_explanations": ["Authorized testing."],
            "suggested_next_steps": ["Confirm the host owner."],
            "insufficient_evidence": False,
        }
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return chat_response(content, {"prompt_tokens": 100, "completion_tokens": 50})

    settings = settings_for(
        ai_provider="commandcode",
        COMMANDCODE_API_KEY="test-key",
    )
    result = __import__("asyncio").run(
        ai_service.ask_ai(
            db,
            case.id,
            "What happened in the authentication log?",
            settings,
            transport=transport_for(handler),
        )
    )

    assert result["ai_generated"] is True
    assert result["provider"] == "commandcode"
    assert result["citations"][0]["verified"] is True
    assert result["citations"][1]["verified"] is True
    assert result["citations"][2]["verified"] is True
    assert result["citations"][3]["verified"] is False
    assert result["uncertainties"] == ["The year is inferred."]
    assert db.query(AiQuery).count() == 1
    assert db.query(AuditEvent).filter(AuditEvent.action == "ai.query").count() == 1


def test_ask_ai_unstructured_response_is_not_fabricated(db):
    case, _, _, _ = create_case_graph(db)

    def handler(_request: httpx.Request) -> httpx.Response:
        return chat_response("This is not JSON.")

    settings = settings_for(ai_provider="commandcode", COMMANDCODE_API_KEY="test-key")
    result = __import__("asyncio").run(
        ai_service.ask_ai(
            db,
            case.id,
            "Summarize the evidence.",
            settings,
            transport=transport_for(handler),
        )
    )
    assert result["citations"] == []
    assert "non-JSON" in result["uncertainties"][0]
    record = db.query(AiQuery).order_by(AiQuery.created_at.desc()).first()
    assert record is not None
    assert record.validation_status == "unstructured"


def test_ask_ai_insufficient_evidence(db):
    case, _, _, _ = create_case_graph(db)
    content = json.dumps(
        {
            "answer": "The evidence is insufficient to answer this question.",
            "citations": [],
            "uncertainties": ["No transaction records are present."],
            "alternative_explanations": [],
            "suggested_next_steps": ["Upload transaction evidence."],
            "insufficient_evidence": True,
        }
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return chat_response(content)

    settings = settings_for(ai_provider="commandcode", COMMANDCODE_API_KEY="test-key")
    result = __import__("asyncio").run(
        ai_service.ask_ai(
            db,
            case.id,
            "Which transaction is fraudulent?",
            settings,
            transport=transport_for(handler),
        )
    )
    assert result["insufficient_evidence"] is True
    assert result["citations"] == []


def test_status_check_reports_live_result():
    def handler(_request: httpx.Request) -> httpx.Response:
        return chat_response("OK")

    settings = settings_for(ai_provider="commandcode", COMMANDCODE_API_KEY="test-key")
    status = __import__("asyncio").run(
        ai_service.get_status(
            settings,
            check=True,
            transport=transport_for(handler),
        )
    )
    assert status["configured"] is True
    assert status["live_check"]["ok"] is True
    assert status["live_check"]["provider"] == "commandcode"


def test_model_label_maps_deepseek_flash():
    from app.services.ai_service import model_label

    assert model_label("deepseek-v4.1-flash:free") == "DeepSeek V4.1 Flash"
    assert model_label("deepseek/deepseek-v4.1-flash") == "DeepSeek V4.1 Flash"
    assert model_label("another-model") == "another-model"
