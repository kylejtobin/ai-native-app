# Persistence Pattern (Storage Strategy)

> **Repository pattern for ALL storage types. Provides observability, abstraction, and testability.**

## Overview

All storage operations use the **Repository pattern** - not just SQL. Repository provides:

1. **Observability boundary** - Logfire instrumentation on every operation
2. **Semantic abstraction** - Domain operations, not infrastructure details
3. **Swappable implementations** - Change vendors without domain changes
4. **Testability** - Mock repository, not infrastructure
5. **Translation layer** - When storage format ≠ domain format

**Key principle**: Repository abstracts storage CATEGORY (SQL, vector, memory, graph, object), not vendor.

---

## Storage Categories

All storage uses Repository pattern. Choose category by data characteristics:

| Storage Type | Use For | Current | Future |
|--------------|---------|---------|--------|
| **SQL Store** | Aggregates, relations, ACID | Postgres (SQLModel) | MySQL |
| **Vector Store** | Semantic search | Qdrant | Pinecone, Weaviate |
| **Memory Store** | Cache, queues | Redis | Memcached, Valkey |
| **Graph Store** | Relationships, traversal | Neo4j | ArangoDB |
| **Object Store** | Binary blobs (files) | MinIO | Azure Blob, GCS |

---

## Why Repository for Everything?

### For a Bank-Grade System

**Repository is not optional** because it provides:

1. **Audit trail** - Every storage operation logged via Logfire
2. **Performance analysis** - "Which queries are slow?" queryable
3. **Security monitoring** - "Who accessed what?" auditable
4. **Failure tracking** - "What's the error rate?" measurable
5. **Testing** - Mock repositories, not infrastructure

**Without Repository:** Storage calls scattered, inconsistent instrumentation, hard to audit.

**With Repository:** Single boundary, consistent observability, testable.

### What Repository Normalizes

**Repository normalizes ACCESS, not TYPES:**

```python
# ❌ Without Repository
async def store(client: QdrantClient, ...):
    client.upsert(...)  # No instrumentation, inconsistent patterns

# ✅ With Repository (composing vendor types)
from qdrant_client.models import Payload, UpdateResult

async def store(repo: QdrantVectorRepository, payload: Payload):  # Qdrant's type
    return await repo.upsert(...)  # Instrumented, semantic, testable
```

Repository provides semantic operations and Logfire spans, while vendor types (Qdrant's `Payload`, Pydantic AI's `ModelMessage`) flow through unchanged.

---

## SQL Store

**Foundation:** SQLModel (Pydantic + SQLAlchemy tables)

**Two modes:**

### Simple: SQLModel Alone
When aggregate is primarily data:
```python
from sqlmodel import SQLModel, Field

class TokenRevocation(SQLModel, table=True):
    """SQLModel IS the domain model."""
    token_id: UUID = Field(primary_key=True)
    subject_id: UUID = Field(index=True)
    revoked_at: datetime

    # Still use repository for observability
class TokenRevocationRepository:
    async def get(self, token_id: UUID) -> TokenRevocation | None:
        with logfire.span("repo.token_revocation.get"):
            ...
```

### Complex: Domain Model + Repository
When aggregate has business logic:
```python
# Separate domain model with rich value objects
class User(BaseModel):
    model_config = {"frozen": True}
    email: EmailAddress  # Value object

    def authenticate(self, verification_result) -> UserAuthResult:
        """Business logic in domain."""
        ...

# Repository translates between domain and storage
class UserRepository:
    def to_domain(self, user_row: UserTable) -> User:
        return User(email=EmailAddress(user_row.email_local, user_row.email_domain))
```

**See:** `app-repo-sql-store.md` for full SQL pattern

---

## Vector Store

**Semantic search operations with observability. Composes vendor types directly.**

