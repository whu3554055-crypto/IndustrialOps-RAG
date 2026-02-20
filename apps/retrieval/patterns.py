"""检索层共享正则 — 无重型依赖，便于单元测试."""

from __future__ import annotations

import re

FAULT_CODE_PATTERN = re.compile(
    r"\b(?:ALM|E|F)[-_]?\d{2,4}\b|\b(?:故障码|报警码)\s*[A-Z0-9-]+\b",
    re.IGNORECASE,
)
