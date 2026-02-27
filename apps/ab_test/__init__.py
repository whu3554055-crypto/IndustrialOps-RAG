"""A/B 测试 — Phase 3 search-only 起步，见 docs/plans/phase3-ab-test-design.md."""

from __future__ import annotations

from typing import Any

__all__ = [
    "ABTestConfig",
    "ResolvedRetrieval",
    "VariantSelection",
    "build_experiment_report",
    "load_ab_test_config",
    "render_markdown",
    "resolve_retrieval_mode",
    "select_variant",
]


def __getattr__(name: str) -> Any:
    if name == "build_experiment_report":
        from apps.ab_test.analyze import build_experiment_report

        return build_experiment_report
    if name == "render_markdown":
        from apps.ab_test.analyze import render_markdown

        return render_markdown
    if name == "ABTestConfig":
        from apps.ab_test.config import ABTestConfig

        return ABTestConfig
    if name == "load_ab_test_config":
        from apps.ab_test.config import load_ab_test_config

        return load_ab_test_config
    if name == "ResolvedRetrieval":
        from apps.ab_test.resolve import ResolvedRetrieval

        return ResolvedRetrieval
    if name == "resolve_retrieval_mode":
        from apps.ab_test.resolve import resolve_retrieval_mode

        return resolve_retrieval_mode
    if name == "VariantSelection":
        from apps.ab_test.router import VariantSelection

        return VariantSelection
    if name == "select_variant":
        from apps.ab_test.router import select_variant

        return select_variant
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
