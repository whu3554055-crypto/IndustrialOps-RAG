"""应用全部 PostgreSQL 表结构（feedback / session / retrieval_logs）."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.config import get_settings  # noqa: E402

SQL_FILES = (
    "feedback_schema.sql",
    "session_schema.sql",
    "retrieval_logs_schema.sql",
)


def main() -> None:
    import psycopg2

    url = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            for name in SQL_FILES:
                sql = (ROOT / "deploy" / "sql" / name).read_text(encoding="utf-8")
                cur.execute(sql)
                print(f"OK: {name}")
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
