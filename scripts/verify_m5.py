"""M5 验收 — QLoRA 配置、SFT 数据、训练脚本 dry-run、踩坑文档.

学习文档：docs/m5_finetune.md §7
不启动 GPU 训练；RAGAS 前后对比为可选（需 reports/ragas_before.json + ragas_after.json）.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.config import load_profile  # noqa: E402
from pipelines.finetune.train_qlora import finetune_cfg, load_sft_records, validate_sft_records  # noqa: E402

SFT_EXAMPLE = ROOT / "data" / "processed" / "sft.jsonl.example"
PITFALLS = ROOT / "docs" / "finetune_pitfalls.md"
HELM_JOB = ROOT / "deploy" / "helm" / "industrial-ops-rag" / "templates" / "finetune-train-job.yaml"
TRAIN_SCRIPT = ROOT / "pipelines" / "finetune" / "train_qlora.py"
TRAIN_PROFILE = ROOT / "deploy" / "profiles" / "train-gpu-24g.yaml"
MINI_PROFILE = ROOT / "deploy" / "profiles" / "dev-finetune-mini.yaml"
SFT_TRAIN = ROOT / "data" / "processed" / "sft_train.jsonl"


def _check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {label}" + (f" — {detail}" if detail else ""))
    return ok


def _case_profile(report: dict) -> bool:
    cfg = finetune_cfg(load_profile())
    required = (
        "base_model",
        "qlora_r",
        "qlora_alpha",
        "max_seq_length",
        "gradient_checkpointing",
    )
    ok = all(k in cfg and cfg[k] is not None for k in required)
    detail = f"base={cfg.get('base_model')} r={cfg.get('qlora_r')}"
    _check("profile finetune", ok, detail)
    report["cases"].append({"name": "profile_finetune", "ok": ok, "cfg": cfg})
    return ok


def _case_sft_example(report: dict) -> bool:
    ok = SFT_EXAMPLE.is_file()
    if ok:
        try:
            recs = load_sft_records(SFT_EXAMPLE, max_samples=10)
            validate_sft_records(recs)
            detail = f"{len(recs)} rows in example"
        except (ValueError, OSError) as exc:
            ok = False
            detail = str(exc)[:80]
    else:
        detail = "missing sft.jsonl.example"
    _check("SFT example dataset", ok, detail)
    report["cases"].append({"name": "sft_example", "ok": ok, "detail": detail})
    return ok


def _case_train_dry_run(dataset: Path | None, report: dict) -> bool:
    ds = dataset or SFT_EXAMPLE
    cmd = [
        sys.executable,
        str(TRAIN_SCRIPT),
        "--dry-run",
        "--dataset",
        str(ds),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
        ok = proc.returncode == 0 and "[dry-run]" in proc.stdout
        detail = "dry-run OK" if ok else (proc.stderr or proc.stdout)[-120:]
    except subprocess.TimeoutExpired:
        ok = False
        detail = "timeout"
    _check("train_qlora --dry-run", ok, detail)
    report["cases"].append({"name": "train_dry_run", "ok": ok, "dataset": str(ds)})
    return ok


def _case_pitfalls_doc(report: dict) -> bool:
    text = PITFALLS.read_text(encoding="utf-8") if PITFALLS.is_file() else ""
    data_rows = [
        ln
        for ln in text.splitlines()
        if ln.startswith("| ") and ln[2:3].isdigit() and "（待填）" not in ln
    ]
    ok = len(data_rows) >= 8
    _check("finetune_pitfalls.md", ok, f"data rows={len(data_rows)}/8")
    report["cases"].append({"name": "pitfalls_doc", "ok": ok})
    return ok


def _case_online_profile(report: dict) -> bool:
    ok = TRAIN_PROFILE.is_file()
    detail = ""
    if ok:
        cfg = finetune_cfg(load_profile("train-gpu-24g"))
        ok = int(cfg.get("max_seq_length", 0)) >= 4096 and float(cfg.get("num_train_epochs", 0)) >= 2
        detail = f"max_seq={cfg.get('max_seq_length')} epochs={cfg.get('num_train_epochs')}"
    _check("profile train-gpu-24g (online)", ok, detail)
    report["cases"].append({"name": "train_gpu_24g_profile", "ok": ok})
    return ok


def _case_mini_profile(report: dict) -> bool:
    ok = MINI_PROFILE.is_file()
    detail = ""
    if ok:
        cfg = finetune_cfg(load_profile("dev-finetune-mini"))
        ok = int(cfg.get("max_seq_length", 9999)) <= 512 and int(
            cfg.get("gradient_accumulation_steps", 99)
        ) <= 4
        detail = f"max_seq={cfg.get('max_seq_length')} accum={cfg.get('gradient_accumulation_steps')}"
    _check("profile dev-finetune-mini (6GB)", ok, detail)
    report["cases"].append({"name": "dev_finetune_mini_profile", "ok": ok})
    return ok


def _case_sft_train_split(report: dict) -> bool:
    ok = SFT_TRAIN.is_file()
    detail = "run split_sft_by_doc_id.py" if not ok else ""
    if ok:
        try:
            recs = load_sft_records(SFT_TRAIN, max_samples=5)
            validate_sft_records(recs)
            detail = f"{len(load_sft_records(SFT_TRAIN))} train rows"
        except (ValueError, OSError) as exc:
            ok = False
            detail = str(exc)[:80]
    _check("sft_train.jsonl", ok, detail)
    report["cases"].append({"name": "sft_train_split", "ok": ok})
    return ok


def _case_helm_job_template(report: dict) -> bool:
    ok = HELM_JOB.is_file() and "trainJob.enabled" in HELM_JOB.read_text(encoding="utf-8")
    _check("Helm finetune Job template", ok)
    report["cases"].append({"name": "helm_train_job", "ok": ok})
    return ok


def _case_ragas_compare(report: dict) -> bool:
    before = ROOT / "reports" / "ragas_before.json"
    after = ROOT / "reports" / "ragas_after.json"
    if not before.is_file() or not after.is_file():
        _check("RAGAS before/after (optional)", True, "skipped — reports not present")
        report["cases"].append({"name": "ragas_compare", "ok": True, "skipped": True})
        return True
    detail = ""
    try:
        b = json.loads(before.read_text(encoding="utf-8"))
        a = json.loads(after.read_text(encoding="utf-8"))
        keys = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")
        improved = any(float(a.get(k, 0)) > float(b.get(k, 0)) for k in keys if k in a and k in b)
        ok = improved or a == b
        detail = f"before={ {k: b.get(k) for k in keys} } after={ {k: a.get(k) for k in keys} }"
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        ok = False
        detail = str(exc)[:80]
    _check("RAGAS before/after", ok, detail)
    report["cases"].append({"name": "ragas_compare", "ok": ok})
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="M5 finetune verification")
    parser.add_argument("--dataset", type=Path, default=None, help="Use your sft.jsonl for dry-run")
    parser.add_argument("--check-ragas", action="store_true", help="Require ragas before/after reports")
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()

    report: dict = {"milestone": "M5", "cases": []}
    results = [
        _case_profile(report),
        _case_mini_profile(report),
        _case_online_profile(report),
        _case_sft_example(report),
        _case_sft_train_split(report),
        _case_train_dry_run(args.dataset or SFT_TRAIN if SFT_TRAIN.is_file() else None, report),
        _case_pitfalls_doc(report),
        _case_helm_job_template(report),
    ]
    if args.check_ragas:
        before = ROOT / "reports" / "ragas_before.json"
        after = ROOT / "reports" / "ragas_after.json"
        if not before.is_file() or not after.is_file():
            _check("RAGAS before/after", False, "missing reports/ragas_*.json")
            results.append(False)
        else:
            results.append(_case_ragas_compare(report))
    else:
        _case_ragas_compare(report)

    ok_all = all(results)
    report["ok"] = ok_all
    print(f"\nM5 verify: {'PASS' if ok_all else 'FAIL'} ({sum(results)}/{len(results)} required)")
    if args.write_report:
        out = ROOT / "reports" / "m5_verify.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Report: {out}")
    raise SystemExit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
