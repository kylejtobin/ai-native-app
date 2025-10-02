"""
Integration tests for vector ingestion pipeline.

Demonstrates:
- Hybrid RAG with Qdrant (dense + sparse vectors)
- Ollama dense embedding generation
- FastEmbed SPLADE sparse embedding generation
- Pipeline pattern for observability
- Type-safe domain models for vector operations

Test Environment:
- Uses .env.test (via conftest.py) which has localhost URLs pre-configured
- Requires real Docker infrastructure running (make dev)
- Qdrant at localhost:6333, Ollama at localhost:11434
- FastEmbed SPLADE model auto-downloads on first run

Note: conftest.py loads .env.test for tests not in "integration" path,
      but .env.test has the correct localhost URLs we need anyway.
"""

from uuid import uuid4

import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from app.config import settings
from app.domain.pipeline import StageName
from app.domain.vector_ingestion import (
    DenseEmbeddingModel,
    HybridEmbedding,
    SparseEmbeddingModel,
    SparseVector,
    VectorIngestion,
    VectorType,
)


@pytest.fixture(scope="module", autouse=True)
def use_localhost_for_docker_services():
    """
    Override Docker service names with localhost for host-based integration testing.

    Why this is needed:
    - conftest.py loads .env when 'integration' in sys.argv (this file's path)
    - .env has Docker service names (http://qdrant:6333) for container-to-container
    - These tests run from host machine, need localhost:6333 to reach Docker services
    - .env.test already has localhost URLs, but conftest doesn't load it for integration/

    This fixture applies .env.test values to settings after .env is loaded.
    Alternative: Move these tests to tests/unit/ but they test real infrastructure.
    """
    settings.qdrant_url = "http://localhost:6333"
    settings.ollama_base_url = "http://localhost:11434"

    yield

    # Module teardown: Clean up any leftover test collections
    qdrant = QdrantClient(url=settings.qdrant_url)
    for collection_name in ["test_hybrid_search"]:  # Hardcoded names from manual testing
        try:
            qdrant.delete_collection(collection_name)
        except Exception:
            pass  # Collection may not exist


@pytest.fixture
def qdrant_client() -> QdrantClient:
    """Create Qdrant client for real Docker infrastructure via localhost."""
    return QdrantClient(url=settings.qdrant_url)


@pytest.fixture
def test_collection_name() -> str:
    """Generate unique collection name for test isolation."""
    return f"test_vector_ingestion_{uuid4().hex[:8]}"


@pytest.fixture
def test_collection(qdrant_client: QdrantClient, test_collection_name: str):
    """Create test collection with hybrid vectors, cleanup after test.

    Demonstrates:
    - Qdrant named vectors (dense + sparse)
    - HNSW configuration for semantic search
    - Test isolation with unique collection names
    """
    # Create collection with correct embedding dimensions
    # Note: nomic-embed-text is 768, but other models may differ
    # For tests, we'll create collection on-demand with actual vector from first embedding
    qdrant_client.create_collection(
        collection_name=test_collection_name,
        vectors_config={
            VectorType.DENSE.value: VectorParams(
                size=768,  # nomic-embed-text dimension (from settings.ollama_embedding_model)
                distance=Distance.COSINE,
            ),
        },
        sparse_vectors_config={
            VectorType.SPARSE.value: {},  # SPLADE uses default config
        },
    )

    yield test_collection_name

    # Cleanup
    try:
        qdrant_client.delete_collection(test_collection_name)
    except Exception:
        pass  # Collection may not exist if test failed early


