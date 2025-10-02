# Semantic Search & Vector Ingestion

**Building production-ready RAG systems with hybrid search, type-safe pipelines, and domain-driven ingestion**

This document covers vector ingestion and retrieval for RAG (Retrieval-Augmented Generation) systems. You'll learn hybrid search architecture, how to design type-safe ingestion pipelines, and patterns for composing vector database types without losing semantic richness.

> **Principle: Compose Vendor Types, Don't Wrap Them**
>
> When a vendor provides well-designed Pydantic types (Qdrant's SparseVector, Payload, VectorStruct), compose them directly into your domain models. Wrapper types that add no validation or behavior are pure ceremony—they create impedance mismatch and obscure the vendor's semantics.
>
> Type safety comes from composition, not wrapping.
>
> See: [philosophy.md](../philosophy.md) "Every Type Teaches"

---

## Table of Contents

- [Hybrid Search Architecture](#hybrid-search-architecture)
- [Vector Ingestion Base](#vector-ingestion-base)
- [Composing Qdrant Types](#composing-qdrant-types)
- [Dense Embeddings with Ollama](#dense-embeddings-with-ollama)
- [Sparse Embeddings with FastEmbed](#sparse-embeddings-with-fastembed)
- [Named Vectors & Point Structure](#named-vectors--point-structure)
- [Domain-Specific Ingestion](#domain-specific-ingestion)
- [Collection Schema Design](#collection-schema-design)
- [Query Patterns](#query-patterns)
- [Decision Framework](#decision-framework)
- [Anti-Patterns](#anti-patterns)

---

## Hybrid Search Architecture

**Hybrid search combines dense (semantic) and sparse (keyword) vectors for superior retrieval accuracy.**

Modern RAG systems use hybrid search because neither dense nor sparse alone is sufficient:

- **Dense vectors** (semantic embeddings): Capture meaning and context, excellent for "find similar concepts"
- **Sparse vectors** (keyword matching): Capture exact terms, excellent for proper nouns, acronyms, specific phrases

### The Problem with Dense-Only Search

```python
# Dense embedding struggles with exact matches
query = "GraphRAG implementation"
# Finds: "knowledge graph retrieval", "entity-based RAG" ✅
# Misses: "GraphRAG" (exact term) ❌ 
```

Dense embeddings excel at semantic similarity but struggle with:
- Proper nouns ("Anthropic" vs "anthropology")
- Acronyms ("RAG" vs "rag" vs "ragged")
- Exact phrase matches ("neural network" vs "network of neurons")
- Low-frequency terms (rare technical terms)

### The Problem with Sparse-Only Search

```python
# Sparse vectors (BM25-style) struggle with synonyms
query = "automobile repair"
# Finds: documents with "automobile" and "repair" ✅
# Misses: "car maintenance" (synonyms) ❌
```

Sparse vectors excel at exact matching but struggle with:
- Synonyms ("car" vs "automobile")
- Semantic relationships ("repair" vs "fix" vs "maintain")
- Contextual meaning (polysemy)

### Hybrid Search: Best of Both Worlds

Qdrant's hybrid search combines both vector types using RRF (Reciprocal Rank Fusion) or DBSF (Distribution-Based Score Fusion):

```python
# Hybrid search example
query = "GraphRAG implementation with Claude"
# Dense: Finds semantic matches (knowledge graphs, entity extraction)
# Sparse: Finds exact terms (GraphRAG, Claude)
# Fusion: Combines scores → best of both
```

**Architecture in this codebase:**

From [`src/app/domain/vector_ingestion.py`](../../src/app/domain/vector_ingestion.py):

```python
class HybridEmbedding(BaseModel):
    """Text with both dense and sparse vector representations."""
    text: str
    dense: list[float]  # Semantic similarity
    sparse: SparseVector | None = None  # Keyword matching
    
    @property
    def is_hybrid(self) -> bool:
        return self.sparse is not None
```

---

## Vector Ingestion Base

**Minimal base class provides infrastructure; concrete classes provide domain semantics.**

The ingestion architecture follows a key principle: **avoid premature abstraction that forces generic types**.

### The Wrong Approach: Generic Ingestion

```python
# ❌ Anti-pattern: Forces dict[str, Any]
class VectorIngestion:
    async def ingest(
        self,
        text: str,
        metadata: dict[str, Any],  # Lost type safety!
        collection: str
    ) -> None:
        ...
```

**Problems:**
- `dict[str, Any]` eliminates type safety
- No domain semantics (what fields exist? what's required?)
- Can't validate at construction time
- AI/IDE can't understand structure

### The Right Approach: Minimal Base + Domain Extension

From [`src/app/domain/vector_ingestion.py:177-216`](../../src/app/domain/vector_ingestion.py):

```python
class VectorIngestion(BaseModel):
    """Minimal base for vector ingestion pipelines.
    
    Provides shared pipeline infrastructure and protected helper methods.
    Concrete classes compose these with domain-specific orchestration.
    """
    pipeline: Pipeline = Pipeline()
    model_config = ConfigDict(frozen=True)
    
    # Protected helpers for embedding generation
    async def _create_dense_embedding_stage(...) -> SuccessStage | FailedStage
    async def _create_sparse_embedding_stage(...) -> SuccessStage | FailedStage
    async def _create_upsert_stage(...) -> SuccessStage | FailedStage
```

**Base class provides:**
- Pipeline tracking (observability)
- Embedding generation helpers (dense, sparse, upsert)
- Infrastructure concerns (error handling, stage creation)

**Concrete classes provide:**
- Domain-specific fields (ConversationId, DocumentId, EntityId)
- Semantic metadata types (ConversationMetadata, DocumentMetadata)
- Orchestration logic (what to embed, how to chunk)

### Example: Conversation Ingestion (Future)

```python
class ConversationMetadata(BaseModel):
    """Type-safe metadata for conversation vectors."""
    conversation_id: ConversationId
    message_id: MessageId
    timestamp: datetime
    user_id: UserId
    model_config = ConfigDict(frozen=True)


class ConversationVectorIngestion(VectorIngestion):
    """Ingest conversation history for semantic search."""
    conversation_id: ConversationId
    collection: str = "conversation"
    
    @classmethod
    async def ingest(
        cls,
        history: ConversationHistory,
        qdrant: QdrantClient,
    ) -> ConversationVectorIngestion:
        """Factory method orchestrates domain-specific stages."""
        pipeline = Pipeline()
        
        # Extract text from conversation
        text = history.message_content[-1].content
        
        # Generate embeddings (using base class helpers)
        dense_stage = await cls._create_dense_embedding_stage(
            text=text,
            model=DenseEmbeddingModel("nomic-embed-text"),
            stage_name=StageName("dense-embedding")
        )
        pipeline = pipeline.append(dense_stage)
        
        # Build domain-specific metadata (type-safe!)
        metadata = ConversationMetadata(
            conversation_id=history.id,
            message_id=history.messages[-1].id,
            timestamp=datetime.now(UTC),
            user_id=history.user_id
        )
        
        # Upsert with typed metadata (Payload accepts Pydantic models)
        upsert_stage = await cls._create_upsert_stage(
            embedding=dense_stage.data,
            payload=metadata.model_dump(),  # Pydantic → dict
            qdrant=qdrant,
            collection="conversation",
            stage_name=StageName("upsert")
        )
        pipeline = pipeline.append(upsert_stage)
        
        return cls(conversation_id=history.id, pipeline=pipeline)
```

**Key insights:**
- Domain types (`ConversationId`, `MessageId`) provide semantic richness
- Factory method orchestrates stages with domain logic
- Metadata is type-safe until the Qdrant boundary (then serialized)
- Pipeline tracks observability across all stages

---

## Composing Qdrant Types

**Qdrant provides excellent Pydantic types—compose them directly, don't wrap them.**

### The Anti-Pattern: Unnecessary Wrappers

**What NOT to do:**

```python
# ❌ Deleted from vector_ingestion.py (commit history)
class SparseVector(BaseModel):
    """Wrapper around Qdrant's SparseVector."""
    indices: list[int]
    values: list[float]
    model_config = ConfigDict(frozen=True)
```

**Problems:**
- Zero added value (no validation, no behavior)
- Creates impedance mismatch (our type ↔ their type)
- Requires conversion everywhere
- Obscures vendor semantics
- More code to maintain

### The Right Pattern: Direct Composition

From [`src/app/domain/vector_ingestion.py:19-20`](../../src/app/domain/vector_ingestion.py):

```python
from qdrant_client.models import Payload, SparseVector, VectorStruct
```

**Use Qdrant's types directly:**

```python
class HybridEmbedding(BaseModel):
    text: str
    dense: list[float]
    sparse: SparseVector | None = None  # Qdrant's type, not ours
```

**Benefits:**
- Zero conversion overhead
- Vendor semantics preserved
- Type safety from composition
- IDE understands Qdrant types
- AI comprehends vendor semantics

### When to Wrap vs Compose: Decision Framework

**Compose vendor types when:**
- ✅ Vendor provides Pydantic models
- ✅ Types are well-designed and semantic
- ✅ No additional validation needed
- ✅ Types represent domain concepts (not implementation details)

**Wrap vendor types when:**
- ✅ Adding domain-specific validation
- ✅ Adding computed properties or methods
- ✅ Vendor type is primitive (str, int, dict)
- ✅ Need semantic meaning (DenseEmbeddingModel vs str)

**Examples from this codebase:**

```python
# ✅ Wrapped: str → DenseEmbeddingModel (adds semantic meaning)
class DenseEmbeddingModel(RootModel[str]):
    root: str = Field(min_length=1, max_length=200)
    model_config = ConfigDict(frozen=True)

# ✅ Composed: Qdrant's SparseVector directly
sparse: SparseVector | None = None

# ✅ Composed: Qdrant's Payload type alias
async def _create_upsert_stage(self, payload: Payload, ...)
```

### Payload: Qdrant's Type for Metadata

```python
# Payload is Qdrant's type alias
from qdrant_client.models import Payload  # type alias for dict[str, Any]

# Use it directly in function signatures
async def _create_upsert_stage(
    self,
    embedding: HybridEmbedding,
    payload: Payload,  # Qdrant's semantic type
    qdrant: QdrantClient,
    ...
) -> SuccessStage | FailedStage:
```

**Why use `Payload` instead of `dict[str, Any]`?**
- Semantic meaning: "this is Qdrant metadata"
- Documents the contract: caller knows this goes to Qdrant
- Type safety: still validated by Qdrant at upsert time
- AI comprehension: understands vendor relationship

---

## Dense Embeddings with Ollama

**Local, privacy-preserving semantic embeddings via Ollama.**

Dense embeddings capture semantic meaning—documents with similar embeddings have similar meaning, even if they use different words.

### Implementation

From [`src/app/domain/vector_ingestion.py:222-267`](../../src/app/domain/vector_ingestion.py):

```python
async def _create_dense_embedding_stage(
    self,
    text: str,
    model: DenseEmbeddingModel,
    stage_name: StageName,
) -> SuccessStage | FailedStage:
    """Generate dense embedding via Ollama.
    
    Uses local Ollama server for privacy-preserving, zero-cost inference.
    """
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
        return FailedStage(...)
```

**Key decisions:**

1. **Ollama over API**: Local inference means:
   - Zero per-request cost
   - Complete privacy (data never leaves your infrastructure)
   - Works offline (air-gapped deployments)
   - Fast iteration during development

2. **Settings-based URL**: No hardcoded hosts
   - Development: `http://localhost:11434`
   - Docker: `http://ollama:11434`
   - Production: Load-balanced Ollama cluster

3. **Model identifier wrapped**: `DenseEmbeddingModel` provides:
   - Type safety (can't mix with `SparseEmbeddingModel`)
   - Validation (non-empty, reasonable length)
   - Semantic meaning (not generic `str`)

### Model Selection

**Common dense embedding models:**

| Model | Dimensions | Speed | Use Case |
|-------|-----------|-------|----------|
| `nomic-embed-text` | 768 | Fast | General-purpose RAG |
| `mxbai-embed-large` | 1024 | Medium | High-quality retrieval |
| `bge-large-en-v1.5` | 1024 | Medium | English-only, accurate |
| `all-minilm-l6-v2` | 384 | Very fast | Low-latency, lower quality |

**Decision criteria:**
- **Use nomic-embed-text** (default): Good balance of speed/quality for most RAG
- **Use mxbai-embed-large**: When accuracy matters more than speed
- **Use all-minilm-l6-v2**: When speed is critical, quality acceptable

---

## Sparse Embeddings with FastEmbed

**Lightweight SPLADE embeddings via ONNX runtime—no PyTorch required.**

Sparse embeddings capture exact keyword matches using learned sparse representations (SPLADE: Sparse Lexical and Expansion Model).

### Why FastEmbed over Transformers

Traditional SPLADE implementations use HuggingFace transformers with full PyTorch, adding ~2GB to your Docker image and significant memory overhead. FastEmbed uses ONNX runtime:

- **10x smaller**: ONNX models ~100MB vs PyTorch ~1GB
- **Faster inference**: Optimized ONNX runtime
- **No CUDA dependency**: CPU inference is acceptable for sparse vectors
- **Lower memory**: No PyTorch tensor overhead

### Implementation

From [`src/app/domain/vector_ingestion.py:275-331`](../../src/app/domain/vector_ingestion.py):

```python
async def _create_sparse_embedding_stage(
    self,
    text: str,
    model: SparseEmbeddingModel,
    stage_name: StageName,
) -> SuccessStage | FailedStage:
    """Generate sparse embedding via FastEmbed SPLADE.
    
    Uses Qdrant's FastEmbed library with SPLADE model (ONNX runtime).
    Avoids heavy transformers/PyTorch dependencies while maintaining quality.
    """
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
        
        return SuccessStage(...)
    except Exception as e:
        return FailedStage(...)
```

**Key insights:**

1. **Single model recommended**: `prithivida/Splade_PP_en_v1`
   - Learned sparse representations (better than BM25)
   - Good balance of sparsity and coverage
   - Well-supported by FastEmbed

2. **Batch processing**: FastEmbed always returns list (even for single input)
   - Extract `sparse_embeddings[0]` for single-text case
   - For bulk ingestion, pass multiple texts at once

3. **Direct composition**: `SparseVector` is Qdrant's type
   - No custom wrapper needed
   - Indices and values preserved as-is

---

## Named Vectors & Point Structure

**Qdrant's named vectors enable hybrid search with explicit vector types.**

A single Qdrant point can store multiple vector representations with different names. This is how hybrid search works—store both dense and sparse in one point, query them together.

### Point Structure

From [`src/app/domain/vector_ingestion.py:367-377`](../../src/app/domain/vector_ingestion.py):

```python
# Named vectors: keys match VectorType enum for hybrid search
vector_dict: dict[str, list[float] | SparseVector] = {
    VectorType.DENSE.value: embedding.dense
}

if embedding.is_hybrid and embedding.sparse:
    vector_dict[VectorType.SPARSE.value] = embedding.sparse

# VectorStruct is Qdrant's union type for single/multi/named vectors
vectors: VectorStruct = vector_dict  # type: ignore[assignment]

point = PointStruct(id=str(uuid4()), vector=vectors, payload=payload)
result = qdrant.upsert(collection_name=collection, points=[point])
```

**Point components:**

1. **ID**: Random UUID
   - No deduplication (create new point per ingestion)
   - Use Qdrant's scroll API to find duplicates if needed
   - For updates: query existing point, delete, then insert

2. **Vector**: Named dict mapping `VectorType` to embeddings
   - `"dense"` → `list[float]` (semantic vector)
   - `"sparse"` → `SparseVector` (keyword vector)
   - Keys are strings, values are union type

3. **Payload**: Domain metadata (Qdrant's `Payload` type)
   - Any JSON-serializable dict
   - Used for filtering and display
   - Can be nested (but keep it flat for filtering performance)

### VectorType Enum

From [`src/app/domain/vector_ingestion.py:30-62`](../../src/app/domain/vector_ingestion.py):

```python
class VectorType(StrEnum):
    """Vector representation types for hybrid search."""
    DENSE = "dense"
    SPARSE = "sparse"
```

**Why StrEnum?**
- Type safety (can't typo "dence" vs "dense")
- JSON-serializable (enum values are strings)
- Matches Qdrant collection schema keys
- Enables exhaustive matching in code

---

## Domain-Specific Ingestion

**Concrete classes own their domain semantics—extend the base with rich types.**

### Pattern: Factory Method Orchestration

Each domain (conversations, documents, graph entities) has unique needs:

**Conversations:**
- Extract message content
- Include conversational context (previous N messages)
- Metadata: ConversationId, MessageId, timestamp, user

**Documents:**
- Chunk text (overlap, max tokens)
- Preserve document structure (headings, sections)
- Metadata: DocumentId, source, author, created_at

**Graph Entities:**
- Summarize entity with relationships
- Include relationship context (connected entities)
- Metadata: EntityId, entity_type, relationship_count

### Example: Document Ingestion (Future Implementation)

```python
class DocumentMetadata(BaseModel):
    """Type-safe metadata for document chunks."""
    document_id: DocumentId
    chunk_id: ChunkId
    chunk_index: int
    source_file: str
    created_at: datetime
    author: str | None = None
    model_config = ConfigDict(frozen=True)


class DocumentVectorIngestion(VectorIngestion):
    """Ingest documents with chunking and metadata."""
    document_id: DocumentId
    collection: str = "documents"
    
    @classmethod
    async def ingest(
        cls,
        document: Document,
        qdrant: QdrantClient,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ) -> DocumentVectorIngestion:
        """Chunk document and create embeddings for each chunk."""
        pipeline = Pipeline()
        
        # Chunk text (domain-specific logic)
        chunks = cls._chunk_text(document.content, chunk_size, chunk_overlap)
        
        for idx, chunk in enumerate(chunks):
            # Generate dense embedding
            dense_stage = await cls._create_dense_embedding_stage(
                text=chunk,
                model=DenseEmbeddingModel("nomic-embed-text"),
                stage_name=StageName(f"dense-chunk-{idx}")
            )
            pipeline = pipeline.append(dense_stage)
            
            # Generate sparse embedding
            sparse_stage = await cls._create_sparse_embedding_stage(
                text=chunk,
                model=SparseEmbeddingModel("prithivida/Splade_PP_en_v1"),
                stage_name=StageName(f"sparse-chunk-{idx}")
            )
            pipeline = pipeline.append(sparse_stage)
            
            # Combine embeddings
            hybrid = HybridEmbedding(
                text=chunk,
                dense=dense_stage.data.dense,
                sparse=sparse_stage.data.sparse
            )
            
            # Domain metadata
            metadata = DocumentMetadata(
                document_id=document.id,
                chunk_id=ChunkId(),  # Generate new ID
                chunk_index=idx,
                source_file=document.source_file,
                created_at=document.created_at,
                author=document.author
            )
            
            # Upsert chunk
            upsert_stage = await cls._create_upsert_stage(
                embedding=hybrid,
                payload=metadata.model_dump(),
                qdrant=qdrant,
                collection="documents",
                stage_name=StageName(f"upsert-chunk-{idx}")
            )
            pipeline = pipeline.append(upsert_stage)
        
        return cls(document_id=document.id, pipeline=pipeline)
    
    @staticmethod
    def _chunk_text(text: str, size: int, overlap: int) -> list[str]:
        """Domain-specific chunking logic."""
        # Implement semantic chunking (preserve sentence boundaries, etc.)
        ...
```

**Key pattern:**
- Base class provides helpers (`_create_dense_embedding_stage`, etc.)
- Concrete class provides orchestration (chunking, metadata, loops)
- Domain types (`DocumentId`, `ChunkId`) provide semantic richness
- Factory method returns frozen instance with completed pipeline

---

## Collection Schema Design

**Define collection schema with named vector configs for hybrid search.**

### Schema Creation

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, SparseVectorParams

client = QdrantClient(url="http://localhost:6333")

# Create collection with named vectors
client.create_collection(
    collection_name="documents",
    vectors_config={
        "dense": VectorParams(
            size=768,  # nomic-embed-text dimension
            distance=Distance.COSINE  # Cosine similarity for semantic search
        ),
        "sparse": SparseVectorParams()  # Sparse vectors don't need size (dynamic)
    }
)
```

**Key decisions:**

1. **Distance metric for dense vectors:**
   - `COSINE`: Normalized similarity (most common for embeddings)
   - `DOT`: Raw dot product (faster, if embeddings are pre-normalized)
   - `EUCLID`: Euclidean distance (rare for embeddings)

2. **Sparse vector config:**
   - No size parameter (sparse vectors have variable dimensions)
   - Qdrant handles indexing automatically

3. **Named vector keys:**
   - Must match your `VectorType` enum values
   - `"dense"` and `"sparse"` are conventional

### Payload Schema

Qdrant doesn't enforce payload schema (NoSQL-style), but you should:

```python
# Create payload index for fast filtering
client.create_payload_index(
    collection_name="documents",
    field_name="document_id",
    field_schema="keyword"  # Exact match filtering
)

client.create_payload_index(
    collection_name="documents",
    field_name="created_at",
    field_schema="datetime"  # Range filtering
)
```

**When to index payload fields:**
- ✅ Frequently used in filters (user_id, document_id)
- ✅ Range queries (timestamps, scores)
- ✅ Keyword fields (status, category)

**When NOT to index:**
- ❌ Rarely queried fields (increases memory)
- ❌ High-cardinality text (full content, descriptions)
- ❌ Nested objects (flatten them instead)

---

## Query Patterns

**Hybrid search queries combine dense and sparse with fusion strategies.**

### Basic Hybrid Query

```python
from qdrant_client import QdrantClient
from qdrant_client.models import QueryRequest, Query, Fusion

client = QdrantClient(url="http://localhost:6333")

# Generate query embeddings (same as ingestion)
query_text = "How do I implement GraphRAG?"
dense_query = ollama_client.embeddings(model="nomic-embed-text", prompt=query_text)["embedding"]
sparse_query = fastembed_model.embed([query_text])[0]

# Hybrid query with RRF fusion
results = client.query_points(
    collection_name="documents",
    query=Query(
        fusion=Fusion.RRF,  # Reciprocal Rank Fusion
        dense=dense_query,
        sparse=sparse_query
    ),
    limit=10,
    with_payload=True  # Include metadata in results
)
```

### Query with Payload Filtering

```python
# Filter by document ID before search
results = client.query_points(
    collection_name="documents",
    query=Query(fusion=Fusion.RRF, dense=dense_query, sparse=sparse_query),
    query_filter={
        "must": [
            {"key": "document_id", "match": {"value": document_id}}
        ]
    },
    limit=10
)
```

### Dense-Only Query (Fallback)

```python
# If sparse generation fails, dense-only is acceptable
results = client.query_points(
    collection_name="documents",
    query=dense_query,  # Just list[float], not Query object
    using="dense",  # Specify named vector
    limit=10
)
```

### Result Structure

```python
for point in results.points:
    print(f"Score: {point.score}")
    print(f"Text: {point.payload['text']}")
    print(f"Metadata: {point.payload}")
```

---

## Decision Framework

### When to Use Dense vs Sparse vs Hybrid

**Use dense-only when:**
- ✅ Semantic similarity is primary goal
- ✅ Sparse generation is expensive/slow
- ✅ Queries are natural language (not keyword-heavy)
- ✅ Proper nouns/acronyms not critical

**Use sparse-only when:**
- ✅ Exact keyword matching required
- ✅ BM25-style retrieval sufficient
- ✅ Dense embeddings too slow/expensive
- ✅ Not worth hybrid infrastructure

**Use hybrid when:**
- ✅ Production RAG system (highest quality)
- ✅ Mix of semantic and keyword queries
- ✅ Proper nouns/acronyms matter
- ✅ Can afford dual embedding generation

### Embedding Model Selection

**Dense models:**
- `nomic-embed-text` (768d): Default choice, good speed/quality balance
- `mxbai-embed-large` (1024d): Higher quality, slower
- `all-minilm-l6-v2` (384d): Fast, lower quality

**Sparse models:**
- `prithivida/Splade_PP_en_v1`: Default and recommended (via FastEmbed)

### Collection Design

**One collection per domain:**
```python
collections = {
    "conversations": "Search conversation history",
    "documents": "RAG over document corpus",
    "graph_entities": "Entity summaries for hybrid RAG"
}
```

**Don't share collections** across domains:
- Different metadata schemas
- Different query patterns
- Different retention policies

---

## Anti-Patterns

### ❌ DON'T Wrap Vendor Types Unnecessarily

**Bad:**
```python
class SparseVector(BaseModel):
    """Our wrapper around Qdrant's SparseVector."""
    indices: list[int]
    values: list[float]
```

**Good:**
```python
from qdrant_client.models import SparseVector  # Use theirs
```

**Why:** Zero added value creates impedance mismatch and obscures semantics.

---

### ❌ DON'T Use Generic Metadata Types

**Bad:**
```python
async def ingest(text: str, metadata: dict[str, Any]):
    ...
```

**Good:**
```python
class DocumentMetadata(BaseModel):
    document_id: DocumentId
    chunk_id: ChunkId
    created_at: datetime

async def ingest(text: str, metadata: DocumentMetadata):
    payload: Payload = metadata.model_dump()
    ...
```

**Why:** Type safety, validation, AI comprehension, IDE support.

---

### ❌ DON'T Generate Embeddings Synchronously in API Handlers

**Bad:**
```python
@app.post("/ingest")
async def ingest_document(doc: Document):
    # Blocks API handler for seconds
    embedding = await generate_embedding(doc.content)
    await qdrant.upsert(...)
    return {"status": "ok"}
```

**Good:**
```python
@app.post("/ingest")
async def ingest_document(doc: Document, background_tasks: BackgroundTasks):
    background_tasks.add_task(ingest_async, doc)
    return {"status": "queued", "document_id": doc.id}

async def ingest_async(doc: Document):
    # Runs in background, doesn't block API
    embedding = await generate_embedding(doc.content)
    await qdrant.upsert(...)
```

**Why:** Embedding generation takes seconds; don't block API response.

---

### ❌ DON'T Ignore Chunking for Long Documents

**Bad:**
```python
# Embed entire 50-page document as single vector
embedding = ollama.embeddings(model="nomic", prompt=document.full_text)
```

**Good:**
```python
# Chunk into 512-token segments with 50-token overlap
chunks = chunk_text(document.full_text, size=512, overlap=50)
for chunk in chunks:
    embedding = ollama.embeddings(model="nomic", prompt=chunk)
    # Store each chunk as separate point
```

**Why:** 
- Embeddings have max context length (typically 512-8192 tokens)
- Smaller chunks improve retrieval precision
- Avoids "lost in the middle" problem

---

### ❌ DON'T Store Large Text in Payload

**Bad:**
```python
payload = {
    "full_document": document.content,  # 100KB text
    "metadata": {...}
}
```

**Good:**
```python
payload = {
    "chunk": chunk_text[:500],  # Just the chunk
    "document_id": document.id,  # Reference to full doc in MinIO/PostgreSQL
    "metadata": {...}
}
```

**Why:** Qdrant payload stored in memory; large payloads degrade performance.

---

### ❌ DON'T Query Without Limits

**Bad:**
```python
results = client.query_points(collection_name="documents", query=embedding)
# Returns ALL matching points (could be thousands)
```

**Good:**
```python
results = client.query_points(
    collection_name="documents",
    query=embedding,
    limit=10  # Top-k results only
)
```

**Why:** Unbounded queries waste bandwidth and degrade performance.

---

### ❌ DON'T Forget Payload Indexes for Filtered Queries

**Bad:**
```python
# Query with filter, no index
results = client.query_points(
    collection_name="documents",
    query=embedding,
    query_filter={"must": [{"key": "user_id", "match": {"value": user_id}}]}
)
# Scans all points, slow!
```

**Good:**
```python
# Create index first
client.create_payload_index(
    collection_name="documents",
    field_name="user_id",
    field_schema="keyword"
)

# Now filter query is fast
results = client.query_points(...)
```

**Why:** Unindexed filters require full collection scan.

---

## See Also

- [Type System](type-system.md) - When to wrap vs compose types
- [Pipeline Pattern](pipeline-pattern.md) - Stage tracking and observability
- [Domain Models](domain-models.md) - Rich aggregates and factories
- [Immutability](immutability.md) - Frozen models and functional updates
- [Infrastructure Systems](../infra/systems.md) - Qdrant architecture and configuration

---

**Next:** Implement domain-specific ingestion (ConversationVectorIngestion, DocumentVectorIngestion) using these patterns.

