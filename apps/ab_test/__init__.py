"""A/B 测试 — Phase 3 search-only 起步，见 docs/plans/phase3-ab-test-design.md."""

from apps.ab_test.config import ABTestConfig, load_ab_test_config
from apps.ab_test.router import VariantSelection, select_variant

__all__ = [
    "ABTestConfig",
    "VariantSelection",
    "load_ab_test_config",
    "select_variant",
]
