"""A/B 实验离线聚合与显著性检验（无 scipy 时用标准库近似）."""

from __future__ import annotations

import math
from typing import Any


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(math.ceil(p * len(ordered)) - 1)))
    return float(ordered[idx])


def _norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def two_proportion_z_test(success_a: int, n_a: int, success_b: int, n_b: int) -> dict[str, Any]:
    if n_a == 0 or n_b == 0:
        return {"z": 0.0, "p_value": 1.0, "valid": False}
    p_a = success_a / n_a
    p_b = success_b / n_b
    p_pool = (success_a + success_b) / (n_a + n_b)
    denom = p_pool * (1.0 - p_pool) * (1.0 / n_a + 1.0 / n_b)
    if denom <= 0:
        return {"z": 0.0, "p_value": 1.0, "valid": False}
    z = (p_a - p_b) / math.sqrt(denom)
    p_value = 2.0 * (1.0 - _norm_cdf(abs(z)))
    return {
        "z": z,
        "p_value": p_value,
        "valid": True,
        "rate_a": p_a,
        "rate_b": p_b,
    }


def build_experiment_report(
    *,
    experiment_id: str,
    assignments: list[dict[str, Any]],
    feedback: list[dict[str, Any]],
    retrieval_logs: list[dict[str, Any]],
    min_sample_size: int = 200,
) -> dict[str, Any]:
    by_log = {str(a["log_id"]): a for a in assignments}
    fb_by_log: dict[str, list[dict[str, Any]]] = {}
    for row in feedback:
        lid = str(row.get("retrieval_log_id") or row.get("message_id") or "")
        if lid in by_log:
            fb_by_log.setdefault(lid, []).append(row)

    arms: dict[str, dict[str, Any]] = {}
    for a in assignments:
        v = str(a.get("variant", "?"))
        arms.setdefault(
            v,
            {
                "variant": v,
                "requests": 0,
                "positive": 0,
                "negative": 0,
                "feedback_count": 0,
                "refused": 0,
                "hit_counts": [],
                "latencies": [],
            },
        )
        arms[v]["requests"] += 1
        if a.get("latency_ms") is not None:
            arms[v]["latencies"].append(float(a["latency_ms"]))

    for log in retrieval_logs:
        lid = str(log.get("log_id", ""))
        a = by_log.get(lid)
        if not a:
            continue
        v = str(a.get("variant", "?"))
        if log.get("refused"):
            arms[v]["refused"] += 1
        arms[v]["hit_counts"].append(int(log.get("hit_count", 0)))

    for lid, rows in fb_by_log.items():
        a = by_log[lid]
        v = str(a.get("variant", "?"))
        arms[v]["feedback_count"] += len(rows)
        for row in rows:
            rating = int(row.get("rating", 0))
            if rating == 1:
                arms[v]["positive"] += 1
            elif rating == -1:
                arms[v]["negative"] += 1

    total_requests = len(assignments)
    arm_list = sorted(arms.values(), key=lambda x: x["variant"])
    for arm in arm_list:
        lat = arm["latencies"]
        arm["p95_latency_ms"] = _percentile(lat, 0.95) if lat else None
        hits = arm["hit_counts"]
        arm["avg_hit_count"] = sum(hits) / len(hits) if hits else None
        n_fb = arm["feedback_count"]
        arm["positive_rate"] = arm["positive"] / n_fb if n_fb else None

    recommendation = "continue"
    p_value = 1.0
    if len(arm_list) >= 2:
        a0, a1 = arm_list[0], arm_list[1]
        n_a, n_b = a0["feedback_count"], a1["feedback_count"]
        test = two_proportion_z_test(a0["positive"], n_a, a1["positive"], n_b)
        p_value = float(test["p_value"])
        if (
            total_requests >= min_sample_size
            and test["valid"]
            and n_a > 0
            and n_b > 0
            and p_value < 0.05
        ):
            if (a1.get("positive_rate") or 0) > (a0.get("positive_rate") or 0):
                recommendation = f"consider_promote_{a1['variant']}"
            elif (a0.get("positive_rate") or 0) > (a1.get("positive_rate") or 0):
                recommendation = f"consider_promote_{a0['variant']}"

    latency_warning = False
    if len(arm_list) >= 2:
        p95_a = arm_list[0].get("p95_latency_ms")
        p95_b = arm_list[1].get("p95_latency_ms")
        if p95_a and p95_b and p95_b > 1.1 * p95_a:
            latency_warning = True

    return {
        "experiment_id": experiment_id,
        "total_requests": total_requests,
        "min_sample_size": min_sample_size,
        "sample_sufficient": total_requests >= min_sample_size,
        "arms": arm_list,
        "positive_rate_p_value": p_value,
        "recommendation": recommendation,
        "latency_regression_warning": latency_warning,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# A/B 实验报告 — {report['experiment_id']}",
        "",
        f"- 总请求数：**{report['total_requests']}**（阈值 {report['min_sample_size']}）",
        f"- 样本充足：{'是' if report['sample_sufficient'] else '否'}",
        f"- 建议：**{report['recommendation']}**（须人工 promote，脚本不自动改 profile）",
        f"- 点赞率检验 p-value：{report['positive_rate_p_value']:.4f}",
    ]
    if report.get("latency_regression_warning"):
        lines.append("- ⚠ B 臂 P95 延迟相对 A 退化 >10%")
    lines.extend(["", "## 分臂指标", ""])
    for arm in report["arms"]:
        lines.append(f"### Variant {arm['variant']}")
        lines.append(f"- 请求数：{arm['requests']}")
        lines.append(f"- 反馈数：{arm['feedback_count']}")
        pr = arm.get("positive_rate")
        lines.append(f"- 点赞率：{pr:.2%}" if pr is not None else "- 点赞率：—")
        lines.append(f"- 拒答数：{arm['refused']}")
        p95 = arm.get("p95_latency_ms")
        lines.append(f"- P95 检索延迟(ms)：{p95:.1f}" if p95 is not None else "- P95 检索延迟(ms)：—")
        lines.append("")
    return "\n".join(lines)
