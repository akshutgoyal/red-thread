from __future__ import annotations

import hashlib
from io import BytesIO

import pytest
from botocore.exceptions import ClientError

from app.config import Settings
from app.services import storage_service


class FakeBody:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.position = 0
        self.closed = False

    def read(self, size: int) -> bytes:
        chunk = self.data[self.position : self.position + size]
        self.position += len(chunk)
        return chunk

    def close(self) -> None:
        self.closed = True


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def upload_fileobj(self, fileobj, _bucket, key, ExtraArgs=None) -> None:  # noqa: N803
        self.objects[key] = fileobj.read()

    def put_object(self, Bucket, Key, Body, ContentType=None) -> None:  # noqa: N803
        self.objects[Key] = Body

    def get_object(self, Bucket, Key):  # noqa: N803
        if Key not in self.objects:
            raise self._missing("GetObject")
        return {"Body": FakeBody(self.objects[Key])}

    def download_fileobj(self, Bucket, Key, fileobj) -> None:  # noqa: N803
        if Key not in self.objects:
            raise self._missing("GetObject")
        fileobj.write(self.objects[Key])

    def delete_object(self, Bucket, Key) -> None:  # noqa: N803
        self.objects.pop(Key, None)

    def head_object(self, Bucket, Key):  # noqa: N803
        if Key not in self.objects:
            raise self._missing("HeadObject")
        return {"ContentLength": len(self.objects[Key])}

    @staticmethod
    def _missing(operation: str) -> ClientError:
        return ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}},
            operation,
        )


def test_local_storage_round_trip(tmp_path, monkeypatch):
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        reports_dir=tmp_path / "reports",
        storage_backend="local",
    )
    monkeypatch.setattr(storage_service, "get_settings", lambda: settings)

    key = storage_service.evidence_key("case-1", "file.txt")
    size, digest = storage_service.save_stream(
        key,
        BytesIO(b"hello world"),
        max_bytes=100,
        content_type="text/plain",
    )
    assert size == 11
    assert digest == hashlib.sha256(b"hello world").hexdigest()
    assert (tmp_path / "data" / key).read_bytes() == b"hello world"
    assert storage_service.exists(key)
    assert storage_service.read_prefix(key, 5) == b"hello"

    with storage_service.materialize(key) as path:
        assert path.read_bytes() == b"hello world"

    storage_service.delete(key)
    assert not storage_service.exists(key)


def test_local_storage_rejects_path_traversal(tmp_path, monkeypatch):
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        reports_dir=tmp_path / "reports",
        storage_backend="local",
    )
    monkeypatch.setattr(storage_service, "get_settings", lambda: settings)

    with pytest.raises(ValueError):
        storage_service.save_bytes("../escape.txt", b"x", content_type="text/plain")
    with pytest.raises(ValueError):
        storage_service.read_prefix("/etc/passwd", 10)


def test_r2_storage_round_trip(monkeypatch):
    settings = Settings(
        _env_file=None,
        storage_backend="r2",
        r2_account_id="account",
        r2_access_key_id="key",
        r2_secret_access_key="secret",
        r2_bucket="bucket",
    )
    fake = FakeS3()
    monkeypatch.setattr(storage_service, "get_settings", lambda: settings)
    monkeypatch.setattr(storage_service, "_s3_client", lambda: fake)

    key = storage_service.evidence_key("case-1", "file.txt")
    size, digest = storage_service.save_stream(
        key,
        BytesIO(b"r2 payload"),
        max_bytes=100,
        content_type="text/plain",
    )
    assert size == 10
    assert digest == hashlib.sha256(b"r2 payload").hexdigest()
    assert fake.objects[key] == b"r2 payload"
    assert storage_service.exists(key)
    assert b"".join(storage_service.iter_object(key)) == b"r2 payload"
    assert storage_service.read_prefix(key, 2) == b"r2"

    with storage_service.materialize(key) as path:
        assert path.read_bytes() == b"r2 payload"
        materialized = path
    assert not materialized.exists()

    report_key = storage_service.report_key("case-1", "report.json")
    storage_service.save_bytes(report_key, b"{}", content_type="application/json")
    assert fake.objects[report_key] == b"{}"

    storage_service.delete(key)
    assert not storage_service.exists(key)
    assert not storage_service.exists("evidence/case-1/missing.txt")