```python
from qdrant_client.models import Payload, UpdateResult, ScoredPoint

class QdrantVectorRepository:
    async def upsert(
        self,
        collection: str,
        embedding: HybridEmbedding,
        payload: Payload,  # ← Qdrant's type
    ) -> UpdateResult:  # ← Qdrant's type
        with logfire.span("repo.vector.upsert", collection=collection):
            # Use Qdrant types throughout - no translation
            point = PointStruct(
                id=str(uuid4()),
                vector=embedding.dense,
                payload=payload  # Qdrant's Payload flows through
            )
            return self.client.upsert(...)  # Qdrant's UpdateResult
    
    async def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int
    ) -> list[ScoredPoint]:  # ← Qdrant's type
        with logfire.span(
            "repo.vector.search",
            collection=collection,
            dimensions=len(query_vector)
        ):
            return self.client.search(...)  # Qdrant's ScoredPoint list
```

**Benefits:**
- ✅ Instrument all vector operations
- ✅ Track slow searches
- ✅ Semantic operations (`upsert`, `search`)
- ✅ Test with fake vector repository
- ✅ **No wrapper types** - compose Qdrant's Pydantic types directly
- ✅ **Zero conversion overhead** - types flow through unchanged

**See:** `app-repo-vector-store.md`

---

## Memory Store

**Cache and queue operations with observability.**

```python
class QueueRepository:
    async def push(self, queue: QueueName, message: Message) -> None:
        with logfire.span("repo.queue.push", queue=queue.value):
            await self.client.rpush(queue.value, message.model_dump_json())

    async def pop(self, queue: QueueName) -> Message | None:
        with logfire.span("repo.queue.pop", queue=queue.value):
            data = await self.client.lpop(queue.value)
            return Message.model_validate_json(data) if data else None
```

**Benefits:**
- ✅ Audit all cache/queue operations
- ✅ Track error rates
- ✅ Swap Redis → Valkey seamlessly
- ✅ Test without Redis

**See:** `app-repo-memory-store.md`

---

## Graph Store

**Graph traversal with query language abstraction.**

```python
class GraphRepository:
    async def find_related(
        self,
        node: NodeId,
        relationship: RelationType,
        depth: int
    ) -> list[Node]:
        with logfire.span("repo.graph.traverse", depth=depth):
            # Cypher hidden from domain
            query = "MATCH (n)-[r:REL*1..%d]->(m) ..." % depth
            results = await self.driver.execute_query(query)
            return [self._to_domain(r) for r in results]
```

**Benefits:**
- ✅ Domain doesn't know Cypher
- ✅ Instrument all graph queries
- ✅ Swap Neo4j → ArangoDB
- ✅ Test without graph database

**See:** `app-repo-graph-store.md`

---

## Object Store

**Binary blob storage with semantic operations.**

```python
class ObjectRepository:
    async def store(
        self,
        key: ObjectKey,
        data: bytes,
        metadata: ObjectMetadata
    ) -> StoredObject:
        with logfire.span("repo.object.store", size=len(data)):
            self.client.put_object(...)
            return StoredObject(key=key, size=len(data))
```

**Benefits:**
- ✅ Audit all object operations
- ✅ Track storage usage
- ✅ Swap MinIO → Azure Blob
- ✅ Test without object store

**See:** `app-repo-object-store.md`

---

## Settings: Client Factory

Settings provides configured clients to repositories:

```python
# domain/settings.py
class Settings(BaseSettings):
    POSTGRES_USER: str
    POSTGRES_PASSWORD: SecretStr
    QDRANT_HOST: str
    REDIS_HOST: str

    def postgres_engine(self):
        """SQL database engine."""
        from sqlalchemy.ext.asyncio import create_async_engine
        url = f"postgresql+asyncpg://{self.POSTGRES_USER}:..."
        return create_async_engine(url)

    def qdrant_client(self):
        """Vector database client."""
        from qdrant_client import QdrantClient
        return QdrantClient(host=self.QDRANT_HOST, port=self.QDRANT_PORT)

    def redis_client(self):
        """Cache/queue client."""
        from redis.asyncio import Redis
        return Redis(host=self.REDIS_HOST, ...)
```

