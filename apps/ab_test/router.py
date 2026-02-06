"""确定性粘性分流 — SHA256 分桶."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from apps.ab_test.config import ABTestConfig


@dataclass(frozen=True)
class VariantSelection:
    variant: str
    mode: str
    experiment_id: str


def select_variant(session_id: str, config: ABTestConfig) -> VariantSelection:
    """同一 experiment_id + session_id 始终落到同一 arm."""
    key = f"{config.experiment_id}:{session_id}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 10000
    threshold = int(config.traffic_split * 10000)
    if bucket < threshold:
        arm = config.version_b
    else:
        arm = config.version_a
    return VariantSelection(
        variant=arm.label,
        mode=arm.mode,
        experiment_id=config.experiment_id,
    )
