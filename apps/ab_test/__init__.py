"""A/B 测试 — Phase 3 search-only 起步，见 docs/plans/phase3-ab-test-design.md."""

from apps.ab_test.analyze import build_experiment_report, render_markdown
from apps.ab_test.config import ABTestConfig, load_ab_test_config
from apps.ab_test.resolve import ResolvedRetrieval, resolve_retrieval_mode
from apps.ab_test.router import VariantSelection, select_variant

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
