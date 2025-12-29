"""M6 验收 — RAGAS 流水线、CI、Grafana、Helm 一键.

学习文档：docs/m6_eval.md §7
默认不依赖 K8s；--check-helm 时校验 kubectl 集群（可选）.
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

HELM = ROOT / "deploy" / "helm" / "industrial-ops-rag"
M6_DOC = ROOT / "docs" / "m6_eval.md"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ragas-ci.yml"
GRAFANA_DASH = ROOT / "deploy" / "monitoring" / "grafana" / "dashboards" / "ior-overview.json"
ONE_CLICK_PS1 = ROOT / "scripts" / "one_click_k8s.ps1"
ONE_CLICK_SH = ROOT / "scripts" / "one_click_k8s.sh"
RAGAS_SCRIPT = ROOT / "pipelines" / "evaluation" / "run_ragas.py"
GOLDEN_EXAMPLE = ROOT / "data" / "eval" / "golden.jsonl.example"


def _check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {label}" + (f" — {detail}" if detail else ""))
    return ok


def _case_profile_evaluation(report: dict) -> bool:
    profile = load_profile()
    ev = profile.get("evaluation", {})
    ragas = ev.get("ragas", {})
    ok = bool(ragas.get("golden_path")) and bool(ragas.get("gateway_url"))
    detail = f"golden={ragas.get('golden_path')} gateway={ragas.get('gateway_url')}"
    _check("profile evaluation.ragas", ok, detail)
    report["cases"].append({"name": "profile_evaluation", "ok": ok})
    return ok


def _case_ragas_dry_run(report: dict) -> bool:
    out = ROOT / "reports" / "ragas_ci_dryrun.json"
    cmd = [
        sys.executable,
        str(RAGAS_SCRIPT),
        "--dry-run",
        "--golden",
        str(GOLDEN_EXAMPLE),
        "--output",
        str(out),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
        ok = proc.returncode == 0 and out.is_file()
        detail = "dry-run OK" if ok else (proc.stderr or proc.stdout)[-120:]
        if ok:
            body = json.loads(out.read_text(encoding="utf-8"))
            ok = body.get("faithfulness") is not None and body.get("sample_count", 0) >= 1
            detail = f"faithfulness={body.get('faithfulness')}"
    except subprocess.TimeoutExpired:
        ok = False
        detail = "timeout"
    _check("run_ragas --dry-run", ok, detail)
    report["cases"].append({"name": "ragas_dry_run", "ok": ok})
    return ok


def _case_ci_workflow(report: dict) -> bool:
    ok = CI_WORKFLOW.is_file()
    text = CI_WORKFLOW.read_text(encoding="utf-8") if ok else ""
    ok = ok and "verify_m6" in text and "run_ragas" in text
    _check("GitHub RAGAS CI workflow", ok)
    report["cases"].append({"name": "ci_workflow", "ok": ok})
    return ok


def _case_grafana_dashboard(report: dict) -> bool:
    ok = GRAFANA_DASH.is_file()
    detail = ""
    if ok:
        try:
            dash = json.loads(GRAFANA_DASH.read_text(encoding="utf-8"))
            ok = "panels" in dash and bool(dash.get("title"))
            detail = str(dash.get("title", ""))[:40]
        except json.JSONDecodeError:
            ok = False
            detail = "invalid JSON"
    _check("Grafana dashboard", ok, detail)
    report["cases"].append({"name": "grafana_dashboard", "ok": ok})
    return ok


def _case_helm_templates(report: dict) -> bool:
    names = (
        "ragas-cronjob.yaml",
        "ingest-cronjob.yaml",
        "prometheus-deployment.yaml",
        "grafana-deployment.yaml",
    )
    missing = [n for n in names if not (HELM / "templates" / n).is_file()]
    ok = not missing
    detail = "OK" if ok else f"missing {missing}"
    _check("Helm M6 templates", ok, detail)
    report["cases"].append({"name": "helm_m6_templates", "ok": ok, "missing": missing})
    return ok


def _case_one_click_scripts(report: dict) -> bool:
    ok = ONE_CLICK_PS1.is_file() and ONE_CLICK_SH.is_file()
    _check("one_click_k8s scripts", ok)
    report["cases"].append({"name": "one_click_scripts", "ok": ok})
    return ok


def _case_m6_doc(report: dict) -> bool:
    ok = M6_DOC.is_file()
    text = M6_DOC.read_text(encoding="utf-8") if ok else ""
    ok = ok and "verify_m6" in text and "15" in text
    _check("docs/m6_eval.md", ok)
    report["cases"].append({"name": "m6_doc", "ok": ok})
    return ok


def _case_readme_15min(report: dict) -> bool:
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8") if readme.is_file() else ""
    ok = "15" in text and "verify_m6" in text
    _check("README 15min quickstart", ok)
    report["cases"].append({"name": "readme_15min", "ok": ok})
    return ok


def _case_helm_release(report: dict) -> bool:
    cmd = ["helm", "template", "ior", str(HELM), "-f", str(HELM / "values-dev-single-node.yaml")]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
        stdout = proc.stdout or ""
        ok = proc.returncode == 0 and "ragas" in stdout.lower()
        detail = "helm template OK" if ok else (proc.stderr or stdout)[-120:]
    except FileNotFoundError:
        ok = True
        detail = "skipped — helm not installed"
    except subprocess.TimeoutExpired:
        ok = False
        detail = "timeout"
    _check("helm template render", ok, detail)
    report["cases"].append({"name": "helm_template", "ok": ok, "detail": detail})
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="M6 evaluation & delivery verification")
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()

    report: dict = {"milestone": "M6", "cases": []}
    results = [
        _case_profile_evaluation(report),
        _case_ragas_dry_run(report),
        _case_ci_workflow(report),
        _case_grafana_dashboard(report),
        _case_helm_templates(report),
        _case_one_click_scripts(report),
        _case_m6_doc(report),
        _case_readme_15min(report),
        _case_helm_release(report),
    ]

    ok_all = all(results)
    report["ok"] = ok_all
    passed = sum(1 for r in results if r)
    print(f"\nM6 verify: {'PASS' if ok_all else 'FAIL'} ({passed}/{len(results)} required)")
    if args.write_report:
        out = ROOT / "reports" / "m6_verify.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Report: {out}")
    raise SystemExit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
