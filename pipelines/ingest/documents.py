"""Load raw documents from data/raw (M1: md/txt).

跳过 README.md；title 取首行 # 标题。见 docs/m1_ingest.md §4。
"""

from dataclasses import dataclass
from pathlib import Path

SUPPORTED_SUFFIXES = {".md", ".txt", ".markdown", ".pdf"}


@dataclass(frozen=True)
class RawDocument:
    doc_id: str
    source_file: str
    title: str
    text: str


def load_documents(input_dir: Path) -> list[RawDocument]:
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    docs: list[RawDocument] = []
    for path in sorted(input_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        if path.name.lower() == "readme.md":
            continue
        if path.suffix.lower() == ".pdf":
            from pipelines.ingest.deepdoc.layout import extract_pdf_with_tables

            text = extract_pdf_with_tables(path).strip()
        else:
            text = path.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            continue
        from pipelines.ingest.deepdoc.layout import split_markdown_pipe_tables
        from pipelines.ingest.deepdoc.table_parser import append_table_rows_as_lines
        from pipelines.ingest.multimodal.caption_stub import extract_image_captions
        from pipelines.ingest.multimodal.ocr import ocr_images_in_markdown

        text = split_markdown_pipe_tables(text)
        text = append_table_rows_as_lines(text)
        caps = extract_image_captions(text)
        if caps:
            text = text + "\n\n（图示说明）\n" + "\n".join(caps)
        text = ocr_images_in_markdown(text, path.parent)
        rel = path.relative_to(input_dir).as_posix()
        doc_id = Path(rel).with_suffix("").as_posix()
        docs.append(
            RawDocument(
                doc_id=doc_id,
                source_file=rel,
                title=_extract_title(text, path.stem),
                text=text,
            )
        )
    return docs


def _extract_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback
