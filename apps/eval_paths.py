"""评测集路径解析 — 本地 golden 缺失时回退 .example."""

from __future__ import annotations

from pathlib import Path

from apps.config import ROOT


def resolve_eval_jsonl(path: str | Path) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    if p.is_file():
        return p
    if p.suffix == ".jsonl":
        example = p.with_name(p.stem + ".jsonl.example")
        if example.is_file():
            return example
    raise FileNotFoundError(f"Golden not found: {p} (nor {p.stem}.jsonl.example)")
