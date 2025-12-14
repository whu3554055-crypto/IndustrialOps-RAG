"""M5 SFT 划分."""

import json
from pathlib import Path

from scripts.split_sft_by_doc_id import split_file

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "data" / "processed" / "sft.jsonl.example"


def test_split_holdout(tmp_path: Path) -> None:
    train_out = tmp_path / "train.jsonl"
    hold_out = tmp_path / "hold.jsonl"
    n_train, n_hold = split_file(EXAMPLE, train_out, hold_out, {"pump_p101_manual.md"})
    assert n_hold >= 1
    assert n_train >= 1
    for line in train_out.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        did = rec.get("doc_id") or rec.get("doc_ids", [None])[0]
        assert did != "pump_p101_manual.md"
