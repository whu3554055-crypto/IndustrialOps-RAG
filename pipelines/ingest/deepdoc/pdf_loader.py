"""PDF 文本抽取（轻量）— 无版面分析，供 ingest 入库."""

from __future__ import annotations

from pathlib import Path


def extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF ingest 需要 pypdf：pip install pypdf") from exc
    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            parts.append(text.strip())
    return "\n\n".join(parts)
