"""Load profile + environment settings."""

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]
PROFILES_DIR = ROOT / "deploy" / "profiles"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ior_profile: str = "dev-single-node"
    database_url: str = "postgresql+asyncpg://ior:ior_dev@localhost:5432/industrial_ops"
    redis_url: str = "redis://localhost:6379/0"
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_collection: str = "industrial_ops_chunks"
    opensearch_host: str = "localhost"
    opensearch_port: int = 9200
    opensearch_index: str = "industrial_ops_bm25"
    llm_active_backend: str = "vllm"
    vllm_base_url: str = "http://localhost:8000/v1"
    vllm_model: str = "Qwen/Qwen2.5-7B-Instruct-AWQ"
    tensorrt_llm_base_url: str = "http://localhost:8001/v1"
    embedding_model: str = "BAAI/bge-m3"
    embedding_device: str = "cpu"
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_device: str = "cpu"
    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8080


@lru_cache
def get_settings() -> Settings:
    return Settings()


def load_profile(name: str | None = None) -> dict:
    profile = name or get_settings().ior_profile
    path = PROFILES_DIR / f"{profile}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {path}")
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)
