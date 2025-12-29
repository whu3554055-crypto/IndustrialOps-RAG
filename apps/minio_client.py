"""MinIO/S3 健康检查与对象列举（架构保留）."""

from __future__ import annotations

import urllib.error
import urllib.request

from apps.config import get_settings


def minio_health() -> dict:
    s = get_settings()
    url = f"http://{s.minio_endpoint}/minio/health/live"
    try:
        with urllib.request.urlopen(url, timeout=3.0) as resp:
            ok = resp.status == 200
            return {"ok": ok, "endpoint": s.minio_endpoint, "bucket": s.minio_bucket}
    except urllib.error.URLError as exc:
        return {"ok": False, "endpoint": s.minio_endpoint, "error": str(exc)}
