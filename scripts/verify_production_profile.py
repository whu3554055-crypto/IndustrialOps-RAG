"""校验 production.yaml 关键字段与 Helm values 对齐."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROD = ROOT / "deploy" / "profiles" / "production.yaml"


def main() -> None:
    if not PROD.is_file():
        print(f"Missing {PROD}", file=sys.stderr)
        sys.exit(1)
    data = yaml.safe_load(PROD.read_text(encoding="utf-8"))
    required = ("profile", "services", "llm", "retrieval", "evaluation")
    missing = [k for k in required if k not in data]
    if missing:
        print(f"FAIL missing keys: {missing}")
        sys.exit(1)
    llm = data.get("llm", {})
    if not llm.get("backends"):
        print("FAIL llm.backends empty")
        sys.exit(1)
    print(f"OK production profile keys={list(data.keys())}")
    print(f"  llm.primary={llm.get('primary')}")


if __name__ == "__main__":
    main()