---

## Service Orchestration

Services own infrastructure, create repositories:

```python
# service/auth.py
class AuthService:
    def __init__(self, settings: Settings, clock: ClockService):
        # Own DB infrastructure
        self.engine = settings.postgres_engine()
        self.session_factory = async_sessionmaker(self.engine)
        self.clock = clock

    async def login_user(self, email, password) -> LoginResult:
        async with self.session_factory() as session:
            repo = UserRepository(session)  # Create repository
            result = await self.auth_service.login_user(
                email, password, repo, self.clock, ...
            )
            await session.commit()
            return result
```

**For non-SQL:**
```python
class VectorService:
    def __init__(self, settings: Settings):
        self.qdrant = settings.qdrant_client()

    async def search(self, query: str) -> list[Document]:
        repo = QdrantVectorRepository(self.qdrant)  # Repository wraps client
        return await repo.search(...)
```

---

## Anti-Patterns

**❌ Skip Repository for "simple" operations:**
```python
# WRONG - No observability, hard to test
async def cache_get(key: str):
    redis = settings.redis_client()
    return await redis.get(key)  # ❌ Not instrumented
```

**✅ Always use Repository:**
```python
# CORRECT - Instrumented, testable
class CacheRepository:
    async def get(self, key: CacheKey) -> bytes | None:
        with logfire.span("repo.cache.get", key=key.value):
            return await self.client.get(key.value)

async def cache_get(key: CacheKey, repo: CacheRepository):
    return await repo.get(key)  # ✅ Instrumented, testable
```

**❌ Separate infra/ layer:**
```python
# WRONG - Unnecessary middleman
infra/qdrant.py  # "Service" wrapping QdrantClient
service/vector.py  # "Service" calling infra
domain/vector.py  # Anemic models
```

**✅ Domains own repositories:**
```python
# CORRECT - Domain owns its repository
domain/vector/
  operations.py  # Domain models
  repository.py  # QdrantVectorRepository
```

---

## Migration Strategy

When moving from old patterns:

1. **Create repository per storage category**
   - SQL → `domain/database/repository.py`
   - Vector → `domain/vector/repository.py`
   - Queue → `domain/message/repository.py`

2. **Add client factory to Settings**
   ```python
   def qdrant_client(self): ...
   ```

3. **Wrap operations in Logfire spans**
   ```python
   with logfire.span("repo.vector.search"):
       ...
   ```

4. **Update service to use repository**
   ```python
   repo = VectorRepository(settings.qdrant_client())
   await repo.search(...)
   ```

5. **Delete old infra/ code**
   - Once all storage uses repositories

---

## Key Principles

1. **Repository for ALL storage** - Not just SQL, for observability
2. **Repository abstracts access pattern** - Semantic methods + Logfire spans
3. **Compose vendor types directly** - Qdrant's Payload, Pydantic AI's ModelMessage
4. **Translate only when needed** - SQL requires flattening; Qdrant doesn't need wrappers
5. **Settings provides clients** - Client factory methods
6. **Services own infrastructure** - Create sessions/repositories per request
7. **Domains own repositories** - In `domain/database/`, `domain/vector/`, etc.
8. **Always instrumented** - Every operation wrapped in Logfire span
9. **Protocol-based** - Domain depends on interface, not concrete vendor

**Critical distinction:** Repository normalizes HOW you access storage (semantic operations, observability), NOT WHAT types you use (compose vendor types directly).

---

## Related Patterns

- **app-repo.md** - Generic repository pattern deep dive
- **app-repo-sql-store.md** - SQL with SQLModel
- **app-repo-vector-store.md** - Vector search
- **app-repo-memory-store.md** - Cache/queue
- **app-repo-graph-store.md** - Graph traversal
- **app-repo-object-store.md** - Binary storage
- **app-service.md** - How services orchestrate repositories
