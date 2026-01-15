"""v0.2 代码完备性验收 — 无 GPU."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CHECKS = [
    ("graph relations.yaml", ROOT / "data" / "graph" / "relations.yaml"),
    ("graph store", ROOT / "apps" / "retrieval" / "graph" / "store.py"),
    ("deepdoc layout", ROOT / "pipelines" / "ingest" / "deepdoc" / "layout.py"),
    ("multimodal ocr", ROOT / "pipelines" / "ingest" / "multimodal" / "ocr.py"),
    ("minio store", ROOT / "apps" / "storage" / "minio_store.py"),
    ("ingest cronjob", ROOT / "deploy" / "helm" / "industrial-ops-rag" / "templates" / "ingest-cronjob.yaml"),
    ("gateway Dockerfile", ROOT / "deploy" / "docker" / "Dockerfile.gateway"),
    ("prometheus gateway scrape", ROOT / "deploy" / "monitoring" / "prometheus-scrape-gateway.yaml"),
    ("merge feedback", ROOT / "scripts" / "merge_feedback_to_golden.py"),
    ("qdrant poc", ROOT / "apps" / "retrieval" / "poc" / "qdrant_poc.py"),
    ("m2 golden example", ROOT / "data" / "eval" / "m2_golden.jsonl.example"),
]


def main() -> None:
    ok = True
    for label, path in CHECKS:
        mark = path.is_file()
        print(f"[{'PASS' if mark else 'FAIL'}] {label}")
        ok = ok and mark
    try:
        from apps.retrieval.graph.store import expand_doc_ids, match_entity_ids

        ids = match_entity_ids("P-101 故障码 E01")
        docs = expand_doc_ids(ids)
        print(f"[PASS] graph expand docs={len(docs)}")
    except Exception as exc:
        print(f"[FAIL] graph logic — {exc}")
        ok = False
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
