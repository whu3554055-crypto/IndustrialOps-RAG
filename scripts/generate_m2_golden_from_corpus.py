"""从 data/corpus/demo 章节标题生成 M2 golden 模板（可重复运行）."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "corpus" / "demo"
OUT = ROOT / "data" / "eval" / "m2_golden.jsonl.example"

# verify_m1 核心 10 题（与 golden_m7 m1_aligned 一致）
CORE: list[tuple[str, str]] = [
    ("P-101 出口压力正常范围是多少？", "samples/pump_p101_manual.md"),
    ("P-101 故障码 E01 怎么处理？", "samples/pump_p101_manual.md"),
    ("反应釜 R-201 什么情况下要按 ESD 紧急停车？", "samples/reactor_r201_sop.md"),
    ("F201-02 搅拌电流高可能是什么原因？", "samples/reactor_r201_sop.md"),
    ("空压站 ALM-101 排气温度过高怎么处理？", "samples/compressor_sa01_fault_codes.md"),
    ("SA-01 螺杆空压机排气量是多少？", "samples/compressor_sa01_fault_codes.md"),
    ("E-301 管壳式换热器设计换热面积是多少？", "samples/heat_exchanger_e301_manual.md"),
    ("E-301 检漏发现微漏点如何处理？", "samples/heat_exchanger_e301_manual.md"),
    ("CV-110 皮带机启动前必须确认哪些联锁？", "samples/conveyor_cv110_sop.md"),
    ("CV-110 跑偏报警 B201 怎么处理？", "samples/conveyor_cv110_sop.md"),
]


def _sections(md_path: Path) -> list[str]:
    text = md_path.read_text(encoding="utf-8")
    titles = []
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+)", line.strip())
        if m:
            titles.append(m.group(1).strip())
    return titles


def main() -> None:
    rows: list[dict] = []
    seen_q: set[str] = set()

    for q, doc in CORE:
        rows.append({"question": q, "doc_ids": [doc], "category": "core"})
        seen_q.add(q)

    for md in sorted(CORPUS.glob("*.md")):
        if md.name.lower() == "readme.md":
            continue
        source = f"samples/{md.name}"
        for title in _sections(md):
            for suffix in ("主要内容是什么？", "现场如何处置？"):
                q = f"{title}——{suffix}"
                if q in seen_q:
                    continue
                seen_q.add(q)
                rows.append(
                    {
                        "question": q,
                        "doc_ids": [source],
                        "category": "section",
                        "ground_truth": "",
                    }
                )

    rows = rows[:80]
    with OUT.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(rows)} rows -> {OUT}")


if __name__ == "__main__":
    main()
