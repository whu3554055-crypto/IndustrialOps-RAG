"""知识图谱存储 — YAML + 可选 PostgreSQL；1-hop 扩展 doc_id."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from apps.config import ROOT, get_settings, load_profile

GRAPH_YAML = ROOT / "data" / "graph" / "relations.yaml"

# 问句中常见实体 token → graph entity id
_QUERY_ALIASES: dict[str, str] = {
    "P-101": "device:P-101",
    "R-201": "device:R-201",
    "SA-01": "device:SA-01",
    "E-301": "device:E-301",
    "CV-110": "device:CV-110",
    "E01": "fault:E01",
    "E1024": "fault:E01",
    "ALM-101": "alarm:ALM-101",
    "ALM-102": "alarm:ALM-101",
    "B201": "alarm:B201",
}


@lru_cache(maxsize=1)
def load_graph() -> dict[str, Any]:
    path = Path(load_profile().get("graph", {}).get("relations_path", str(GRAPH_YAML)))
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file():
        return {"entities": [], "edges": []}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {"entities": [], "edges": []}


def match_entity_ids(query: str) -> list[str]:
    found: list[str] = []
    q = query.upper()
    for token, eid in _QUERY_ALIASES.items():
        if token.upper() in q.replace(" ", ""):
            found.append(eid)
    # 故障码 E\d+
    for m in re.finditer(r"\bE(\d{2,4})\b", query, re.I):
        found.append(f"fault:E{m.group(1)}")
    return list(dict.fromkeys(found))


def expand_doc_ids(entity_ids: list[str], hops: int = 1) -> list[str]:
    g = load_graph()
    edges = g.get("edges") or []
    docs: list[str] = []
    frontier = set(entity_ids)
    seen_e = set(entity_ids)
    for _ in range(max(1, hops)):
        next_f: set[str] = set()
        for e in edges:
            if e.get("from") in frontier or e.get("to") in frontier:
                did = e.get("doc_id")
                if did:
                    docs.append(did)
                for end in (e.get("from"), e.get("to")):
                    if end and end not in seen_e:
                        next_f.add(end)
                        seen_e.add(end)
        frontier = next_f
        if not frontier:
            break
    return list(dict.fromkeys(docs))
