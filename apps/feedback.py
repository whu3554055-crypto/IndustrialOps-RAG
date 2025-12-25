"""用户反馈持久化 — M7 文件落盘 + 可选 PostgreSQL.

学习文档：docs/m7_demo.md §4
默认 `file` 模式无需 DB；`postgresql` 需 Compose postgres 已启且已执行 init_feedback_db。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from apps.config import ROOT, get_settings, load_profile


@dataclass
class FeedbackEvent:
    session_id: str
    message_id: str
    rating: int
    comment: str | None = None
    query: str | None = None
    answer_preview: str | None = None
    retrieval_log_id: str | None = None
    event_id: str | None = None
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if not d.get("event_id"):
            d["event_id"] = str(uuid4())
        if not d.get("created_at"):
            d["created_at"] = datetime.now(timezone.utc).isoformat()
        return d


def _demo_config() -> dict:
    return load_profile().get("demo", {})


def feedback_backend() -> str:
    return str(_demo_config().get("feedback_backend", "file")).lower()


def feedback_file_path() -> Path:
    raw = _demo_config().get("feedback_file", "reports/feedback_events.jsonl")
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


def append_feedback(event: FeedbackEvent) -> dict[str, Any]:
    row = event.to_dict()
    backend = feedback_backend()
    if backend == "postgresql":
        try:
            _append_postgres(row)
            row["stored"] = "postgresql"
            return row
        except Exception:
            _append_file(row)
            row["stored"] = "file_fallback"
            return row
    _append_file(row)
    row["stored"] = "file"
    return row


def _append_file(row: dict[str, Any]) -> None:
    path = feedback_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _append_postgres(row: dict[str, Any]) -> None:
    import psycopg2

    url = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO feedback_events
                  (event_id, session_id, message_id, rating, comment,
                   query_text, answer_preview, retrieval_log_id, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    row["event_id"],
                    row["session_id"],
                    row["message_id"],
                    row["rating"],
                    row.get("comment"),
                    row.get("query"),
                    row.get("answer_preview"),
                    row.get("retrieval_log_id"),
                    row["created_at"],
                ),
            )
        conn.commit()
    finally:
        conn.close()


def load_feedback_events(limit: int | None = None) -> list[dict[str, Any]]:
    backend = feedback_backend()
    if backend == "postgresql":
        try:
            return _load_postgres(limit)
        except Exception:
            pass
    return _load_file(limit)


def _load_file(limit: int | None) -> list[dict[str, Any]]:
    path = feedback_file_path()
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    if limit is not None:
        return rows[-limit:]
    return rows


def _load_postgres(limit: int | None) -> list[dict[str, Any]]:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    url = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = psycopg2.connect(url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            sql = (
                "SELECT event_id, session_id, message_id, rating, comment, "
                "query_text AS query, answer_preview, retrieval_log_id, created_at "
                "FROM feedback_events ORDER BY created_at DESC"
            )
            if limit:
                sql += f" LIMIT {int(limit)}"
            cur.execute(sql)
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
