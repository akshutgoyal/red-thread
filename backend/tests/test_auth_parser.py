from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone

from app.parsers.auth_log_parser import (
    AuthParserConfig,
    LiveSecurityTracker,
    ParseWarning,
    detect_alerts,
    event_to_dict,
    export_csv,
    export_json,
    export_security_csv,
    parse_line,
    parse_text,
    parse_timestamp,
)


def test_import_has_no_side_effects():
    result = subprocess.run(
        [sys.executable, "-c", "import app.parsers.auth_log_parser; print('ok')"],
        cwd=".",
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_timestamp_inference_and_exact_iso():
    inferred = parse_timestamp(
        "Oct 15 10:00:00", AuthParserConfig(default_year=2026)
    )
    assert inferred.normalized == datetime(2026, 10, 15, 10, 0, tzinfo=timezone.utc)
    assert inferred.confidence == "inferred_year"
    assert inferred.year_inferred is True
    assert any("Year not present" in warning for warning in inferred.warnings)

    exact = parse_timestamp(
        "2026-10-15T10:00:00Z", AuthParserConfig(default_year=2026)
    )
    assert exact.normalized == datetime(2026, 10, 15, 10, 0, tzinfo=timezone.utc)
    assert exact.confidence == "exact"
    assert exact.year_inferred is False


def test_timestamp_reference_date_rollover():
    reference = datetime(2026, 1, 5, tzinfo=timezone.utc)
    result = parse_timestamp(
        "Dec 31 23:59:59",
        AuthParserConfig(reference_date=reference, timezone="UTC"),
    )
    assert result.normalized is not None
    assert result.normalized.year == 2025
    assert result.year_inferred is True


def test_timestamp_unknown_stays_unknown():
    result = parse_timestamp("not-a-timestamp", AuthParserConfig())
    assert result.normalized is None
    assert result.confidence == "unknown"


def test_ipv4_and_ipv6_are_canonicalized():
    config = AuthParserConfig(default_year=2026)
    v4 = parse_line(
        "Oct 15 10:00:00 srv sshd[1]: Failed password for alice from 203.0.113.45 port 22 ssh2",
        1,
        config,
    )
    assert v4.source_ip == "203.0.113.45"

    v6 = parse_line(
        "Oct 15 10:00:00 srv sshd[2]: Failed password for bob from 2001:0db8:0:0::1 port 22 ssh2",
        2,
        config,
    )
    assert v6.source_ip == "2001:db8::1"


def test_session_and_sudo_parsing():
    config = AuthParserConfig(default_year=2026)
    session = parse_line(
        "Oct 15 06:00:05 srv sshd[4112]: pam_unix(sshd:session): session opened for user admin by (uid=0)",
        1,
        config,
    )
    assert session.event_type == "auth.session"
    assert session.username == "admin"
    assert session.session_event == "opened"

    sudo = parse_line(
        "Oct 15 06:02:00 srv sudo: admin : TTY=pts/0 ; PWD=/home/admin ; USER=root ; COMMAND=/usr/bin/apt update",
        2,
        config,
    )
    assert sudo.event_type == "auth.sudo"
    assert sudo.sudo_target_user == "root"
    assert sudo.sudo_command == "/usr/bin/apt update"


def test_malformed_line_returns_warning():
    result = parse_line("this is not a log line", 7, AuthParserConfig())
    assert isinstance(result, ParseWarning)
    assert result.source_line_number == 7


def test_thresholds_and_batch_live_parity():
    config = AuthParserConfig(
        default_year=2026,
        burst_limit=8,
        burst_window_seconds=60,
        persistent_limit=10,
        persistent_window_seconds=900,
    )
    lines = [
        f"Oct 15 10:00:{second:02d} srv sshd[{1000 + second}]: Failed password for user{second} from 203.0.113.45 port {40000 + second} ssh2"
        for second in range(8)
    ]
    lines.append(
        "Oct 15 10:01:00 srv sshd[2000]: Failed password for root from 203.0.113.45 port 41000 ssh2"
    )
    lines.append(
        "Oct 15 10:02:00 srv sshd[2001]: Failed password for admin from 203.0.113.45 port 41001 ssh2"
    )
    lines.append(
        "Oct 15 10:03:00 srv sshd[2002]: Accepted password for root from 203.0.113.45 port 41002 ssh2"
    )
    result = parse_text("\n".join(lines), config)
    assert len(result.alerts) == 1
    batch_alert = result.alerts[0]
    assert "AUTH-BURST-001" in batch_alert.rule_ids
    assert "AUTH-PERSIST-002" in batch_alert.rule_ids
    assert "AUTH-MULTIUSER-003" in batch_alert.rule_ids
    assert "AUTH-SUCCESS-AFTER-FAIL-005" in batch_alert.rule_ids
    assert batch_alert.level == "HIGH SUSPICION"

    tracker = LiveSecurityTracker(config)
    live_alerts = [
        alert
        for alert in (tracker.process(event) for event in result.events)
        if alert is not None
    ]
    assert live_alerts
    final = live_alerts[-1]
    assert final.score == batch_alert.score
    assert set(final.rule_ids) == set(batch_alert.rule_ids)


def test_configurable_thresholds():
    config = AuthParserConfig(
        default_year=2026,
        burst_limit=3,
        burst_window_seconds=10,
        persistent_limit=99,
        many_users_limit=99,
        invalid_user_limit=99,
        enable_success_after_failure=False,
    )
    text = "\n".join(
        [
            "Oct 15 10:00:00 srv sshd[1]: Failed password for a from 198.51.100.9 port 1 ssh2",
            "Oct 15 10:00:05 srv sshd[2]: Failed password for b from 198.51.100.9 port 2 ssh2",
            "Oct 15 10:00:09 srv sshd[3]: Failed password for c from 198.51.100.9 port 3 ssh2",
        ]
    )
    result = parse_text(text, config)
    assert len(result.alerts) == 1
    assert result.alerts[0].rule_ids == ["AUTH-BURST-001"]


def test_no_alert_for_single_failure():
    config = AuthParserConfig(default_year=2026)
    result = parse_text(
        "Oct 15 10:00:00 srv sshd[1]: Failed password for alice from 198.51.100.9 port 1 ssh2",
        config,
    )
    assert result.alerts == []


def test_export_json_csv_and_security_csv(tmp_path):
    config = AuthParserConfig(default_year=2026)
    result = parse_text(
        "\n".join(
            [
                "Oct 15 10:00:00 srv sshd[1]: Failed password for alice from 198.51.100.9 port 1 ssh2",
                "Oct 15 10:00:05 srv sshd[2]: Failed password for bob from 198.51.100.9 port 2 ssh2",
                "Oct 15 10:00:09 srv sshd[3]: Failed password for carol from 198.51.100.9 port 3 ssh2",
            ]
        ),
        AuthParserConfig(
            default_year=2026,
            burst_limit=2,
            burst_window_seconds=10,
            persistent_limit=99,
            many_users_limit=99,
            invalid_user_limit=99,
            enable_success_after_failure=False,
        ),
    )
    json_path = tmp_path / "events.json"
    csv_path = tmp_path / "events.csv"
    security_path = tmp_path / "security.csv"
    export_json(json_path, result)
    export_csv(csv_path, result)
    export_security_csv(security_path, result)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["parser"]["name"] == "auth_log"
    assert len(payload["events"]) == 3
    assert csv_path.exists() and security_path.exists()
    assert "event_id" in csv_path.read_text(encoding="utf-8")
    assert "alert_id" in security_path.read_text(encoding="utf-8")


def test_event_to_dict_has_provenance():
    event = parse_line(
        "Oct 15 10:00:00 srv sshd[1]: Failed password for alice from 198.51.100.9 port 1 ssh2",
        4,
        AuthParserConfig(default_year=2026),
    )
    payload = event_to_dict(event)
    assert payload["source_line_number"] == 4
    assert payload["timestamp_confidence"] == "inferred_year"
    assert payload["ip"] == "198.51.100.9"
    assert payload["user"] == "alice"
