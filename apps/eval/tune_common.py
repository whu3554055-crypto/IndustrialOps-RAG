"""调参共用工具 — profile 临时覆盖、holdout 划分、小样本限制.

本地性能有限时：用 ``--limit`` / ``m2_golden_tiny.jsonl`` / ``--dry-run``，避免全量 80 题 × 多轮检索。
"""

from __future__ import annotations

import json
import random
import tempfile
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Iterator

import yaml

from apps.config import PROFILES_DIR, ROOT

DEFAULT_PROFILE = "dev-single-node"
TINY_GOLDEN = ROOT / "data" / "eval" / "m2_golden_tiny.jsonl"

SEARCH_SPACE: dict[str, list[int]] = {
    "retrieval.vector_top_k": [10, 20, 30, 40, 50],
    "retrieval.bm25_top_k": [10, 20, 30, 40, 50],
    "retrieval.rrf_k": [30, 40, 50, 60, 70, 80, 90, 100],
    "retrieval.rerank_top_n": [3, 5, 7, 10],
    "agent.max_history_turns": [1, 2, 3, 4, 5],
}

BAYESIAN_PARAMS: list[tuple[str, int, int]] = [
    ("retrieval.vector_top_k", 10, 50),
    ("retrieval.bm25_top_k", 10, 50),
    ("retrieval.rrf_k", 30, 100),
    ("retrieval.rerank_top_n", 3, 10),
]

PARAM_ALIASES: dict[str, str] = {
    "vector_top_k": "retrieval.vector_top_k",
    "bm25_top_k": "retrieval.bm25_top_k",
    "rrf_k": "retrieval.rrf_k",
    "rerank_top_n": "retrieval.rerank_top_n",
    "context_top_k": "retrieval.rerank_top_n",
    "max_history_turns": "agent.max_history_turns",
}


def resolve_param(name: str) -> str:
    return PARAM_ALIASES.get(name, name)


def score_result(recall: float, p95_ms: float) -> float:
    latency_term = 10000 / p95_ms if p95_ms > 0 else 0
    return recall * 0.7 + latency_term * 0.3


def objective_score(recall: float, p95_ms: float) -> float:
    """Minimization objective (negated score) for optimizers."""
    return -score_result(recall, p95_ms)


def _set_nested(data: dict, dotted: str, value: int) -> None:
    parts = dotted.split(".")
    node = data
    for key in parts[:-1]:
        node = node.setdefault(key, {})
    node[parts[-1]] = value


@contextmanager
def profile_override(profile_name: str, updates: dict[str, int]) -> Iterator[Path]:
    path = PROFILES_DIR / f"{profile_name}.yaml"
    backup = path.read_text(encoding="utf-8")
    data = yaml.safe_load(backup) or {}
    for param_path, value in updates.items():
        _set_nested(data, param_path, value)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    try:
        yield path
    finally:
        path.write_text(backup, encoding="utf-8")


def load_golden_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def write_golden_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def split_holdout(
    rows: list[dict],
    *,
    holdout_ratio: float = 0.2,
    seed: int = 42,
) -> tuple[list[dict], list[dict]]:
    if not rows:
        return [], []
    if holdout_ratio <= 0:
        return list(rows), []
    ratio = min(max(holdout_ratio, 0.05), 0.5)
    shuffled = list(rows)
    rng = random.Random(seed)
    rng.shuffle(shuffled)
    holdout_n = max(1, int(len(shuffled) * ratio))
    if holdout_n >= len(shuffled):
        holdout_n = max(1, len(shuffled) // 5)
    holdout = shuffled[:holdout_n]
    tune = shuffled[holdout_n:]
    if not tune:
        tune, holdout = holdout[1:], holdout[:1]
    return tune, holdout


@contextmanager
def limited_golden_file(source: Path, limit: int | None) -> Iterator[Path]:
    if limit is None or limit <= 0:
        yield source
        return
    rows = load_golden_rows(source)[:limit]
    if not rows:
        raise ValueError(f"golden empty or limit invalid: {source}")
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".jsonl",
        delete=False,
    ) as tmp:
        for row in rows:
            tmp.write(json.dumps(row, ensure_ascii=False) + "\n")
        tmp_path = Path(tmp.name)
    try:
        yield tmp_path
    finally:
        tmp_path.unlink(missing_ok=True)


def pick_best(results: list[dict]) -> dict | None:
    scored = [row for row in results if "score" in row]
    if not scored:
        return None
    return max(scored, key=lambda row: row["score"])


def save_tune_report(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload.setdefault("date", date.today().isoformat())
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def params_from_vector(names: list[str], values: list[int]) -> dict[str, int]:
    return dict(zip(names, values, strict=True))
