"""会话历史 — file 落盘 + 可选 PostgreSQL.

学习文档：docs/m3_agent.md；初始化：scripts/init_db.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apps.config import ROOT, get_settings, load_profile


def _cfg() -> dict:
    return load_profile().get("persistence", {})


def session_backend() -> str:
    return str(_cfg().get("session_backend", "file")).lower()


def session_file_path() -> Path:
    raw = _cfg().get("session_file", "reports/chat_sessions.json")
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


def _load_file_store() -> dict[str, list[dict[str, str]]]:
    path = session_file_path()
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_file_store(store: dict[str, list[dict[str, str]]]) -> None:
    path = session_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def get_history(session_id: str, max_turns: int = 3) -> list[dict[str, str]]:
    if session_backend() == "postgresql":
        try:
            return _get_history_postgres(session_id, max_turns)
        except Exception:
            pass
    msgs = _load_file_store().get(session_id, [])
    if max_turns <= 0:
        return []
    return msgs[-(max_turns * 2) :]


def append_turn(session_id: str, user: str, assistant: str) -> None:
    if session_backend() == "postgresql":
        try:
            _append_postgres(session_id, user, assistant)
            return
        except Exception:
            pass
    store = _load_file_store()
    store.setdefault(session_id, []).extend(
        [
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ]
    )
    _save_file_store(store)


def clear_session(session_id: str) -> None:
    if session_backend() == "postgresql":
        try:
            _clear_postgres(session_id)
            return
        except Exception:
            pass
    store = _load_file_store()
    store.pop(session_id, None)
    _save_file_store(store)


def _pg_conn():
    import psycopg2

    url = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://")
    return psycopg2.connect(url)


def _get_history_postgres(session_id: str, max_turns: int) -> list[dict[str, str]]:
    limit = max_turns * 2
    conn = _pg_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT role, content FROM chat_messages
                WHERE session_id = %s
                ORDER BY id DESC LIMIT %s
                """,
                (session_id, limit),
            )
            rows = list(reversed(cur.fetchall()))
        return [{"role": r[0], "content": r[1]} for r in rows]
    finally:
        conn.close()


def _append_postgres(session_id: str, user: str, assistant: str) -> None:
    conn = _pg_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_sessions (session_id) VALUES (%s)
                ON CONFLICT (session_id) DO UPDATE SET updated_at = NOW()
                """,
                (session_id,),
            )
            for role, content in (("user", user), ("assistant", assistant)):
                cur.execute(
                    "INSERT INTO chat_messages (session_id, role, content) VALUES (%s,%s,%s)",
                    (session_id, role, content),
                )
        conn.commit()
    finally:
        conn.close()


def _clear_postgres(session_id: str) -> None:
    conn = _pg_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chat_sessions WHERE session_id = %s", (session_id,))
        conn.commit()
    finally:
        conn.close()
