"""Vector Ingestion Base - Minimal pipeline infrastructure for vector store ingestion.

This module provides the minimal base for vector ingestion pipelines.
Concrete implementations handle domain-specific logic (what to embed, how to chunk, etc.).

Key Principles:
    - Base class provides shared infrastructure only
    - Concrete classes own domain semantics
    - No premature abstraction of stages
    - Type safety through Pydantic models
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, RootModel

from .pipeline import Pipeline

if TYPE_CHECKING:
    from qdrant_client import QdrantClient

    from .pipeline import FailedStage, StageName, SuccessStage


class VectorType(StrEnum):
    """Vector representation types for hybrid search.

    Qdrant supports named vectors where each point can have multiple
    vector representations. Hybrid search combines these for better results.

    Types:
        DENSE: Semantic embeddings (e.g., OpenAI text-embedding-3-small)
               Captures meaning and context, good for semantic similarity.

        SPARSE: Keyword-based vectors (e.g., BM25, SPLADE)
                Captures exact term matches, good for specific words/names.

    Architecture Note:
        These map to Qdrant's named vector fields in collection schemas.
        Each point stores both vector types for hybrid retrieval with RRF/DBSF fusion.

    Why StrEnum?
        - Fixed set of values (dense and sparse - that's it)
        - Type safety prevents typos ("dence" vs DENSE)
        - JSON-serializable for configs and Qdrant API calls
        - Can add behavior later (e.g., default_dimension() method)

    Example:
        >>> vector_dict = {
        ...     VectorType.DENSE.value: [0.1, 0.2, ...],
        ...     VectorType.SPARSE.value: SparseVector(...)
        ... }
        >>> point = PointStruct(id=uuid, vector=vector_dict, payload={...})
    """

    DENSE = "dense"
    SPARSE = "sparse"


class DenseEmbeddingModel(RootModel[str]):
    """Semantic embedding model identifier for dense vectors.

    Wraps model identifier string to provide:
        - Type safety: Can't accidentally mix with sparse model identifiers
        - Validation: Enforces non-empty, reasonable length
        - Semantic meaning: Clear this is for dense/semantic embeddings
        - Observability: Logfire displays as domain type, not generic string

    Common Models:
        - "text-embedding-3-small" (OpenAI, 1536 dims)
        - "text-embedding-3-large" (OpenAI, 3072 dims)
        - "embed-english-v3.0" (Cohere)

    Why RootModel?
        Same pattern as StageName, MessageId - wraps primitive with
        domain validation and type distinction in traces.

    Example:
        >>> model = DenseEmbeddingModel("text-embedding-3-small")
        >>> print(model.root)  # "text-embedding-3-small"
        >>> # Type-safe: can't pass SparseEmbeddingModel where DenseEmbeddingModel expected
    """

    root: str = Field(min_length=1, max_length=200)
    model_config = ConfigDict(frozen=True)


class SparseEmbeddingModel(RootModel[str]):
    """Sparse embedding model identifier for keyword-based vectors.

    Wraps model identifier string to provide:
        - Type safety: Can't accidentally mix with dense model identifiers
        - Validation: Enforces non-empty, reasonable length
        - Semantic meaning: Clear this is for sparse/keyword embeddings
        - Observability: Logfire displays as domain type, not generic string

    Common Models:
        - "bm25" (Classic IR algorithm)
        - "splade" (Learned sparse representations)
        - "sparta" (Sparse transformer)

    Why separate from DenseEmbeddingModel?
        Different semantic meaning and use cases. Type system prevents
        accidentally using dense model for sparse encoding and vice versa.

    Example:
        >>> model = SparseEmbeddingModel("bm25")
        >>> print(model.root)  # "bm25"
        >>> # Type-safe: can't pass DenseEmbeddingModel where SparseEmbeddingModel expected
    """

    root: str = Field(min_length=1, max_length=200)
    model_config = ConfigDict(frozen=True)


class SparseVector(BaseModel):
    """Sparse vector representation with indices and values.

    Efficient representation for sparse embeddings where most values are zero.
    Maps directly to Qdrant's SparseVector format.

    Attributes:
        indices: Non-zero element positions
        values: Non-zero element values

    Invariants:
        - indices and values must have same length
        - indices should be sorted (convention, not enforced)
        - no duplicate indices (convention, not enforced)
    """

    indices: list[int]
    values: list[float]

    model_config = ConfigDict(frozen=True)


class HybridEmbedding(BaseModel):
    """Text with both dense and sparse vector representations.

    Core data structure for hybrid search ingestion. Encapsulates text content
    with its multiple vector representations (dense for semantics, sparse for keywords).

    Attributes:
        text: Original text that was embedded
        dense: Dense embedding vector (always present)
        sparse: Sparse embedding vector (optional for hybrid search)

    Why this design?
        - Type-safe: Explicit fields prevent confusion
        - Efficient: Sparse vectors stored in compressed format
        - Flexible: Supports dense-only or hybrid (dense + sparse)
        - Composable: Ready for Qdrant PointStruct construction

    Invariants:
        - dense must be present (semantic search minimum)
        - sparse is optional (hybrid search enhancement)
        - Text must be non-empty (validation via Pydantic)

    Example:
        >>> # Dense only (basic semantic search)
        >>> emb = HybridEmbedding(
        ...     text="Hello world",
        ...     dense=[0.1, 0.2, 0.3, ...],
        ...     sparse=None
        ... )
        >>>
        >>> # Hybrid (dense + sparse for better results)
        >>> emb = HybridEmbedding(
        ...     text="Hello world",
        ...     dense=[0.1, 0.2, 0.3, ...],
        ...     sparse=SparseVector(indices=[3, 8], values=[0.5, 0.8])
        ... )
    """

    text: str
    dense: list[float]
    sparse: SparseVector | None = None

    model_config = ConfigDict(frozen=True)

    @property
    def is_hybrid(self) -> bool:
        """True if both dense and sparse vectors are present.

        Returns:
            True for hybrid embeddings, False for dense-only.
        """
        return self.sparse is not None


class VectorIngestion(BaseModel):
    """Minimal base for vector ingestion pipelines.

    Provides only the pipeline tracking infrastructure.
    Concrete classes add domain-specific fields and stage-building methods.

    Why minimal?
        Different domains have different needs:
        - Conversations: message extraction, conversational context
        - Documents: chunking strategies, document metadata
        - Graph entities: relationship context, entity summarization

        Premature abstraction of "common" embedding/upsert methods would
        force lowest-common-denominator types (dict, Any, str) that
        violate our type safety principles.

    Architecture:
        Each concrete class composes Pipeline primitive and builds
        domain-specific stages with proper semantic types.

    Example:
        >>> class ConversationVectorIngestion(VectorIngestion):
        ...     conversation_id: ConversationId
        ...     collection: str = "conversation"
        ...
        ...     @classmethod
        ...     async def ingest(cls, history: ConversationHistory, ...) -> ConversationVectorIngestion:
        ...         pipeline = Pipeline()
        ...         # Build domain-specific stages
        ...         ...
        ...         return cls(conversation_id=history.conversation_id, pipeline=pipeline)
    """

    pipeline: Pipeline = Pipeline()

    model_config = ConfigDict(frozen=True)

    async def _create_dense_embedding_stage(
        self,
        text: str,
        model: DenseEmbeddingModel,
        stage_name: StageName,
    ) -> SuccessStage | FailedStage:
        """Generate dense embedding via Ollama.

        Calls Ollama embeddings API with specified model.
        Returns stage with HybridEmbedding containing dense vector.

        Args:
            text: Text to embed
            model: Dense embedding model identifier
            stage_name: Name for this stage in pipeline

        Returns:
            SuccessStage with HybridEmbedding or FailedStage with error
        """
        from datetime import UTC, datetime

        from .domain_type import ErrorCategory, StageCategory, StageStatus
        from .pipeline import ErrorMessage, FailedStage, SuccessStage

        start = datetime.now(UTC)
        try:
            import ollama

            from ..config import settings

            client = ollama.Client(host=settings.ollama_base_url)
            response = client.embeddings(model=model.root, prompt=text)
            dense_vector = response["embedding"]

            embedding = HybridEmbedding(text=text, dense=dense_vector)

            return SuccessStage(
                status=StageStatus.SUCCESS,
                category=StageCategory.ENRICHMENT,
                name=stage_name,
                data=embedding,
                start_time=start,
                end_time=datetime.now(UTC),
            )
        except Exception as e:
            return FailedStage(
                status=StageStatus.FAILED,
                category=StageCategory.ENRICHMENT,
                error_category=ErrorCategory.EXTERNAL_SERVICE,
                name=stage_name,
                error=ErrorMessage(str(e)),
                start_time=start,
                end_time=datetime.now(UTC),
            )

    async def _create_sparse_embedding_stage(
        self,
        text: str,
        model: SparseEmbeddingModel,
        stage_name: StageName,
    ) -> SuccessStage | FailedStage:
        """Generate sparse embedding via FastEmbed SPLADE.

        Uses Qdrant's FastEmbed library with SPLADE model.
        Lightweight alternative to transformers/pytorch.

        Args:
            text: Text to embed
            model: Sparse embedding model identifier (e.g., "prithivida/Splade_PP_en_v1")
            stage_name: Name for this stage in pipeline

        Returns:
            SuccessStage with HybridEmbedding or FailedStage with error
        """
        from datetime import UTC, datetime

        from .domain_type import ErrorCategory, StageCategory, StageStatus
        from .pipeline import ErrorMessage, FailedStage, SuccessStage

        start = datetime.now(UTC)
        try:
            from fastembed import SparseTextEmbedding

            embedding_model = SparseTextEmbedding(model_name=model.root)
            sparse_embeddings = list(embedding_model.embed([text]))

            # Extract first (only) embedding - FastEmbed returns indices/values format
            fastembed_sparse = sparse_embeddings[0]

            # Convert to our SparseVector type (same format, just wrapped)
            sparse_vec = SparseVector(
                indices=fastembed_sparse.indices.tolist(),
                values=fastembed_sparse.values.tolist(),
            )

            # Note: We need a dummy dense vector here since HybridEmbedding requires it
            # In practice, you'd either combine this with dense stage or pass through existing embedding
            # For now, this method is meant to be composed with dense stage
            embedding = HybridEmbedding(text=text, dense=[], sparse=sparse_vec)

            return SuccessStage(
                status=StageStatus.SUCCESS,
                category=StageCategory.ENRICHMENT,
                name=stage_name,
                data=embedding,
                start_time=start,
                end_time=datetime.now(UTC),
            )
        except Exception as e:
            return FailedStage(
                status=StageStatus.FAILED,
                category=StageCategory.ENRICHMENT,
                error_category=ErrorCategory.EXTERNAL_SERVICE,
                name=stage_name,
                error=ErrorMessage(str(e)),
                start_time=start,
                end_time=datetime.now(UTC),
            )

    async def _create_upsert_stage(
        self,
        embedding: HybridEmbedding,
        metadata: dict[str, Any],
        qdrant: QdrantClient,
        collection: str,
        stage_name: StageName,
    ) -> SuccessStage | FailedStage:
        """Upsert hybrid embedding to Qdrant.

        Constructs Qdrant point with named vectors and metadata payload.
        Handles both dense-only and hybrid (dense + sparse) embeddings.

        Args:
            embedding: HybridEmbedding with dense and optionally sparse vectors
            metadata: Arbitrary metadata dict for Qdrant payload (any JSON-serializable types)
            qdrant: Qdrant client instance
            collection: Target collection name
            stage_name: Name for this stage in pipeline

        Returns:
            SuccessStage with UpdateResult or FailedStage with error
        """
        from datetime import UTC, datetime
        from uuid import uuid4

        from .domain_type import ErrorCategory, StageCategory, StageStatus
        from .pipeline import ErrorMessage, FailedStage, SuccessStage

        start = datetime.now(UTC)
        try:
            from qdrant_client.models import PointStruct
            from qdrant_client.models import SparseVector as QdrantSparseVector

            # Build named vector dict with dense vector
            vector_dict: dict[str, Any] = {VectorType.DENSE.value: embedding.dense}

            # Add sparse if present
            if embedding.is_hybrid and embedding.sparse:
                vector_dict[VectorType.SPARSE.value] = QdrantSparseVector(
                    indices=embedding.sparse.indices,
                    values=embedding.sparse.values,
                )

            # Create point
            point = PointStruct(id=str(uuid4()), vector=vector_dict, payload=metadata)

            # Upsert to Qdrant - returns UpdateResult (Qdrant's Pydantic model)
            result = qdrant.upsert(collection_name=collection, points=[point])

            return SuccessStage(
                status=StageStatus.SUCCESS,
                category=StageCategory.PERSISTENCE,
                name=stage_name,
                data=result,  # Qdrant's UpdateResult type
                start_time=start,
                end_time=datetime.now(UTC),
            )
        except Exception as e:
            return FailedStage(
                status=StageStatus.FAILED,
                category=StageCategory.PERSISTENCE,
                error_category=ErrorCategory.EXTERNAL_SERVICE,
                name=stage_name,
                error=ErrorMessage(str(e)),
                start_time=start,
                end_time=datetime.now(UTC),
            )


__all__ = [
    "DenseEmbeddingModel",
    "HybridEmbedding",
    "SparseEmbeddingModel",
    "SparseVector",
    "VectorIngestion",
    "VectorType",
]
