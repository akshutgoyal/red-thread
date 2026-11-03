from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

TEST_ROOT = Path(tempfile.mkdtemp(prefix="red-thread_test_"))
os.environ["RED_THREAD_DATA_DIR"] = str(TEST_ROOT / "data")
os.environ["RED_THREAD_REPORTS_DIR"] = str(TEST_ROOT / "reports")
os.environ["RED_THREAD_DATABASE_URL"] = f"sqlite:///{TEST_ROOT / 'test.db'}"
os.environ["RED_THREAD_AUTH_DEFAULT_YEAR"] = "2026"
os.environ["RED_THREAD_AUTH_DEFAULT_TIMEZONE"] = "UTC"
os.environ["RED_THREAD_ENABLE_LIVE_MONITOR"] = "false"
os.environ["RED_THREAD_STORAGE_BACKEND"] = "local"
os.environ["RED_THREAD_SEED_DEMO"] = "false"
os.environ["RED_THREAD_AI_PROVIDER"] = "none"
os.environ["RED_THREAD_AI_REDACT_PII"] = "false"
os.environ["COMMANDCODE_API_KEY"] = ""
os.environ["TOKENHARBOR_API_KEY"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def case(client):
    response = client.post(
        "/api/cases",
        json={
            "title": "Operation PhishTrace Test",
            "description": "Synthetic test case for Red Thread.",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


AUTH_LOG = """\
Oct 15 10:00:01 srv sshd[1001]: Failed password for invalid user alice from 203.0.113.45 port 40001 ssh2
Oct 15 10:00:06 srv sshd[1002]: Failed password for invalid user bob from 203.0.113.45 port 40002 ssh2
Oct 15 10:00:11 srv sshd[1003]: Failed password for invalid user carol from 203.0.113.45 port 40003 ssh2
Oct 15 10:00:16 srv sshd[1004]: Failed password for invalid user dave from 203.0.113.45 port 40004 ssh2
Oct 15 10:00:21 srv sshd[1005]: Failed password for invalid user erin from 203.0.113.45 port 40005 ssh2
Oct 15 10:00:26 srv sshd[1006]: Failed password for invalid user frank from 203.0.113.45 port 40006 ssh2
Oct 15 10:00:31 srv sshd[1007]: Failed password for invalid user grace from 203.0.113.45 port 40007 ssh2
Oct 15 10:00:36 srv sshd[1008]: Failed password for invalid user hank from 203.0.113.45 port 40008 ssh2
Oct 15 10:05:00 srv sshd[1009]: Failed password for root from 203.0.113.45 port 40009 ssh2
Oct 15 10:12:00 srv sshd[1010]: Failed password for admin from 203.0.113.45 port 40010 ssh2
Oct 15 10:13:00 srv sshd[1011]: Accepted password for root from 203.0.113.45 port 40100 ssh2
Oct 15 06:00:00 srv sshd[4112]: Accepted publickey for admin from 103.21.244.2 port 51244 ssh2: RSA SHA256:d8a
Oct 15 06:00:05 srv sshd[4112]: pam_unix(sshd:session): session opened for user admin by (uid=0)
Oct 15 06:02:00 srv sudo: admin : TTY=pts/0 ; PWD=/home/admin ; USER=root ; COMMAND=/usr/bin/apt update
Oct 15 06:03:00 srv sshd[4200]: Failed password for invalid user ipv6test from 2001:db8::1 port 50000 ssh2
Oct 15 06:04:00 srv CRON[9999]: (root) CMD (cmd)
Oct 15 06:05:00 srv sshd[4112]: pam_unix(sshd:session): session closed for user admin
"""


@pytest.fixture()
def auth_log_bytes() -> bytes:
    return AUTH_LOG.encode("utf-8")
