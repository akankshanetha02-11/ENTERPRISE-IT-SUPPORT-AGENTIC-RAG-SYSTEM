
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root directory
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):

    # -----------------------------------
    # Application Settings
    # -----------------------------------
    app_name: str = "ENTERPRISE IT SUPPORT AGENTIC RAG SYSTEM"
    app_env: str = "development"

    # -----------------------------------
    # OpenRouter LLM Settings
    # -----------------------------------
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str ="openrouter/free"

    # Legacy OpenAI compatibility
    openai_api_key: str = ""

    # -----------------------------------
    # External Search Settings
    # -----------------------------------
    tavily_api_key: str = ""

    # -----------------------------------
    # Pinecone Vector Database
    # -----------------------------------
    pinecone_api_key: str = ""
    pinecone_index_name: str = "it-support-rag"
    pinecone_namespace: str = "company-it-kb"

    # -----------------------------------
    # Embedding Model Settings
    # -----------------------------------
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # -----------------------------------
    # Retrieval Settings
    # -----------------------------------
    top_k: int = 4
    max_retries: int = 1

    # -----------------------------------
    # Admin Settings
    # -----------------------------------
    admin_api_key: str = "change-me"

    # -----------------------------------
    # Storage Paths
    # -----------------------------------
    audit_db_path: str = str(BASE_DIR / "data" / "audit.db")
    upload_dir: str = str(BASE_DIR / "uploads")
    sample_kb_dir: str = str(BASE_DIR / "data" / "sample_kb")

    # -----------------------------------
    # Pydantic Settings Configuration
    # -----------------------------------
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # -----------------------------------
    # LLM API Key Helper
    # -----------------------------------
    @property
    def llm_api_key(self) -> str:
        """
        Return OpenRouter API key.
        Use legacy OpenAI key only as fallback.
        """
        return self.openrouter_api_key or self.openai_api_key


# -----------------------------------
# Get Settings
# -----------------------------------
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


# Global settings instance
settings = get_settings()

