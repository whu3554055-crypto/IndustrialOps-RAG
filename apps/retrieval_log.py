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


def load_recent_logs(limit: int = 50) -> list[dict[str, Any]]:
    if log_backend() == "postgresql":
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor

            url = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://")
            conn = psycopg2.connect(url)
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        "SELECT log_id::text, session_id, query, hit_count, refused, created_at "
                        "FROM retrieval_logs ORDER BY created_at DESC LIMIT %s",
                        (limit,),
                    )
                    return [dict(r) for r in cur.fetchall()]
            finally:
                conn.close()
        except Exception:
            pass
    rows: list[dict[str, Any]] = []
    path = log_file_path()
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows[-limit:]


def write_retrieval_log(
    *,
    log_id: str,
    session_id: str,
    query: str,
    search_query: str,
    hits: list[dict[str, Any]],
    refused: bool,
    experiment_id: str | None = None,
    variant: str | None = None,
    retrieval_mode: str | None = None,
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
        "experiment_id": experiment_id,
        "variant": variant,
        "retrieval_mode": retrieval_mode,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    from apps.metrics import inc_retrieval_log

    if log_backend() == "postgresql":
        try:
            _write_postgres(row)
            row["stored"] = "postgresql"
            inc_retrieval_log()
            return row
        except Exception:
            pass
    _append_file(row)
    row["stored"] = "file"
    inc_retrieval_log()
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
                  (log_id, session_id, query, search_query, hit_count, top_source_file,
                   refused, experiment_id, variant, retrieval_mode, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    UUID(row["log_id"]),
                    row.get("session_id"),
                    row["query"],
                    row.get("search_query"),
                    row["hit_count"],
                    row.get("top_source_file"),
                    row["refused"],
                    row.get("experiment_id"),
                    row.get("variant"),
                    row.get("retrieval_mode"),
                    row["created_at"],
                ),
            )
        conn.commit()
    finally:
        conn.close()
