"""Resolve finetune base_model: prefer repo-local weights from hf download --local-dir."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HF_HUB_INSTRUCT = "Qwen/Qwen2.5-7B-Instruct"

# hf download --local-dir d:\\repo\\RAG\\models\\Qwen2.5-7B-Instruct
LOCAL_INSTRUCT_CANDIDATES: tuple[str, ...] = (
    "models/Qwen2.5-7B-Instruct",
    "models/Qwen/Qwen2.5-7B-Instruct",
)


def _as_repo_path(spec: str, root: Path) -> Path:
    p = Path(spec)
    if p.is_absolute():
        return p.resolve()
    return (root / p).resolve()


def _looks_like_hub_id(spec: str) -> bool:
    norm = spec.replace("\\", "/")
    if norm.startswith(("models/", "./", "../")):
        return False
    if Path(spec).is_absolute():
        return False
    # org/repo, e.g. Qwen/Qwen2.5-7B-Instruct
    return norm.count("/") == 1


def is_usable_local_model(model_dir: Path) -> bool:
    """Enough files to load without Hub id (config + at least one weight shard)."""
    if not model_dir.is_dir():
        return False
    if not (model_dir / "config.json").is_file():
        return False
    if (model_dir / "model.safetensors").is_file():
        return True
    return bool(list(model_dir.glob("model-*-of-*.safetensors")))


def find_local_instruct(root: Path = ROOT) -> Path | None:
    for rel in LOCAL_INSTRUCT_CANDIDATES:
        candidate = (root / rel).resolve()
        if is_usable_local_model(candidate):
            return candidate
    return None


def resolve_base_model(
    spec: str | None,
    *,
    root: Path = ROOT,
    cli_override: str | None = None,
) -> str:
    """Return absolute local path or Hub model id for ``from_pretrained``."""
    raw = (cli_override or spec or HF_HUB_INSTRUCT).strip()

    if not _looks_like_hub_id(raw):
        path = _as_repo_path(raw, root)
        if is_usable_local_model(path):
            return str(path)
        if path.is_dir():
            return str(path)

    if _looks_like_hub_id(raw):
        local = find_local_instruct(root)
        if local is not None:
            return str(local)
        return raw

    return raw
