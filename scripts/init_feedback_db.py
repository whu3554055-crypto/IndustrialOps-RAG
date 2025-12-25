"""初始化 PostgreSQL feedback_events 表 — M7.

学习文档：docs/m7_demo.md §4.2
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.config import get_settings  # noqa: E402

SCHEMA = ROOT / "deploy" / "sql" / "feedback_schema.sql"


def main() -> None:
    import psycopg2

    url = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://")
    sql = SCHEMA.read_text(encoding="utf-8")
    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print(f"OK: applied {SCHEMA.name}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
