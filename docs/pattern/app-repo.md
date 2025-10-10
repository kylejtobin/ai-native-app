# Repository Pattern (Generic)

> **Repository: Semantic abstraction layer for storage operations with built-in observability**

## Overview

Repository pattern provides a semantic interface between domain code and storage infrastructure. It's not just for SQL - it's our **observability and abstraction boundary** for ALL storage types.

**Key principle**: Every storage operation goes through a repository for consistent instrumentation, testing, and abstraction.

**Critical distinction**: Repository abstracts the **access pattern** (semantic methods, Logfire spans), NOT the types. When vendors provide excellent Pydantic types (Qdrant, Pydantic AI), compose them directly. Repository normalizes HOW you access storage, not WHAT types you use.

---

## Why Repository Pattern?

### 1. **Observability Boundary**

Repository is the SINGLE point to instrument all storage operations:

```python
class UserRepository:
    async def get_by_email(self, email: EmailAddress) -> User | None:
        with logfire.span(
            "repo.user.get_by_email",
            email_domain=email.domain,
        ) as span:
            result = await self._query(email)
            span.set_attribute("found", result is not None)
            return result
```

**With Logfire:**
- Query all storage operations: "Show me all repo operations"
- Find slow operations: "Which queries took >100ms?"
- Track failures: "What percentage of Redis ops failed?"
- See patterns: "Which collections are searched most?"

**Without Repository:**
- Storage calls scattered throughout code
- Inconsistent instrumentation
- Hard to query across operations

### 2. **Semantic Abstraction**

Repository provides domain-meaningful operations:

```python
# ✅ Semantic operation
await user_repo.get_by_email(email)

# ❌ Infrastructure details leaked
await redis.get(f"user:email:{email.local_part}@{email.domain}")
```

Domain code thinks in terms of **what** (get user by email), not **how** (Redis key pattern).

**Repository normalizes access, not types:**

```python
# ✅ Repository with vendor types composed directly
from qdrant_client.models import Payload, PointStruct, UpdateResult

class QdrantVectorRepository:
    async def upsert(
        self,
        collection: str,
        embedding: HybridEmbedding,
        payload: Payload,  # ← Qdrant's type, not wrapped!
    ) -> UpdateResult:  # ← Qdrant's type, not wrapped!
        with logfire.span("repo.vector.upsert", collection=collection):
            # Use Qdrant types directly throughout
            point = PointStruct(
                id=str(uuid4()),
                vector=embedding.dense,
                payload=payload  # Qdrant's Payload
            )
            return self.client.upsert(...)  # Returns Qdrant's UpdateResult
```

The repository provides semantic operations (`upsert`) and observability (`logfire.span`), while Qdrant's types flow through unchanged.

### 3. **Swappable Implementations**

Repository abstracts the storage category:

```python
class VectorRepository(Protocol):
    async def search(self, collection: CollectionName, query: Vector) -> list[Result]:
        ...

# Qdrant implementation
class QdrantVectorRepository:
    def __init__(self, client: QdrantClient): ...

# Pinecone implementation (future)
class PineconeVectorRepository:
    def __init__(self, client: PineconeClient): ...
```

Domain depends on `VectorRepository` protocol, not concrete Qdrant/Pinecone.

### 4. **Testability**

Mock at repository level, not infrastructure:

```python
# Test with fake repository
class FakeUserRepository:
    def __init__(self, users: dict[EmailAddress, User]):
        self.users = users

    async def get_by_email(self, email: EmailAddress) -> User | None:
        return self.users.get(email)

# Test domain without database
auth = AuthService()
fake_repo = FakeUserRepository({test_email: test_user})
result = await auth.login_user(email, password, fake_repo, clock, crypto)
```

No Docker, no Postgres, no Redis - just pure domain logic testing.

### 5. **Translation Layer (When Needed)**

Repository provides translation ONLY when storage format differs from domain format:

**When translation IS needed (SQL flattening):**
```python
class UserRepository:
    def to_domain(self, user_row: UserTable, cred_row: CredentialTable) -> User:
        """Storage → Domain (reconstruct value objects from flat SQL)."""
        return User(
            user_id=UserId(user_row.user_id),
            email=EmailAddress(user_row.email_local, user_row.email_domain),  # Reconstruct
            credential=UserCredential(...)
        )

    def to_storage(self, user: User) -> UserTable:
        """Domain → Storage (flatten value objects to SQL columns)."""
        return UserTable(
            email_local=user.email.local_part,  # Flatten
            email_domain=user.email.domain,
        )
```

**When translation is NOT needed (vendor provides Pydantic types):**
```python
class QdrantVectorRepository:
    async def upsert(
        self,
        embedding: HybridEmbedding,
        payload: Payload,  # ← Already Qdrant's type
    ) -> UpdateResult:  # ← Already Qdrant's type
        # No translation! Types flow through directly.
        point = PointStruct(...)
        return self.client.upsert(...)
```

**Rule:** Translate only when storage format ≠ domain format. Don't wrap well-designed vendor types.

---

## The Generic Pattern

### Repository Interface

```python
from typing import Protocol
from pydantic import BaseModel

class Repository(Protocol[T]):
    """Generic repository for aggregate T."""

    async def get(self, id: AggregateId) -> T | None:
        """Get by ID."""
        ...

    async def save(self, aggregate: T) -> T:
        """Save (create or update)."""
        ...

    async def delete(self, id: AggregateId) -> bool:
        """Delete by ID."""
        ...
```

