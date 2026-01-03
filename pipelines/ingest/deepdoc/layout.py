"""版面增强 — PDF 表格（pdfplumber）+ Markdown 管道表拆行."""

from __future__ import annotations

import re
from pathlib import Path


def extract_pdf_with_tables(path: Path) -> str:
    """优先 pdfplumber 抽表；失败则回退 pypdf."""
    try:
        import pdfplumber
    except ImportError:
        from pipelines.ingest.deepdoc.pdf_loader import extract_pdf_text

        return extract_pdf_text(path)

    parts: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if text.strip():
                parts.append(text.strip())
            for table in page.extract_tables() or []:
                for row in table:
                    cells = [str(c or "").strip() for c in row]
                    if any(cells):
                        parts.append(" | ".join(cells))
    return "\n\n".join(parts) if parts else ""


def split_markdown_pipe_tables(text: str) -> str:
    """将管道表每行转为可检索叙述."""
    lines = text.splitlines()
    out: list[str] = []
    for line in lines:
        out.append(line)
        if "|" in line and not re.match(r"^\s*\|?[\s\-:|]+\|?\s*$", line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 2 and cells[0]:
                out.append(f"（表行）{' / '.join(cells)}")
    return "\n".join(out)
