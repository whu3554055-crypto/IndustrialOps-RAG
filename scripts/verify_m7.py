"""M7 脚手架验收 — 语料/反馈/demo 代码齐全（默认 9 项全必过）.

学习文档：docs/m7_demo.md §7.1
不依赖 Milvus/vLLM/ingest/live 问答；那些是本机「执行操作」，硬件不足可不跑。

--check-live：额外执行 Gateway 探活，非默认验收项。
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
from apps.feedback import FeedbackEvent, append_feedback, load_feedback_events  # noqa: E402
from pipelines.evaluation.run_ragas import load_golden  # noqa: E402

M7_DOC = ROOT / "docs" / "m7_demo.md"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ragas-ci.yml"
DEMO_CORPUS = ROOT / "data" / "corpus" / "demo"
GOLDEN_M7 = ROOT / "data" / "eval" / "golden_m7.jsonl.example"
SEED_SCRIPT = ROOT / "scripts" / "seed_demo_corpus.py"
FEEDBACK_SCHEMA = ROOT / "deploy" / "sql" / "feedback_schema.sql"
EXPORT_SCRIPT = ROOT / "pipelines" / "feedback" / "export_feedback.py"
WEB_APP = ROOT / "apps" / "web" / "app.py"
DEMO_UI = ROOT / "apps" / "web" / "demo_ui.py"
REQUIRED_CORPUS = (
    "pump_p101_manual.md",
    "reactor_r201_sop.md",
    "compressor_sa01_fault_codes.md",
    "heat_exchanger_e301_manual.md",
    "conveyor_cv110_sop.md",
)


def _check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {label}" + (f" — {detail}" if detail else ""))
    return ok


def _case_demo_corpus(report: dict) -> bool:
    missing = [n for n in REQUIRED_CORPUS if not (DEMO_CORPUS / n).is_file()]
    ok = not missing
    detail = f"{len(REQUIRED_CORPUS) - len(missing)}/{len(REQUIRED_CORPUS)} files" if ok else f"missing {missing}"
    _check("demo corpus (tracked)", ok, detail)
    report["cases"].append({"name": "demo_corpus", "ok": ok})
    return ok


def _case_golden_m7(report: dict) -> bool:
    ok = GOLDEN_M7.is_file()
    detail = ""
    if ok:
        rows = load_golden(GOLDEN_M7)
        ok = len(rows) >= 10
        detail = f"{len(rows)} rows"
    _check("golden_m7.jsonl.example", ok, detail)
    report["cases"].append({"name": "golden_m7", "ok": ok})
    return ok


def _case_profile_demo(report: dict) -> bool:
    demo = load_profile().get("demo", {})
    ok = bool(demo.get("corpus_path")) and bool(demo.get("golden_example"))
    detail = f"corpus={demo.get('corpus_path')}"
    _check("profile demo section", ok, detail)
    report["cases"].append({"name": "profile_demo", "ok": ok})
    return ok


def _case_seed_script(report: dict) -> bool:
    ok = SEED_SCRIPT.is_file()
    if ok:
        proc = subprocess.run(
            [sys.executable, str(SEED_SCRIPT)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
            cwd=str(ROOT),
        )
        ok = proc.returncode == 0
        detail = "seed OK" if ok else (proc.stderr or proc.stdout)[-80:]
    else:
        detail = "missing script"
    _check("seed_demo_corpus.py", ok, detail)
    report["cases"].append({"name": "seed_script", "ok": ok})
    return ok


def _case_feedback_roundtrip(report: dict) -> bool:
    event = FeedbackEvent(
        session_id="verify-m7",
        message_id="msg-verify",
        rating=-1,
        comment="scaffold test",
        query="演示问句",
        answer_preview="演示答案",
    )
    saved = append_feedback(event)
    rows = load_feedback_events(limit=20)
    ok = any(r.get("message_id") == "msg-verify" for r in rows)
    _check("feedback append/load", ok, saved.get("stored", ""))
    report["cases"].append({"name": "feedback_roundtrip", "ok": ok})
    return ok


def _case_export_script(report: dict) -> bool:
    ok = EXPORT_SCRIPT.is_file() and FEEDBACK_SCHEMA.is_file()
    _check("feedback export + SQL schema", ok)
    report["cases"].append({"name": "feedback_export", "ok": ok})
    return ok


def _case_web_demo(report: dict) -> bool:
    ok = DEMO_UI.is_file()
    text = DEMO_UI.read_text(encoding="utf-8") if ok else ""
    ok = ok and "/v1/feedback" in text and "/v1/chat" in text
    _check("Gradio demo UI", ok)
    report["cases"].append({"name": "web_demo", "ok": ok})
    return ok


def _case_ci_workflow(report: dict) -> bool:
    ok = CI_WORKFLOW.is_file()
    text = CI_WORKFLOW.read_text(encoding="utf-8") if ok else ""
    ok = ok and "verify_m7" in text and "golden_m7" in text
    _check("GitHub CI includes verify_m7", ok)
    report["cases"].append({"name": "ci_workflow", "ok": ok})
    return ok


def _case_m7_doc(report: dict) -> bool:
    ok = M7_DOC.is_file()
    text = M7_DOC.read_text(encoding="utf-8") if ok else ""
    ok = ok and "verify_m7" in text and "脱敏" in text
    _check("docs/m7_demo.md", ok)
    report["cases"].append({"name": "m7_doc", "ok": ok})
    return ok


def _case_gateway_feedback_impl(report: dict) -> bool:
    main_py = ROOT / "apps" / "gateway" / "main.py"
    text = main_py.read_text(encoding="utf-8")
    ok = "append_feedback" in text and "run_ingest_job" in text
    _check("gateway feedback wired", ok)
    report["cases"].append({"name": "gateway_feedback", "ok": ok})
    return ok


def _case_live_gateway(report: dict) -> bool:
    """仅在使用 --check-live 时调用；Gateway 不可达则 FAIL（非默认脚手架）."""
    import httpx

    url = load_profile().get("demo", {}).get("gateway_url", "http://localhost:8080")
    try:
        r = httpx.get(f"{url.rstrip('/')}/v1/health", timeout=3.0)
        ok = r.status_code == 200
        detail = "live OK" if ok else f"status={r.status_code}"
    except Exception as exc:
        ok = False
        detail = str(exc)[:80]
    _check("gateway health (--check-live)", ok, detail)
    report["cases"].append({"name": "live_gateway", "ok": ok, "detail": detail})
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="M7 demo corpus & feedback verification")
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument(
        "--check-live",
        action="store_true",
        help="额外执行：探测 Gateway /v1/health（非默认脚手架项）",
    )
    args = parser.parse_args()

    report: dict = {"milestone": "M7", "cases": []}
    results = [
        _case_demo_corpus(report),
        _case_golden_m7(report),
        _case_profile_demo(report),
        _case_seed_script(report),
        _case_feedback_roundtrip(report),
        _case_export_script(report),
        _case_web_demo(report),
        _case_ci_workflow(report),
        _case_m7_doc(report),
        _case_gateway_feedback_impl(report),
    ]
    if args.check_live:
        results.append(_case_live_gateway(report))

    ok_all = all(results)
    report["ok"] = ok_all
    passed = sum(1 for r in results if r)
    print(f"\nM7 verify: {'PASS' if ok_all else 'FAIL'} ({passed}/{len(results)} required)")
    if args.write_report:
        out = ROOT / "reports" / "m7_verify.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Report: {out}")
    raise SystemExit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