### Repository Implementation

```python
import logfire

class ConcreteRepository:
    """Repository implementation with observability."""

    def __init__(self, client: StorageClient):
        self.client = client

    async def get(self, id: AggregateId) -> Aggregate | None:
        with logfire.span(
            "repo.aggregate.get",
            aggregate_type="Aggregate",
            id=str(id.value)
        ) as span:
            try:
                # Storage operation
                raw = await self.client.fetch(id)

                if not raw:
                    span.set_attribute("found", False)
                    return None

                # Translation
                domain = self.to_domain(raw)
                span.set_attribute("found", True)
                return domain

            except Exception as e:
                span.record_exception(e)
                logfire.error("repo.get_failed", error=str(e))
                raise

    async def save(self, aggregate: Aggregate) -> Aggregate:
        with logfire.span(
            "repo.aggregate.save",
            aggregate_type="Aggregate",
            id=str(aggregate.id.value)
        ) as span:
            try:
                # Translation
                storage_model = self.to_storage(aggregate)

                # Storage operation
                await self.client.upsert(storage_model)

                span.set_attribute("success", True)
                return aggregate

            except Exception as e:
                span.record_exception(e)
                logfire.error("repo.save_failed", error=str(e))
                raise

    def to_domain(self, raw) -> Aggregate:
        """Storage → Domain."""
        # Implementation specific
        ...

    def to_storage(self, aggregate: Aggregate):
        """Domain → Storage."""
        # Implementation specific
        ...
```

---

## Storage Categories

Repository pattern applies to ALL storage types:

### **SQL Store** (`app-repo-sql-store.md`)
- Complex aggregates (User, Module, Token)
- SQLModel as foundation (Pydantic tables)
- Optional rich domain model when business logic warrants
- Alembic migrations

### **Vector Store** (`app-repo-vector-store.md`)
- Semantic search operations
- Current: Qdrant
- Future: Pinecone, Weaviate

### **Memory Store** (`app-repo-memory-store.md`)
- Cache operations (get, set, expire)
- Queue operations (push, pop, claim)
- Current: Redis
- Future: Memcached, Valkey

### **Graph Store** (`app-repo-graph-store.md`)
- Graph traversal operations
- Relationship queries
- Current: Neo4j
- Future: ArangoDB

### **Object Store** (`app-repo-object-store.md`)
- Binary object storage
- Current: MinIO (S3 compatible)
- Future: Azure Blob, GCS

---

## When to Use Repository

**Use Repository for:**
- ✅ All production storage operations
- ✅ When you need observability (always!)
- ✅ When you want testability
- ✅ When storage might change (Qdrant → Pinecone)
- ✅ When domain model ≠ storage model

**Skip Repository for:**
- ❌ Never (for production code)
- ⚠️ Maybe for scripts/migrations (but you lose observability)

**For a bank-grade system:** Repository is not optional. Observability and testability are requirements.

---

## Logfire Integration

Repository + Logfire gives us full storage observability:

**Query slow operations:**
```python
# Find all vector searches >100ms
logfire.query("""
    repo.vector.search
    WHERE duration > 100ms
""")
```

**Track failure rates:**
```python
# Redis operation success rate
logfire.query("""
    repo.memory.*
    GROUP BY success
""")
```

**Audit access:**
```python
# Who accessed what
logfire.query("""
    repo.*.get
    SELECT subject_id, aggregate_id, timestamp
""")
```

---

## Key Principles

1. **Repository per storage category** - Not per vendor (vector store, not "Qdrant repo")
2. **Semantic operations** - Domain-meaningful method names
3. **Always instrumented** - Every operation wrapped in Logfire span
4. **Protocol-based** - Domain depends on interface, not concrete implementation
5. **Compose vendor types** - Use Qdrant's Payload, Pydantic AI's ModelMessage directly
6. **Translate only when needed** - SQL requires flattening; Qdrant doesn't need wrappers
7. **Testable** - Easy to mock for unit tests

**Remember:** Repository normalizes HOW you access storage (semantic methods, Logfire spans), not WHAT types you use (compose vendor types directly).

---

## Anti-Patterns

### ❌ Wrapping Well-Designed Vendor Types

```python
# WRONG - Unnecessary wrapper
class OurPayload(BaseModel):
    data: dict[str, Any]
    
class QdrantVectorRepository:
    async def upsert(self, payload: OurPayload):
        # Now have to convert
        qdrant_payload = Payload(**payload.data)
        ...
```

**Fix:** Use Qdrant's `Payload` directly—it's already an excellent Pydantic model.

### ❌ Skipping Repository for "Simple" Operations

```python
# WRONG - No observability
async def store_vector(client: QdrantClient, ...):
    client.upsert(...)  # Not instrumented, hard to test
```

**Fix:** Always use repository for consistent observability and testing.

### ❌ Translation When Not Needed

```python
# WRONG - Translating already-good types
class QdrantVectorRepository:
    def _to_domain(self, scored_point: ScoredPoint) -> OurScoredPoint:
        # Recreating Qdrant's type for no reason
        return OurScoredPoint(id=scored_point.id, score=scored_point.score)
```

**Fix:** Return `ScoredPoint` directly—it's already Pydantic.

---

## Related Patterns

- **app-repo-sql-store.md** - SQL persistence with SQLModel
- **app-repo-vector-store.md** - Vector search operations
- **app-repo-memory-store.md** - Cache and queue operations
- **app-persistence.md** - Storage strategy overview
- **app-service.md** - How services use repositories
