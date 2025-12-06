"""Text chunking with Chinese-friendly separators.

默认 512 字 / overlap 64；分隔符优先段落与中文句号。docs/m1_ingest.md §4.2
"""

from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from pipelines.ingest.documents import RawDocument

SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", " ", ""]


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    source_file: str
    title: str
    chunk_index: int
    text: str


def chunk_documents(
    docs: list[RawDocument],
    *,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[Chunk]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=SEPARATORS,
        length_function=len,
    )
    chunks: list[Chunk] = []
    for doc in docs:
        parts = splitter.split_text(doc.text)
        for idx, text in enumerate(parts):
            text = text.strip()
            if not text:
                continue
            chunks.append(
                Chunk(
                    chunk_id=f"{doc.doc_id}#{idx}",
                    doc_id=doc.doc_id,
                    source_file=doc.source_file,
                    title=doc.title,
                    chunk_index=idx,
                    text=text,
                )
            )
    return chunks
