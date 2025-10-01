"""Application Configuration

Type-safe configuration using Pydantic Settings for environment variable handling.
Shows how to properly manage configuration in modern Python applications.

Patterns Demonstrated:
- Type-safe environment variable parsing with validation
- Sensible defaults for development
- Clear separation of infrastructure vs application config
- No magic strings in the codebase
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables"""

    # =============================================================================
    # APPLICATION
    # =============================================================================

    app_name: str = Field(..., alias="APP_NAME")
    app_version: str = Field(..., alias="APP_VERSION")
    app_description: str = Field(..., alias="APP_DESCRIPTION")
    environment: str = Field(..., alias="ENVIRONMENT")

    # =============================================================================
    # API CONFIGURATION
    # =============================================================================

    api_host: str = Field(..., alias="API_HOST")
    api_port: int = Field(..., alias="API_PORT")
    log_level: str = Field(..., alias="LOG_LEVEL")

    # CORS Settings
    cors_origins: str = Field(..., alias="CORS_ORIGINS")
    cors_credentials: bool = Field(..., alias="CORS_CREDENTIALS")
    cors_methods: str = Field(..., alias="CORS_METHODS")
    cors_headers: str = Field(..., alias="CORS_HEADERS")

    # =============================================================================
    # DATABASE CONNECTIONS (Available but not required to be connected)
    # =============================================================================

    # PostgreSQL - Primary datastore
    database_url: str = Field(..., alias="DATABASE_URL")
    database_host: str = Field(..., alias="DATABASE_HOST")
    database_port: int = Field(..., alias="DATABASE_PORT")
    database_name: str = Field(..., alias="DATABASE_NAME")
    database_user: str = Field(..., alias="DATABASE_USER")
    database_password: str = Field(..., alias="DATABASE_PASSWORD")

    # Redis - Cache and queues
    redis_url: str = Field(..., alias="REDIS_URL")
    redis_host: str = Field(..., alias="REDIS_HOST")
    redis_port: int = Field(..., alias="REDIS_PORT")
    redis_password: str = Field(..., alias="REDIS_PASSWORD")

    # Neo4j - Graph database
    neo4j_uri: str = Field(..., alias="NEO4J_URI")
    neo4j_user: str = Field(..., alias="NEO4J_USER")
    neo4j_password: str = Field(..., alias="NEO4J_PASSWORD")

    # Qdrant - Vector database
    qdrant_url: str = Field(..., alias="QDRANT_URL")
    qdrant_collection: str = Field(..., alias="QDRANT_COLLECTION")

    # MinIO - Object storage
    minio_endpoint: str = Field(..., alias="MINIO_ENDPOINT")
    minio_access_key: str = Field(..., alias="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(..., alias="MINIO_SECRET_KEY")
    minio_secure: bool = Field(..., alias="MINIO_SECURE")
    minio_bucket_name: str = Field(..., alias="MINIO_BUCKET_NAME")

    # =============================================================================
    # LLM CONFIGURATION
    # =============================================================================

    # Model Catalog
    model_catalog_path: str = Field(
        default="src/app/domain/model_metadata.json",
        alias="MODEL_CATALOG_PATH",
    )

    # Ollama - Local LLM
    ollama_base_url: str = Field(..., alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(..., alias="OLLAMA_MODEL")
    ollama_embedding_model: str = Field(..., alias="OLLAMA_EMBEDDING_MODEL")
    ollama_timeout: int = Field(..., alias="OLLAMA_TIMEOUT")
    ollama_pull_models: str = Field(..., alias="OLLAMA_PULL_MODELS")

    # External LLM APIs (optional)
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(..., alias="ANTHROPIC_API_KEY")
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    together_api_key: str | None = Field(default=None, alias="TOGETHER_API_KEY")
    tavily_api_key: str = Field(..., alias="TAVILY_API_KEY")

    # =============================================================================
    # PERFORMANCE
    # =============================================================================

    # Database pool settings
    db_pool_size: int = Field(..., alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(..., alias="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(..., alias="DB_POOL_TIMEOUT")
    db_echo: bool = Field(..., alias="DB_ECHO")

    # Cache settings
    cache_ttl: int = Field(..., alias="CACHE_TTL")
    cache_prefix: str = Field(..., alias="CACHE_PREFIX")

    model_config = {"env_file": ".env", "case_sensitive": False, "extra": "ignore"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.model_validate({})


settings = get_settings()
