"""MinIO 对象存储 — 上传/下载/列举."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from apps.config import get_settings


def _client():
    from minio import Minio

    s = get_settings()
    host = s.minio_endpoint.replace("http://", "").replace("https://", "")
    secure = s.minio_endpoint.startswith("https")
    return Minio(host, access_key=s.minio_access_key, secret_key=s.minio_secret_key, secure=secure)


def ensure_bucket() -> None:
    c = _client()
    s = get_settings()
    if not c.bucket_exists(s.minio_bucket):
        c.make_bucket(s.minio_bucket)


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> dict[str, Any]:
    ensure_bucket()
    c = _client()
    bucket = get_settings().minio_bucket
    c.put_object(bucket, key, BytesIO(data), length=len(data), content_type=content_type)
    return {"bucket": bucket, "key": key, "size": len(data)}


def download_bytes(key: str) -> bytes:
    c = _client()
    bucket = get_settings().minio_bucket
    resp = c.get_object(bucket, key)
    try:
        return resp.read()
    finally:
        resp.close()
        resp.release_conn()


def list_objects(prefix: str = "", limit: int = 100) -> list[str]:
    c = _client()
    bucket = get_settings().minio_bucket
    if not c.bucket_exists(bucket):
        return []
    return [obj.object_name for obj in c.list_objects(bucket, prefix=prefix, recursive=True)][:limit]
