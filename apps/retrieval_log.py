"""检索日志 — file + 可选 PostgreSQL."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from apps.config import ROOT, get_settings, load_profile


def _cfg() -> dict:
    return load_profile().get("persistence", {})


def log_backend() -> str:
    return str(_cfg().get("retrieval_log_backend", "file")).lower()


def log_file_path() -> Path:
    raw = _cfg().get("retrieval_log_file", "reports/retrieval_logs.jsonl")
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


def write_retrieval_log(
    *,
    log_id: str,
    session_id: str,
    query: str,
    search_query: str,
    hits: list[dict[str, Any]],
    refused: bool,
) -> dict[str, Any]:
    top_source = hits[0].get("source_file", "") if hits else ""
    row = {
        "log_id": log_id,
        "session_id": session_id,
        "query": query,
        "search_query": search_query,
        "hit_count": len(hits),
        "top_source_file": top_source,
        "refused": refused,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if log_backend() == "postgresql":
        try:
            _write_postgres(row)
            row["stored"] = "postgresql"
            return row
        except Exception:
            pass
    _append_file(row)
    row["stored"] = "file"
    return row


def _append_file(row: dict[str, Any]) -> None:
    path = log_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_postgres(row: dict[str, Any]) -> None:
    import psycopg2

    url = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO retrieval_logs
                  (log_id, session_id, query, search_query, hit_count, top_source_file, refused, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    UUID(row["log_id"]),
                    row.get("session_id"),
                    row["query"],
                    row.get("search_query"),
                    row["hit_count"],
                    row.get("top_source_file"),
                    row["refused"],
                    row["created_at"],
                ),
            )
        conn.commit()
    finally:
        conn.close()
