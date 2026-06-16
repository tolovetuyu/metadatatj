"""从 .env 加载配置。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")


def _bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name, str(default)).strip().lower()
    return val in ("1", "true", "yes", "on")


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


@dataclass(frozen=True)
class Settings:
    root_dir: Path = _ROOT
    knowledge_dir: Path = Path(os.getenv("KNOWLEDGE_DIR", str(_ROOT / "knowledge"))).resolve()
    chroma_persist_dir: Path = Path(
        os.getenv("CHROMA_PERSIST_DIR", str(_ROOT / "data" / "chroma"))
    ).resolve()

    recommend_host: str = os.getenv("RECOMMEND_HOST", "0.0.0.0")
    recommend_port: int = _int("RECOMMEND_PORT", 6058)
    tablemap_host: str = os.getenv("TABLEMAP_HOST", "0.0.0.0")
    tablemap_port: int = _int("TABLEMAP_PORT", 6061)

    llm_api_base: str = os.getenv("LLM_API_BASE", "https://api.openai.com/v1").rstrip("/")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    llm_timeout: int = _int("LLM_TIMEOUT", 60)
    llm_temperature: float = _float("LLM_TEMPERATURE", 0.0)

    embedding_api_base: str = os.getenv("EMBEDDING_API_BASE", "https://api.openai.com/v1").rstrip("/")
    embedding_api_key: str = os.getenv("EMBEDDING_API_KEY", "") or os.getenv("LLM_API_KEY", "")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    # 阿里云百炼限制 batch size 最大为 10
    embedding_batch_size: int = _int("EMBEDDING_BATCH_SIZE", 10)
    embedding_timeout: int = _int("EMBEDDING_TIMEOUT", 60)

    recall_top_k: int = _int("RECALL_TOP_K", 30)
    rerank_top_k: int = _int("RERANK_TOP_K", 5)
    table_match_threshold: float = _float("TABLE_MATCH_THRESHOLD", 0.75)
    field_match_threshold: float = _float("FIELD_MATCH_THRESHOLD", 0.80)

    llm_decompose_enabled: bool = _bool("LLM_DECOMPOSE_ENABLED", True)
    llm_rerank_enabled: bool = _bool("LLM_RERANK_ENABLED", True)

    admin_host: str = os.getenv("ADMIN_HOST", "0.0.0.0")
    admin_port: int = _int("ADMIN_PORT", 6070)
    admin_secret_key: str = os.getenv("ADMIN_SECRET_KEY", "metadata-tj-admin-dev")
    upload_dir: Path = Path(os.getenv("UPLOAD_DIR", str(_ROOT / "data" / "uploads"))).resolve()

    # 数据库配置
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = _int("DB_PORT", 3306)
    db_user: str = os.getenv("DB_USER", "root")
    db_password: str = os.getenv("DB_PASSWORD", "")
    db_name: str = os.getenv("DB_NAME", "metadata")
    db_charset: str = os.getenv("DB_CHARSET", "utf8mb4")
    # 数据加载模式: "db" 从数据库读取, "file" 从文件读取
    data_source: str = os.getenv("DATA_SOURCE", "file")

    # 历史推荐数据库配置（独立数据库）
    history_db_host: str = os.getenv("HISTORY_DB_HOST", os.getenv("DB_HOST", "localhost"))
    history_db_port: int = _int("HISTORY_DB_PORT", _int("DB_PORT", 3306))
    history_db_user: str = os.getenv("HISTORY_DB_USER", os.getenv("DB_USER", "root"))
    history_db_password: str = os.getenv("HISTORY_DB_PASSWORD", os.getenv("DB_PASSWORD", ""))
    history_db_name: str = os.getenv("HISTORY_DB_NAME", "metadata_history")
    history_db_charset: str = os.getenv("HISTORY_DB_CHARSET", "utf8mb4")

    # 历史推荐配置
    history_recommend_enabled: bool = _bool("HISTORY_RECOMMEND_ENABLED", False)
    history_recommend_table: str = os.getenv("HISTORY_RECOMMEND_TABLE", "rucp_history_recommend_stat")
    history_source_table: str = os.getenv("HISTORY_SOURCE_TABLE", "rucp_element_mapping_history")
    history_sync_interval_hours: float = _float("HISTORY_SYNC_INTERVAL_HOURS", 24.0)
    # 历史推荐最小匹配次数阈值（默认超过5次才纳入统计）
    history_min_match_count: int = _int("HISTORY_MIN_MATCH_COUNT", 5)

    # 人工对标过程表（rucp_task_process 与历史库同库）
    task_process_table: str = os.getenv("TASK_PROCESS_TABLE", "rucp_task_process")


settings = Settings()
