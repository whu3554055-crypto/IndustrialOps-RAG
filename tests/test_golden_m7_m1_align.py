"""golden_m7 与 verify_m1 的 10 题对齐检查."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "data" / "eval" / "golden_m7.jsonl.example"


def _load_m1_cases() -> list[tuple[str, str]]:
    import sys

    sys.path.insert(0, str(ROOT))
    from scripts.verify_m1 import M1_CASES

    return list(M1_CASES)


def _load_m1_aligned_golden() -> list[dict]:
    rows = []
    for line in GOLDEN.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("m1_aligned"):
            rows.append(row)
    return rows


def test_golden_m7_count_matches_m1() -> None:
    m1 = _load_m1_cases()
    golden = _load_m1_aligned_golden()
    assert len(golden) == len(m1) == 10


def test_golden_m7_questions_and_doc_ids() -> None:
    m1 = _load_m1_cases()
    golden = _load_m1_aligned_golden()
    for (q_m1, doc_m1), row in zip(m1, golden, strict=True):
        assert row["question"] == q_m1
        doc_ids = row["doc_ids"]
        assert len(doc_ids) == 1
        assert doc_ids[0] == f"samples/{doc_m1}"
        assert doc_m1 in doc_ids[0]
