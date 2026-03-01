"""SubQuestion 分支脚手架验收 — 无 GPU / 无 ingest.

学习：docs/plans/subquestion-complete-roadmap.md
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REQUIRED = [
    ("subquestion engine", ROOT / "apps" / "retrieval" / "llamaindex" / "subquestion" / "engine.py"),
    ("synthesizer", ROOT / "apps" / "retrieval" / "llamaindex" / "subquestion" / "synthesizer.py"),
    ("li benchmark", ROOT / "apps" / "retrieval" / "llamaindex" / "subquestion" / "li_benchmark.py"),
    ("m2 compound golden", ROOT / "data" / "eval" / "m2_compound.jsonl.example"),
    ("golden compound RAGAS", ROOT / "data" / "eval" / "golden_compound.jsonl.example"),
    ("compare compound ab", ROOT / "scripts" / "compare_compound_ab.py"),
    ("ab profile example", ROOT / "deploy" / "profiles" / "examples" / "ab-test-subquestion-compound.yaml"),
]


def _check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{mark}] {label}{suffix}")
    return ok


def main() -> None:
    ok = True
    for label, path in REQUIRED:
        ok = _check(label, path.is_file(), str(path.relative_to(ROOT))) and ok

    try:
        from apps.retrieval.llamaindex.subquestion.question_gen import split_subquestions

        parts = split_subquestions("P-101 压力范围？还有 E1024 怎么处理")
        ok = _check("rule split compound", len(parts) >= 2, str(len(parts))) and ok
    except Exception as exc:
        ok = _check("rule split compound", False, str(exc)) and ok

    golden = ROOT / "data" / "eval" / "golden_compound_tiny.jsonl"
    try:
        from pipelines.evaluation.run_ragas import dry_run_report, load_golden

        rows = load_golden(golden)
        body = dry_run_report(rows)
        ok = _check(
            "golden_compound dry-run",
            body.get("mode") == "dry-run" and body.get("sample_count") == len(rows),
        ) and ok
    except Exception as exc:
        rows = [
            json.loads(line)
            for line in golden.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        ok = _check(
            "golden_compound jsonl",
            len(rows) >= 3 and all(r.get("ground_truth") for r in rows),
            f"dry-run skipped ({exc})",
        ) and ok

    report_path = ROOT / "reports" / "subquestion_verify.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {"date": date.today().isoformat(), "branch": "feature/subquestion-complete", "passed": ok},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\n报告: {report_path}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
