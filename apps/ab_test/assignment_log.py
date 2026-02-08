"""A/B 实验分配记录 — file / PostgreSQL（与 persistence.retrieval_log_backend 对齐）."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from apps.config import ROOT, get_settings, load_profile


def _persistence() -> dict:
    return load_profile().get("persistence", {})


def assignment_backend() -> str:
    raw = _persistence().get("ab_assignment_backend")
    if raw is not None:
        return str(raw).lower()
    return str(_persistence().get("retrieval_log_backend", "file")).lower()


def assignment_file_path() -> Path:
    raw = _persistence().get(
        "ab_assignment_file",
        "reports/ab_assignments.jsonl",
    )
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


def write_assignment(
    *,
    log_id: str,
    experiment_id: str,
    session_id: str,
    variant: str,
    retrieval_mode: str,
    scope: str,
    latency_ms: float | None = None,
) -> dict[str, Any]:
    row = {
        "log_id": log_id,
        "experiment_id": experiment_id,
        "session_id": session_id,
        "variant": variant,
        "retrieval_mode": retrieval_mode,
        "scope": scope,
        "latency_ms": latency_ms,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if assignment_backend() == "postgresql":
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
    path = assignment_file_path()
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
                INSERT INTO ab_assignments
                  (log_id, experiment_id, session_id, variant,
                   retrieval_mode, scope, latency_ms, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    UUID(row["log_id"]),
                    row["experiment_id"],
                    row["session_id"],
                    row["variant"],
                    row["retrieval_mode"],
                    row["scope"],
                    row.get("latency_ms"),
                    row["created_at"],
                ),
            )
        conn.commit()
    finally:
        conn.close()
