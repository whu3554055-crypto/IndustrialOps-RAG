"""从 M1 语料批量生成 SFT JSONL（vLLM 出题 + 抽审样例）.

数据源：data/raw 下 md/txt（与 run_ingest 相同 loader）。
默认：3 篇样例 × 每篇 3 条；调用本机 vLLM；失败时回退规则抽取。

学习：docs/m5_finetune.md §4
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.config import get_settings, resolve_vllm_model  # noqa: E402
from pipelines.ingest.documents import RawDocument, load_documents  # noqa: E402

DEFAULT_INPUT = ROOT / "data" / "raw"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "sft.generated.jsonl"
DEFAULT_REVIEW = ROOT / "data" / "processed" / "sft.review_sample.jsonl"

GENERATE_PROMPT = """你是工业设备运维培训出题专家。根据以下文档，生成恰好 {n} 条监督微调(SFT)问答。
要求：
1. 问题像现场工程师提问；答案必须严格来自文档，禁止编造文档外信息
2. 覆盖不同主题（参数、故障码、操作规程等）
3. 只输出 JSON 数组，格式 [{{"question":"...","answer":"..."}}]，不要 markdown 或其它文字

文档标题：{title}
文件名：{source_file}

---
{text}
---"""


def doc_id_for_split(doc: RawDocument) -> str:
    """与 split_sft_by_doc_id 默认 holdout 一致：用 source 文件名."""
    return Path(doc.source_file).name


def _truncate(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def _parse_qa_json(raw: str) -> list[dict[str, str]]:
    raw = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    if fence:
        raw = fence.group(1).strip()
    start, end = raw.find("["), raw.rfind("]")
    if start >= 0 and end > start:
        raw = raw[start : end + 1]
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("LLM output is not a JSON array")
    out: list[dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        q = str(item.get("question") or item.get("instruction") or "").strip()
        a = str(item.get("answer") or item.get("output") or "").strip()
        if q and a:
            out.append({"question": q, "answer": a})
    return out


def call_vllm(
    *,
    base_url: str,
    model: str,
    prompt: str,
    timeout: float,
) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 512,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer EMPTY"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return str(payload["choices"][0]["message"]["content"])


def heuristic_pairs(doc: RawDocument, n: int) -> list[dict[str, str]]:
    """无 LLM 时从表格/标题/列表抽取问答（测试与离线兜底）."""
    pairs: list[dict[str, str]] = []
    text = doc.text

    for code, symptom, action in re.findall(
        r"\|\s*(E\d+|F\d+-\d+|ALM-\d+)\s*\|\s*([^|]+)\|\s*([^|]+)\|",
        text,
    ):
        pairs.append(
            {
                "question": f"{doc.title} 中故障码 {code.strip()} 如何处理？",
                "answer": f"{symptom.strip()}；{action.strip()}",
            }
        )

    for m in re.finditer(r"^###\s+(.+)$", text, re.MULTILINE):
        title = m.group(1).strip()
        start = m.end()
        nxt = re.search(r"^#{1,3}\s+", text[start:], re.MULTILINE)
        block = text[start : start + nxt.start()] if nxt else text[start:]
        reason = re.search(r"\*\*原因\*\*[：:]\s*(.+)", block)
        action = re.search(r"\*\*处理\*\*[：:]\s*(.+)", block)
        if reason or action:
            ans = "；".join(x.group(1).strip() for x in (reason, action) if x)
            pairs.append({"question": f"{title} 的原因和处理？", "answer": ans})

    for m in re.finditer(r"^-\s+\*\*(F\d+-\d+|[^*]+)\*\*[：:]\s*(.+)$", text, re.MULTILINE):
        code, desc = m.group(1).strip(), m.group(2).strip()
        pairs.append({"question": f"{doc.title} 故障 {code} 说明？", "answer": desc})

    for m in re.finditer(r"^-\s+(.{8,80})$", text, re.MULTILINE):
        line = m.group(1).strip()
        if "：" in line or ":" in line:
            pairs.append({"question": f"关于 {doc.title}：{line.split('：')[0].split(':')[0]}？", "answer": line})

    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for p in pairs:
        key = p["question"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(p)
    return deduped[:n]


def generate_for_doc(
    doc: RawDocument,
    *,
    per_doc: int,
    use_llm: bool,
    base_url: str,
    model: str,
    timeout: float,
    max_chars: int,
) -> list[dict[str, Any]]:
    did = doc_id_for_split(doc)
    text = _truncate(doc.text, max_chars)
    pairs: list[dict[str, str]] = []
    llm_count = 0

    if use_llm:
        prompt = GENERATE_PROMPT.format(
            n=per_doc,
            title=doc.title,
            source_file=doc.source_file,
            text=text,
        )
        try:
            raw = call_vllm(base_url=base_url, model=model, prompt=prompt, timeout=timeout)
            pairs = _parse_qa_json(raw)[:per_doc]
            llm_count = len(pairs)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError) as exc:
            print(f"[warn] LLM failed for {doc.source_file}: {exc}; using heuristic", file=sys.stderr)

    if len(pairs) < per_doc:
        fallback = heuristic_pairs(doc, per_doc)
        seen_q = {p["question"] for p in pairs}
        for p in fallback:
            if p["question"] not in seen_q:
                pairs.append(p)
                seen_q.add(p["question"])
            if len(pairs) >= per_doc:
                break

    records: list[dict[str, Any]] = []
    for i, p in enumerate(pairs[:per_doc]):
        records.append(
            {
                "messages": [
                    {"role": "user", "content": p["question"]},
                    {"role": "assistant", "content": p["answer"]},
                ],
                "doc_id": did,
                "source_file": doc.source_file,
                "generator": "vllm" if i < llm_count else "heuristic",
            }
        )
    return records


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r, ensure_ascii=False) for r in records]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def pick_review_sample(records: list[dict[str, Any]], ratio: float, seed: int) -> list[dict[str, Any]]:
    if not records:
        return []
    rng = random.Random(seed)
    by_doc: dict[str, list[dict[str, Any]]] = {}
    for rec in records:
        by_doc.setdefault(str(rec.get("doc_id", "")), []).append(rec)
    out: list[dict[str, Any]] = []
    for doc_rows in by_doc.values():
        k = max(1, round(len(doc_rows) * ratio))
        for rec in rng.sample(doc_rows, min(k, len(doc_rows))):
            tagged = dict(rec)
            tagged["_review"] = {"status": "pending", "note": "人工抽审：核对答案是否严格来自原文"}
            out.append(tagged)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SFT JSONL from M1 raw corpus")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--review-out", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--per-doc", type=int, default=3, help="Q&A pairs per document")
    parser.add_argument("--max-docs", type=int, default=None, help="Limit documents (debug)")
    parser.add_argument("--review-ratio", type=float, default=0.34, help="Fraction per doc for review file")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-chars", type=int, default=1800, help="Truncate doc text for prompt")
    parser.add_argument("--timeout", type=float, default=180.0, help="vLLM request timeout seconds")
    parser.add_argument("--no-llm", action="store_true", help="Skip vLLM; heuristic only")
    parser.add_argument(
        "--merge-to",
        type=Path,
        default=None,
        help="Append generated rows to this JSONL (e.g. data/processed/sft.jsonl)",
    )
    args = parser.parse_args()

    input_dir = args.input if args.input.is_absolute() else ROOT / args.input
    docs = load_documents(input_dir)
    if args.max_docs is not None:
        docs = docs[: args.max_docs]
    if not docs:
        raise SystemExit(f"No documents under {input_dir}")

    s = get_settings()
    model = resolve_vllm_model()
    # Docker vLLM 常暴露 served path 作为 model id
    if model.startswith("Qwen/") and not args.no_llm:
        try:
            with urllib.request.urlopen(s.vllm_base_url.rstrip("/") + "/models", timeout=15) as resp:
                listed = json.loads(resp.read().decode())["data"]
            if listed:
                model = listed[0]["id"]
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError):
            pass

    all_records: list[dict[str, Any]] = []
    for doc in docs:
        rows = generate_for_doc(
            doc,
            per_doc=args.per_doc,
            use_llm=not args.no_llm,
            base_url=s.vllm_base_url,
            model=model,
            timeout=args.timeout,
            max_chars=args.max_chars,
        )
        print(f"[gen] {doc.source_file}: {len(rows)} rows")
        all_records.extend(rows)

    out_path = args.output if args.output.is_absolute() else ROOT / args.output
    review_path = args.review_out if args.review_out.is_absolute() else ROOT / args.review_out
    write_jsonl(out_path, all_records)
    review = pick_review_sample(all_records, args.review_ratio, args.seed)
    write_jsonl(review_path, review)

    if args.merge_to:
        merge_path = args.merge_to if args.merge_to.is_absolute() else ROOT / args.merge_to
        existing = merge_path.read_text(encoding="utf-8").strip() if merge_path.is_file() else ""
        new_body = out_path.read_text(encoding="utf-8").strip()
        merged = "\n".join(x for x in (existing, new_body) if x) + "\n"
        merge_path.parent.mkdir(parents=True, exist_ok=True)
        merge_path.write_text(merged, encoding="utf-8")
        print(f"[merge] -> {merge_path}")

    meta = {
        "input": str(input_dir),
        "documents": len(docs),
        "records": len(all_records),
        "review_samples": len(review),
        "llm": not args.no_llm,
        "model": model if not args.no_llm else None,
    }
    meta_path = out_path.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] {len(all_records)} -> {out_path}")
    print(f"[review] {len(review)} -> {review_path}")


if __name__ == "__main__":
    main()
