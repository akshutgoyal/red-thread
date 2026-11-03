from __future__ import annotations

import hashlib
import mimetypes
import os
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import BinaryIO
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from ..config import get_settings

CHUNK_SIZE = 1024 * 1024
SPOOL_MAX_BYTES = 8 * 1024 * 1024


class StorageError(Exception):
    pass


class StorageLimitExceeded(StorageError):
    pass


class StorageEmptyFile(StorageError):
    pass


class StorageObjectNotFound(StorageError):
    pass


def evidence_key(case_id: str, stored_filename: str) -> str:
    return _validate_key(f"evidence/{case_id}/{stored_filename}")


def report_key(case_id: str, filename: str) -> str:
    return _validate_key(f"reports/{case_id}/{filename}")


def _validate_key(key: str) -> str:
    if not key or "\\" in key:
        raise ValueError("Invalid storage key.")
    path = PurePosixPath(key)
    if path.is_absolute():
        raise ValueError("Invalid storage key.")
    parts = path.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Invalid storage key.")
    return "/".join(parts)


def _local_path(key: str) -> Path:
    settings = get_settings()
    if key.startswith("reports/"):
        root = settings.resolved_reports_dir
        relative = key.removeprefix("reports/")
    elif key.startswith("evidence/"):
        root = settings.resolved_data_dir
        relative = key
    else:
        root = settings.resolved_reports_dir
        relative = key
    path = (root / relative).resolve()
    if path != root and root not in path.parents:
        raise StorageError("Storage key resolves outside its storage root.")
    return path


def _is_missing(error: ClientError) -> bool:
    code = str(error.response.get("Error", {}).get("Code", ""))
    status_code = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return code in {"404", "NoSuchKey", "NotFound"} or status_code == 404


@lru_cache(maxsize=1)
def _s3_client():
    settings = get_settings()
    if not settings.resolved_r2_endpoint or not settings.r2_bucket:
        raise StorageError("R2 storage is not configured.")
    return boto3.client(
        "s3",
        endpoint_url=settings.resolved_r2_endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name=settings.r2_region or "auto",
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


def _r2_bucket() -> str:
    bucket = get_settings().r2_bucket
    if not bucket:
        raise StorageError("R2 bucket is not configured.")
    return bucket


def save_stream(
    key: str,
    stream: BinaryIO,
    *,
    max_bytes: int,
    content_type: str | None = None,
) -> tuple[int, str]:
    key = _validate_key(key)
    digest = hashlib.sha256()
    size = 0
    with tempfile.SpooledTemporaryFile(max_size=SPOOL_MAX_BYTES) as buffer:
        while True:
            chunk = stream.read(CHUNK_SIZE)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                raise StorageLimitExceeded("File exceeds the upload limit.")
            digest.update(chunk)
            buffer.write(chunk)

        if size == 0:
            raise StorageEmptyFile("Empty files are not accepted.")

        buffer.seek(0)
        media_type = content_type or mimetypes.guess_type(key)[0] or "application/octet-stream"
        if get_settings().is_r2:
            try:
                _s3_client().upload_fileobj(
                    buffer,
                    _r2_bucket(),
                    key,
                    ExtraArgs={"ContentType": media_type},
                )
            except (BotoCoreError, ClientError) as error:
                raise StorageError(f"R2 upload failed: {error}") from error
        else:
            path = _local_path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
            try:
                with temp_path.open("wb") as output:
                    shutil.copyfileobj(buffer, output, length=CHUNK_SIZE)
                os.replace(temp_path, path)
            finally:
                temp_path.unlink(missing_ok=True)

    return size, digest.hexdigest()


def save_bytes(key: str, data: bytes, *, content_type: str) -> None:
    key = _validate_key(key)
    if get_settings().is_r2:
        try:
            _s3_client().put_object(
                Bucket=_r2_bucket(),
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        except (BotoCoreError, ClientError) as error:
            raise StorageError(f"R2 upload failed: {error}") from error
        return

    path = _local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temp_path.write_bytes(data)
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def iter_object(key: str) -> Iterator[bytes]:
    key = _validate_key(key)
    if get_settings().is_r2:
        try:
            response = _s3_client().get_object(Bucket=_r2_bucket(), Key=key)
        except ClientError as error:
            if _is_missing(error):
                raise StorageObjectNotFound(key) from error
            raise StorageError(f"R2 download failed: {error}") from error
        except BotoCoreError as error:
            raise StorageError(f"R2 download failed: {error}") from error

        body = response["Body"]

        def chunks() -> Iterator[bytes]:
            try:
                while True:
                    chunk = body.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk
            finally:
                body.close()

        return chunks()

    path = _local_path(key)
    try:
        handle = path.open("rb")
    except FileNotFoundError as error:
        raise StorageObjectNotFound(key) from error

    def local_chunks() -> Iterator[bytes]:
        with handle:
            while True:
                chunk = handle.read(CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk

    return local_chunks()


def read_prefix(key: str, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    iterator = iter_object(key)
    try:
        for chunk in iterator:
            remaining = max_bytes - total
            if remaining <= 0:
                break
            piece = chunk[:remaining]
            chunks.append(piece)
            total += len(piece)
            if total >= max_bytes:
                break
    finally:
        close = getattr(iterator, "close", None)
        if close is not None:
            close()
    return b"".join(chunks)


@contextmanager
def materialize(key: str) -> Iterator[Path]:
    key = _validate_key(key)
    if not get_settings().is_r2:
        path = _local_path(key)
        if not path.is_file():
            raise StorageObjectNotFound(key)
        yield path
        return

    suffix = Path(key).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
        temp_path = Path(handle.name)
    try:
        with temp_path.open("wb") as output:
            try:
                _s3_client().download_fileobj(_r2_bucket(), key, output)
            except ClientError as error:
                if _is_missing(error):
                    raise StorageObjectNotFound(key) from error
                raise StorageError(f"R2 download failed: {error}") from error
            except BotoCoreError as error:
                raise StorageError(f"R2 download failed: {error}") from error
        yield temp_path
    finally:
        temp_path.unlink(missing_ok=True)


def delete(key: str) -> None:
    key = _validate_key(key)
    if get_settings().is_r2:
        try:
            _s3_client().delete_object(Bucket=_r2_bucket(), Key=key)
        except (BotoCoreError, ClientError) as error:
            raise StorageError(f"R2 delete failed: {error}") from error
        return
    _local_path(key).unlink(missing_ok=True)


def exists(key: str) -> bool:
    key = _validate_key(key)
    if get_settings().is_r2:
        try:
            _s3_client().head_object(Bucket=_r2_bucket(), Key=key)
            return True
        except ClientError as error:
            if _is_missing(error):
                return False
            raise StorageError(f"R2 head failed: {error}") from error
        except BotoCoreError as error:
            raise StorageError(f"R2 head failed: {error}") from error
    return _local_path(key).is_file()


def content_type_for(key: str) -> str:
    return mimetypes.guess_type(key)[0] or "application/octet-stream"


def delete_prefix(prefix: str) -> int:
    if not get_settings().is_r2:
        raise StorageError("delete_prefix is only supported for R2 storage.")
    client = _s3_client()
    bucket = _r2_bucket()
    deleted = 0
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        keys = [{"Key": item["Key"]} for item in page.get("Contents", [])]
        if not keys:
            continue
        client.delete_objects(Bucket=bucket, Delete={"Objects": keys})
        deleted += len(keys)
    return deleted
