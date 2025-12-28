"""多模态占位 — 从 Markdown 图片 alt 文本提取说明，不做视觉模型."""

from __future__ import annotations

import re


def extract_image_captions(markdown: str) -> list[str]:
    """返回 `![alt](path)` 中的 alt 文本列表."""
    return re.findall(r"!\[([^\]]*)\]\([^)]+\)", markdown)
