"""兼容入口 — 请用 scripts/init_db.py 初始化全部表."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    script = Path(__file__).resolve().parent / "init_db.py"
    raise SystemExit(subprocess.call([sys.executable, str(script)]))
