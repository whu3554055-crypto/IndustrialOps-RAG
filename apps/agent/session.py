"""In-memory session history — M3 scaffold; M6+ 可换 PostgreSQL."""

from __future__ import annotations

_store: dict[str, list[dict[str, str]]] = {}


def get_history(session_id: str, max_turns: int = 3) -> list[dict[str, str]]:
    """Return last `max_turns` user/assistant pairs as OpenAI-style messages."""
    msgs = _store.get(session_id, [])
    if max_turns <= 0:
        return []
    return msgs[-(max_turns * 2) :]


def append_turn(session_id: str, user: str, assistant: str) -> None:
    _store.setdefault(session_id, []).extend(
        [
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ]
    )


def clear_session(session_id: str) -> None:
    _store.pop(session_id, None)
