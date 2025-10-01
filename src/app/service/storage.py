"""Storage service - thin orchestrator for Redis, MinIO, and Qdrant clients."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from minio import Minio
    from qdrant_client import QdrantClient
    from redis.asyncio import Redis


class MemoryStoreConfig(BaseModel):
    """Redis connection configuration."""

    url: str

    model_config = ConfigDict(frozen=True)


class ObjectStoreConfig(BaseModel):
    """MinIO/S3 connection configuration."""

    endpoint: str
    access_key: str
    secret_key: str
    secure: bool = False

    model_config = ConfigDict(frozen=True)


class VectorStoreConfig(BaseModel):
    """Qdrant vector database configuration."""

    url: str
    collection: str

    model_config = ConfigDict(frozen=True)


class StorageService:
    """
    Thin orchestrator - lazy-loads storage clients from config.

    Responsibilities:
    - Provide Redis client for conversation history
    - Provide MinIO client for file storage
    - Provide Qdrant client for vector search
    - Lazy initialization for faster startup
    """

    def __init__(
        self,
        memory_config: MemoryStoreConfig,
        object_config: ObjectStoreConfig,
        vector_config: VectorStoreConfig,
    ):
        self.memory_config = memory_config
        self.object_config = object_config
        self.vector_config = vector_config
        self._memory_client: Redis | None = None
        self._object_client: Minio | None = None
        self._vector_client: QdrantClient | None = None

    def get_memory_client(self) -> Redis:
        """Get or create Redis client (lazy)."""
        if self._memory_client is None:
            from redis.asyncio import Redis

            self._memory_client = Redis.from_url(self.memory_config.url)
        return self._memory_client

    def get_object_client(self) -> Minio:
        """Get or create MinIO client (lazy)."""
        if self._object_client is None:
            from minio import Minio

            self._object_client = Minio(
                endpoint=self.object_config.endpoint,
                access_key=self.object_config.access_key,
                secret_key=self.object_config.secret_key,
                secure=self.object_config.secure,
            )
        return self._object_client

    def get_vector_client(self) -> QdrantClient:
        """Get or create Qdrant client (lazy)."""
        if self._vector_client is None:
            from qdrant_client import QdrantClient

            self._vector_client = QdrantClient(url=self.vector_config.url)
        return self._vector_client


def create_storage_service(
    memory_config: MemoryStoreConfig,
    object_config: ObjectStoreConfig,
    vector_config: VectorStoreConfig,
) -> StorageService:
    """Factory from infrastructure configs."""
    return StorageService(memory_config, object_config, vector_config)


__all__ = ["MemoryStoreConfig", "ObjectStoreConfig", "StorageService", "VectorStoreConfig", "create_storage_service"]
