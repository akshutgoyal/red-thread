from __future__ import annotations

from datetime import datetime, timezone

from app.models import Event
from app.services import correlation_service, entity_service, reconciliation_service


def _upload(client, case_id, filename, content):
    response = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": (filename, content, "text/plain")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _event(db, case, evidence, event_type, timestamp, attributes, locator):
    event = Event(
        case_id=case["id"],
        evidence_id=evidence["id"],
        event_type=event_type,
        timestamp_raw=timestamp,
        timestamp_normalized=datetime.fromisoformat(timestamp.replace("Z", "+00:00")),
        timestamp_confidence="exact",
        timestamp_timezone="UTC",
        source_filename=evidence["original_filename"],
        source_locator=locator,
        source_snippet=str(attributes),
        attributes_json=attributes,
        warnings_json=[],
        parser_name="test_fixture",
        parser_version="1.0.0",
    )
    db.add(event)
    db.flush()
    return event


def _link(db, case_id, event, entity_type, value, role):
    entity = entity_service.get_or_create_entity(db, case_id, entity_type, value, role=role)
    entity_service.link_event_entity(db, event, entity, role=role, raw_value=value)


def test_graph_contains_exact_matches_and_optional_temporal_leads(client, case, db):
    phone = "+91-98765-43210"
    call = _upload(client, case["id"], "call_log.csv", b"caller,receiver\n")
    chat = _upload(client, case["id"], "chat_export.txt", b"sender,message\n")

    call_event = _event(
        db,
        case,
        call,
        "call",
        "2026-10-15T10:15:00Z",
        {"caller": phone, "receiver": "+91-91234-56789"},
        "row:4",
    )
    _link(db, case["id"], call_event, "phone", phone, "caller")
    chat_event = _event(
        db,
        case,
        chat,
        "chat_message",
        "2026-10-15T10:18:30Z",
        {"sender": phone, "message": "Pay now"},
        "line:12",
    )
    _link(db, case["id"], chat_event, "phone", phone, "sender")
    db.commit()

    reconciliation_service.run(db, case["id"])
    db.commit()

    graph = correlation_service.build_graph(db, case["id"], include_temporal=False)
    node_ids = {node.id for node in graph.nodes}
    assert f"evidence:{call['id']}" in node_ids
    assert f"evidence:{chat['id']}" in node_ids
    assert f"event:{call_event.id}" in node_ids
    assert f"event:{chat_event.id}" in node_ids

    edge_types = {edge.edge_type for edge in graph.edges}
    assert "evidence_contains_event" in edge_types
    assert "exact_identifier_match" in edge_types
    assert "temporal_proximity" not in edge_types

    temporal_graph = correlation_service.build_graph(
        db, case["id"], include_temporal=True, temporal_window_seconds=600
    )
    temporal_edges = [
        edge for edge in temporal_graph.edges if edge.edge_type == "temporal_proximity"
    ]
    assert temporal_edges
    assert all(edge.match_method == "heuristic" for edge in temporal_edges)
    assert all(edge.confidence == "low" for edge in temporal_edges)