@pytest.fixture
def ingestion() -> VectorIngestion:
    """Create VectorIngestion instance."""
    return VectorIngestion()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dense_embedding_generation(ingestion: VectorIngestion):
    """
    Demonstrates: Dense embedding via Ollama.

    Tests that we can generate semantic embeddings using local LLM.
    Dense vectors capture meaning and context for semantic similarity.
    """
    text = "Machine learning is a subset of artificial intelligence"
    model = DenseEmbeddingModel(settings.ollama_embedding_model)
    stage_name = StageName("test_dense_embed")

    stage = await ingestion._create_dense_embedding_stage(
        text=text,
        model=model,
        stage_name=stage_name,
    )

    # Verify success
    assert stage.status.value == "success"
    assert stage.name == stage_name

    # Verify embedding structure
    embedding = stage.data
    assert isinstance(embedding, HybridEmbedding)
    assert embedding.text == text
    assert len(embedding.dense) > 0  # Has embedding vector
    assert embedding.sparse is None  # Only dense at this stage
    assert not embedding.is_hybrid


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sparse_embedding_generation(ingestion: VectorIngestion):
    """
    Demonstrates: Sparse embedding via FastEmbed SPLADE.

    Tests keyword-based vector generation for exact term matching.
    Sparse vectors complement dense embeddings in hybrid search.
    """
    text = "PostgreSQL database performance optimization"
    model = SparseEmbeddingModel("prithivida/Splade_PP_en_v1")
    stage_name = StageName("test_sparse_embed")

    stage = await ingestion._create_sparse_embedding_stage(
        text=text,
        model=model,
        stage_name=stage_name,
    )

    # Verify success
    assert stage.status.value == "success"
    assert stage.name == stage_name

    # Verify embedding structure
    embedding = stage.data
    assert isinstance(embedding, HybridEmbedding)
    assert embedding.text == text
    assert embedding.sparse is not None
    assert isinstance(embedding.sparse, SparseVector)
    assert len(embedding.sparse.indices) > 0
    assert len(embedding.sparse.indices) == len(embedding.sparse.values)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upsert_to_qdrant(
    ingestion: VectorIngestion,
    qdrant_client: QdrantClient,
    test_collection: str,
):
    """
    Demonstrates: Upserting hybrid embedding to Qdrant.

    Tests that we can store points with both dense and sparse vectors,
    along with arbitrary metadata payload.
    """
    # Create a hybrid embedding
    text = "The quick brown fox jumps over the lazy dog"
    embedding = HybridEmbedding(
        text=text,
        dense=[0.1] * 768,  # Mock dense vector
        sparse=SparseVector(indices=[100, 200, 300], values=[0.5, 0.3, 0.2]),
    )
    metadata = {"source": "test", "category": "example", "text": text}
    stage_name = StageName("test_upsert")

    stage = await ingestion._create_upsert_stage(
        embedding=embedding,
        metadata=metadata,
        qdrant=qdrant_client,
        collection=test_collection,
        stage_name=stage_name,
    )

    # Verify success
    assert stage.status.value == "success"
    assert stage.name == stage_name

    # Verify in Qdrant
    collection_info = qdrant_client.get_collection(test_collection)
    assert collection_info.points_count == 1

    # Query to verify data (use named vector query for hybrid collections)
    results = qdrant_client.query_points(
        collection_name=test_collection,
        query=[0.1] * 768,  # Dense vector
        using=VectorType.DENSE.value,  # Specify which named vector to use
        limit=1,
        with_payload=True,
    )
    assert len(results.points) == 1
    point = results.points[0]
    assert point.payload["source"] == "test"
    assert point.payload["text"] == text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_hybrid_ingestion(
    ingestion: VectorIngestion,
    qdrant_client: QdrantClient,
    test_collection: str,
):
    """
    Demonstrates: Complete hybrid RAG ingestion pipeline.

    End-to-end test showing:
    1. Dense embedding generation (Ollama)
    2. Sparse embedding generation (FastEmbed SPLADE)
    3. Combining into HybridEmbedding
    4. Upserting to Qdrant with metadata
    5. Querying back to verify

    This is the full production flow for ingesting documents into vector store.
    """
    text = "Rust programming language provides memory safety without garbage collection"

    # Step 1: Generate dense embedding
    dense_stage = await ingestion._create_dense_embedding_stage(
        text=text,
        model=DenseEmbeddingModel(settings.ollama_embedding_model),
        stage_name=StageName("dense_embed"),
    )
    assert dense_stage.status.value == "success"
    dense_embedding = dense_stage.data

    # Step 2: Generate sparse embedding
    sparse_stage = await ingestion._create_sparse_embedding_stage(
        text=text,
        model=SparseEmbeddingModel("prithivida/Splade_PP_en_v1"),
        stage_name=StageName("sparse_embed"),
    )
    assert sparse_stage.status.value == "success"
    sparse_result = sparse_stage.data

    # Step 3: Combine into hybrid embedding
    hybrid_embedding = HybridEmbedding(
        text=text,
        dense=dense_embedding.dense,
        sparse=SparseVector(
            indices=sparse_result.sparse.indices,
            values=sparse_result.sparse.values,
        ),
    )
    assert hybrid_embedding.is_hybrid

    # Step 4: Upsert to Qdrant
    metadata = {"source": "integration_test", "language": "rust", "text": text}
    upsert_stage = await ingestion._create_upsert_stage(
        embedding=hybrid_embedding,
        metadata=metadata,
        qdrant=qdrant_client,
        collection=test_collection,
        stage_name=StageName("upsert"),
    )
    assert upsert_stage.status.value == "success"

    # Step 5: Verify via query
    results = qdrant_client.query_points(
        collection_name=test_collection,
        query=dense_embedding.dense,
        using=VectorType.DENSE.value,  # Specify which named vector to query
        limit=1,
        with_payload=True,
    )
    assert len(results.points) == 1
    point = results.points[0]
    assert point.payload["source"] == "integration_test"
    assert point.payload["language"] == "rust"
    assert point.payload["text"] == text
    assert point.score > 0.99  # Should match itself with high score


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dense_embedding_failure_handling(ingestion: VectorIngestion):
    """
    Demonstrates: Pipeline error handling for external service failures.

    Tests that failed stages are properly captured with error details.
    """
    text = "Test text"
    model = DenseEmbeddingModel("nonexistent-model-xyz")
    stage_name = StageName("test_failure")

    stage = await ingestion._create_dense_embedding_stage(
        text=text,
        model=model,
        stage_name=stage_name,
    )

    # Verify failure is captured
    assert stage.status.value == "failed"
    assert stage.error_category.value == "external"
    assert stage.name == stage_name
    # Error message varies - could be connection error or model not found
    assert len(stage.error.root) > 0  # Has an error message
