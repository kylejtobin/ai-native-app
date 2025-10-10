# Vector Store Repository Pattern

> **Semantic search operations with observability. Composes vendor types directly.**

## Overview

Vector stores handle embedding-based semantic search. Repository provides observability boundary and abstracts the specific vector database.

**Critical principle:** Repository normalizes access patterns (semantic methods, Logfire spans) while composing vendor types directly. Qdrant provides excellent Pydantic types—use them, don't wrap them.

**Current implementation:** Qdrant
**Future options:** Pinecone, Weaviate, Milvus

---

## Repository Interface

```python
from typing import Protocol
from qdrant_client.models import Payload, UpdateResult, ScoredPoint

class VectorRepository(Protocol):
    async def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int,
        filter: Payload | None = None
    ) -> list[ScoredPoint]:  # ← Qdrant's type
        """Semantic search."""
        ...
    
    async def upsert(
        self,
        collection: str,
        embedding: HybridEmbedding,
        payload: Payload  # ← Qdrant's type
    ) -> UpdateResult:  # ← Qdrant's type
        """Insert or update with hybrid vectors."""
        ...
```

**Key: Protocol uses vendor types.** No translation needed when vendor provides Pydantic models.

---

## Qdrant Implementation

```python
import logfire
from uuid import uuid4
from qdrant_client import QdrantClient
from qdrant_client.models import Payload, PointStruct, UpdateResult, ScoredPoint, VectorStruct

class QdrantVectorRepository:
    """Repository normalizes access, composes Qdrant types directly."""
    
    def __init__(self, client: QdrantClient):
        self.client = client
    
    async def upsert(
        self,
        collection: str,
        embedding: HybridEmbedding,
        payload: Payload,  # ← Qdrant's type (already Pydantic!)
    ) -> UpdateResult:  # ← Qdrant's type
        with logfire.span(
            "repo.vector.upsert",
            collection=collection,
            is_hybrid=embedding.is_hybrid
        ):
            # Use Qdrant types throughout - no translation needed
            vector_dict: dict[str, list[float] | SparseVector] = {
                VectorType.DENSE.value: embedding.dense
            }
            
            if embedding.is_hybrid and embedding.sparse:
                vector_dict[VectorType.SPARSE.value] = embedding.sparse
            
            vectors: VectorStruct = vector_dict  # type: ignore
            
            point = PointStruct(
                id=str(uuid4()),
                vector=vectors,
                payload=payload  # Qdrant's Payload flows through
            )
            
            return self.client.upsert(
                collection_name=collection,
                points=[point]
            )  # Returns Qdrant's UpdateResult
    
    async def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int,
        filter: Payload | None = None
    ) -> list[ScoredPoint]:  # ← Qdrant's type
        with logfire.span(
            "repo.vector.search",
            collection=collection,
            dimensions=len(query_vector),
            limit=limit
        ) as span:
            results = self.client.search(
                collection_name=collection,
                query_vector=query_vector,
                query_filter=filter,
                limit=limit
            )
            span.set_attribute("results_count", len(results))
            return results  # Qdrant's ScoredPoint list - no translation
```

**No wrapper types. No translation layer. Qdrant's Pydantic types flow through unchanged.**

The repository provides:
- ✅ Semantic operations (`upsert`, `search`)
- ✅ Consistent Logfire instrumentation
- ✅ Swappable implementations (protocol-based)

While preserving:
- ✅ Qdrant's excellent type system
- ✅ Zero conversion overhead
- ✅ Direct access to vendor features

---

## Related Patterns

- **app-repo.md** - Generic repository pattern
- **app-persistence.md** - Storage strategy overview

---

*This file will be expanded when implementing vector domain.*
