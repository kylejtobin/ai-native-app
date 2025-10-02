"""Vector Ingestion Base - Minimal pipeline infrastructure for hybrid RAG.

Provides base class and helpers for Qdrant vector ingestion with hybrid search
(dense + sparse embeddings). Concrete classes add domain-specific semantics.

Architecture:
    VectorIngestion (base) → Provides pipeline tracking + embedding helpers
    ├─ ConversationVectorIngestion → Embeds conversation history
    ├─ DocumentVectorIngestion → Chunks and embeds documents
    └─ GraphEntityVectorIngestion → Embeds graph entity summaries

Key Principles:
    - Compose Qdrant's types (SparseVector, Payload, VectorStruct) directly
    - No wrapper types that add no value (type safety comes from composition)
    - Base class provides infrastructure, not abstracted domain logic
    - Concrete classes own their domain semantics (IDs, metadata, orchestration)
    - Type safety eliminates dict[str, Any] at every boundary

Hybrid Search Design:
    - Dense vectors: Semantic similarity via Ollama (local, private)
    - Sparse vectors: Keyword matching via FastEmbed SPLADE (ONNX, no PyTorch)
    - Named vectors: Qdrant stores both in single point for RRF/DBSF fusion
    - Payload: Domain metadata for filtering and context

See Also:
    - pipeline.py: Pipeline primitive for stage tracking
    - storage.py: Pattern for composing vendor clients
    - type-system.md: When to wrap vs compose external types
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, RootModel
from qdrant_client.models import Payload, SparseVector, VectorStruct

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


class HybridEmbedding(BaseModel):
    """Text with both dense and sparse vector representations.

    Core data structure for hybrid search ingestion. Encapsulates text content
    with its multiple vector representations (dense for semantics, sparse for keywords).

    Attributes:
        text: Original text that was embedded
        dense: Dense embedding vector (always present)
        sparse: Sparse embedding vector (optional, using Qdrant's SparseVector)

    Why this design?
        - Type-safe: Uses Qdrant's SparseVector type directly
        - Efficient: Sparse vectors stored in compressed format (indices/values)
        - Flexible: Supports dense-only or hybrid (dense + sparse)
        - Composable: Ready for Qdrant PointStruct construction

    Invariants:
        - dense must be present (semantic search minimum)
        - sparse is optional (hybrid search enhancement)
        - Text must be non-empty (validation via Pydantic)

    Example:
        >>> from qdrant_client.models import SparseVector
        >>>
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

    Provides shared pipeline infrastructure and protected helper methods
    (_create_dense_embedding_stage, _create_sparse_embedding_stage, _create_upsert_stage).
    Concrete classes compose these with domain-specific orchestration.

    Why minimal?
        Different domains need different types:
        - Conversations: ConversationId, MessageId, conversational context
        - Documents: DocumentId, ChunkMetadata, chunking strategies
        - Graph entities: EntityId, RelationshipContext, graph summaries

        Forcing common abstractions would require generic dict[str, Any] types
        that eliminate type safety and semantic richness.

    Design Pattern:
        Base class provides infrastructure (pipeline tracking, embedding generation).
        Concrete classes provide domain semantics (what to embed, what metadata to store).

    Concrete Class Responsibilities:
        1. Define domain-specific fields (IDs, metadata types)
        2. Implement factory method that orchestrates stages
        3. Build pipeline with proper semantic types
        4. Return frozen instance with completed pipeline

    Example:
        >>> class ConversationVectorIngestion(VectorIngestion):
        ...     conversation_id: ConversationId
        ...     collection: str = "conversation"
        ...
        ...     @classmethod
        ...     async def ingest(cls, history: ConversationHistory, ...) -> ConversationVectorIngestion:
        ...         pipeline = Pipeline()
        ...         # Orchestrate domain-specific stages using base class helpers
        ...         dense_stage = await cls._create_dense_embedding_stage(...)
        ...         pipeline = pipeline.append(dense_stage)
        ...         # ... more stages
        ...         return cls(conversation_id=history.id, pipeline=pipeline)
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

        Uses local Ollama server for privacy-preserving, zero-cost inference.
        Returns HybridEmbedding with dense vector and empty sparse (sparse added separately).

        Args:
            text: Text to embed
            model: Dense embedding model identifier (e.g., "nomic-embed-text")
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

        Uses Qdrant's FastEmbed library with SPLADE model (ONNX runtime).
        Avoids heavy transformers/PyTorch dependencies while maintaining quality.

        Returns HybridEmbedding with empty dense vector—designed to be composed
        with _create_dense_embedding_stage in concrete implementations.

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

            # FastEmbed batches even single inputs; extract the only result
            fastembed_sparse = sparse_embeddings[0]

            # Convert FastEmbed's sparse format to Qdrant's SparseVector
            sparse_vec = SparseVector(
                indices=fastembed_sparse.indices.tolist(),
                values=fastembed_sparse.values.tolist(),
            )

            # Empty dense vector: concrete classes combine with dense stage
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
        payload: Payload,
        qdrant: QdrantClient,
        collection: str,
        stage_name: StageName,
    ) -> SuccessStage | FailedStage:
        """Upsert hybrid embedding to Qdrant.

        Constructs PointStruct with named vectors for hybrid search (dense + sparse).
        Named vectors enable Qdrant's RRF/DBSF fusion and per-vector filtering.

        Point Structure:
            - id: Random UUID (no deduplication - create new point per ingestion)
            - vector: Named dict mapping VectorType to embeddings
            - payload: Domain metadata for filtering and display

        Args:
            embedding: HybridEmbedding with dense and optionally sparse vectors
            payload: Qdrant payload dict (JSON-serializable metadata)
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

            # Named vectors: keys match VectorType enum for hybrid search
            vector_dict: dict[str, list[float] | SparseVector] = {VectorType.DENSE.value: embedding.dense}

            if embedding.is_hybrid and embedding.sparse:
                vector_dict[VectorType.SPARSE.value] = embedding.sparse

            # VectorStruct is Qdrant's union type for single/multi/named vectors
            vectors: VectorStruct = vector_dict  # type: ignore[assignment]

            point = PointStruct(id=str(uuid4()), vector=vectors, payload=payload)
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
    "VectorIngestion",
    "VectorType",
]
