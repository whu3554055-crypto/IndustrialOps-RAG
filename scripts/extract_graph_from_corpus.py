"""从语料 MD 抽取故障码/位号边，合并写入 data/graph/relations.yaml."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "corpus" / "demo"
OUT = ROOT / "data" / "graph" / "relations.yaml"

CODE_PAT = re.compile(r"\b(E\d{2,4}|ALM-\d+|B\d{3}|F\d{3}-\d+)\b", re.I)
DEVICE_PAT = re.compile(r"\b(P-\d+|R-\d+|SA-\d+|E-\d+|CV-\d+)\b", re.I)


def main() -> None:
    base = yaml.safe_load(OUT.read_text(encoding="utf-8")) if OUT.is_file() else {}
    entities = {e["id"]: e for e in base.get("entities", [])}
    edges = list(base.get("edges", []))
    seen = {(e["from"], e["to"], e.get("doc_id")) for e in edges}

    for md in sorted(CORPUS.glob("*.md")):
        if md.name.lower() == "readme.md":
            continue
        text = md.read_text(encoding="utf-8")
        doc_id = f"samples/{md.name}"
        devices = list(dict.fromkeys(DEVICE_PAT.findall(text)))
        codes = list(dict.fromkeys(CODE_PAT.findall(text)))
        for d in devices:
            eid = f"device:{d}"
            entities.setdefault(eid, {"id": eid, "label": d})
        for code in codes:
            fid = f"fault:{code.upper()}"
            entities.setdefault(fid, {"id": fid, "label": code})
            if devices:
                key = (fid, f"device:{devices[0]}", doc_id)
                if key not in seen:
                    edges.append(
                        {
                            "from": fid,
                            "to": f"device:{devices[0]}",
                            "rel": "affects",
                            "doc_id": doc_id,
                        }
                    )
                    seen.add(key)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        yaml.safe_dump(
            {"entities": list(entities.values()), "edges": edges},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    print(f"entities={len(entities)} edges={len(edges)} -> {OUT}")


if __name__ == "__main__":
    main()
