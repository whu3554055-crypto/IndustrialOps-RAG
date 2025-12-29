"""Markdown 表格行增强 — 便于 BM25 命中参数表."""

from __future__ import annotations

import re


def append_table_rows_as_lines(text: str) -> str:
    """将 | a | b | 行转为「列: 值」叙述，追加在原文后."""
    lines = text.splitlines()
    out: list[str] = []
    for line in lines:
        out.append(line)
        if "|" not in line or line.strip().startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] and cells[1]:
            out.append(f"（表）{cells[0]}：{cells[1]}")
    return "\n".join(out)
