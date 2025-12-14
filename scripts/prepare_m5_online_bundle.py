"""列出线上训练需上传的文件（M5）."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PATHS = [
    "pipelines/finetune/train_qlora.py",
    "pipelines/finetune/README.md",
    "deploy/profiles/train-gpu-24g.yaml",
    "deploy/docker/Dockerfile.finetune",
    "deploy/compose/docker-compose.finetune.yml",
    "pyproject.toml",
    "apps/config.py",
    "data/processed/sft_train.jsonl",
    "data/processed/sft.jsonl",
    "data/processed/sft.jsonl.example",
    "docs/m5_online_train.md",
]


def main() -> None:
    out = ROOT / "reports" / "m5_online_bundle_manifest.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    missing: list[str] = []
    for rel in PATHS:
        p = ROOT / rel
        status = "OK" if p.is_file() else "MISSING"
        if status == "MISSING":
            missing.append(rel)
        lines.append(f"{status}\t{rel}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Manifest: {out}")
    if missing:
        print("Missing (create before upload):", ", ".join(missing))
        print("Tip: run split_sft_by_doc_id.py to create sft_train.jsonl")
    else:
        print("All listed files present — git clone on GPU host is usually simpler than partial upload.")


if __name__ == "__main__":
    main()
