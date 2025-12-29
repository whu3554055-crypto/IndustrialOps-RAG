"""为 golden 模板中空 ground_truth 从语料章节抽取首段填充."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "corpus" / "demo"


def _doc_text(source_file: str) -> str:
    name = Path(source_file).name
    path = CORPUS / name
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _snippet_for_question(question: str, text: str, max_len: int = 200) -> str:
    # 用问句中的设备/章节关键词在 md 中找邻近段落
    tokens = re.findall(r"[\u4e00-\u9fffA-Za-z0-9\-]+", question)
    tokens = [t for t in tokens if len(t) >= 2][:6]
    paragraphs = [p.strip() for p in re.split(r"\n\n+", text) if len(p.strip()) > 20]
    for para in paragraphs:
        if any(t in para for t in tokens):
            return para[:max_len]
    return paragraphs[0][:max_len] if paragraphs else ""


def fill_file(path: Path, *, in_place: bool) -> int:
    out_path = path if in_place else path.with_suffix(".filled.jsonl")
    filled = 0
    lines_out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("ground_truth"):
            lines_out.append(json.dumps(row, ensure_ascii=False))
            continue
        doc_ids = row.get("doc_ids") or []
        text = _doc_text(doc_ids[0]) if doc_ids else ""
        snippet = _snippet_for_question(row.get("question", ""), text)
        if snippet:
            row["ground_truth"] = snippet
            filled += 1
        lines_out.append(json.dumps(row, ensure_ascii=False))
    out_path.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
    print(f"Filled {filled} ground_truth -> {out_path}")
    return filled


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "eval" / "m2_golden.jsonl.example")
    parser.add_argument("--in-place", action="store_true")
    args = parser.parse_args()
    fill_file(args.input, in_place=args.in_place)


if __name__ == "__main__":
    main()
