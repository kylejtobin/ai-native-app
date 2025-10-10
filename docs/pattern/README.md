# Architectural Patterns

Core patterns for building applications using ADT-driven, domain-rich, type-first design.

## Philosophy

**The whole program is data.** Business logic lives in immutable domain models. Types are the contracts. Services orchestrate. Infrastructure is owned by domains.

**Repository pattern is used for ALL storage types** - not just SQL. Every storage operation goes through a repository for observability, testability, and abstraction.

---

## Pattern Files

### Core Patterns

#### 1. **app.md** - Rich Domain Models (Foundation)

The foundation. Domain entities are immutable Pydantic models with business logic.

**Read this first** to understand:
- Why `frozen=True` on all domain models
- Smart enums (behavior on enum types)
- Value objects (typed primitives)
- Discriminated unions (ADT dispatch)
- Business logic in domain methods

**When to read**: Starting any new feature

---

#### 2. **app-service.md** - Domain Services (Orchestration)

Domain services orchestrate multi-step workflows across domains.

**Covers**:
- Services own their infrastructure (get clients from Settings)
- Load → Domain → Save pattern
- Protocol-based dependency injection
- Cross-domain orchestration
- Repository creation and lifecycle

**When to read**: Building workflows that coordinate multiple entities

---

#### 3. **app-persistence.md** - Storage Strategy (Overview)

High-level overview of storage patterns. Repository for all storage types.

**Covers**:
- Why Repository for everything (observability!)
- Storage categories: SQL, vector, memory, graph, object
- Settings as client factory
- Services own infrastructure
- Migration from old patterns

**When to read**: Before designing any persistence layer

---

#### 4. **app-api.md** - Ultra-Thin API Layer

FastAPI routes are minimal adapters between HTTP and domain services.

**Covers**:
- Parse request → delegate to service → return response
- No business logic in routes
- Dependency injection via `app.state`
- Error handling via ADT results
- Request/response contracts

**When to read**: Building HTTP endpoints

---

### Repository Patterns (Storage-Specific)

All storage uses Repository pattern. These guides explain implementation details per storage category:

#### **app-repo.md** - Repository Pattern (Generic)

Generic repository pattern applicable to all storage types.

**Covers**:
- Why Repository (observability, abstraction, testability)
- Generic repository interface
- Logfire integration
- Protocol-based design
- When to use Repository (always!)

**When to read**: Before implementing any storage layer

---

#### **app-repo-sql-store.md** - SQL Store (Postgres)

SQL persistence with SQLModel foundation.

**Covers**:
- SQLModel: Pydantic + SQLAlchemy tables
- Simple mode: SQLModel alone (no translation)
- Complex mode: SQLModel + rich domain model + Repository
- Decision tree: when to separate domain model
- Alembic migrations

**When to read**: Persisting domain aggregates with relational data

---

#### **app-repo-vector-store.md** - Vector Store (Qdrant)

Semantic search operations with observability.

**Covers**:
- Vector repository interface
- Qdrant implementation
- Instrumentation for searches
- Swappable vector providers

**When to read**: Implementing semantic search (will be expanded when building vector domain)

---

#### **app-repo-memory-store.md** - Memory Store (Redis)

Cache and queue operations.

**Covers**:
- Cache repository (get/set/expire)
- Queue repository (push/pop/claim)
- Redis implementation
- Instrumentation for cache hits/misses

**When to read**: Implementing caching or queuing (will be expanded when building message domain)

---

#### **app-repo-graph-store.md** - Graph Store (Neo4j)

Graph traversal with query language abstraction.

**Covers**:
- Graph repository interface
- Neo4j implementation (hides Cypher)
- Relationship queries
- Instrumentation for graph operations

**When to read**: Implementing graph operations (will be expanded when refactoring graph domain)

---

#### **app-repo-object-store.md** - Object Store (MinIO)

Binary blob storage (S3-compatible).

**Covers**:
- Object repository interface
- MinIO implementation
- Metadata handling
- Instrumentation for storage operations

**When to read**: Implementing file/blob storage (will be expanded when refactoring object domain)

---

## Pattern Application Order

When building a new feature:

1. **Define domain models** (`app.md`)
   - Value objects, smart enums, discriminated unions
   - Business logic methods

2. **Choose storage category** (`app-persistence.md`)
   - SQL? Vector? Cache? Graph? Object?

3. **Implement repository** (`app-repo-*.md`)
   - Generic pattern + storage-specific guide
   - Always with Logfire instrumentation

4. **Build domain service** (`app-service.md`)
   - Service owns infrastructure
   - Creates repositories per request

5. **Add HTTP endpoint** (`app-api.md`)
   - Parse → delegate → return

---

## Key Principles

1. **Repository for ALL storage** - Observability is not optional for bank-grade systems
2. **Repository abstracts access pattern, not types** - Semantic methods + Logfire spans
3. **Compose vendor types directly** - Qdrant's Payload, Pydantic AI's ModelMessage
4. **Translate only when needed** - SQL requires flattening; Qdrant doesn't need wrappers
5. **SQLModel is SQL foundation** - Pydantic everywhere!
6. **Services own infrastructure** - Get clients from Settings, create repositories
7. **Domains own repositories** - No separate infra/ layer
8. **Always instrumented** - Every storage operation wrapped in Logfire span
9. **Protocol-based** - Depend on interface, not concrete implementation

**Critical distinction:** Repository normalizes HOW you access storage (semantic operations, observability), NOT WHAT types you use (compose vendor types directly).

---

## Migration from Old Patterns

If you see:
- `infra/service.py` - **Delete**, move to `domain/X/repository.py`
- Direct client calls without repository - **Wrap in repository**
- Protocol files duplicating types - **Delete**, types are contracts
- Boolean returns instead of ADTs - **Refactor to discriminated unions**

**Goal**: Domain owns storage, repository provides observability boundary.

---

## Quick Reference

| Need to... | Read... |
|------------|---------|
| Start any feature | `app.md` |
| Orchestrate workflow | `app-service.md` |
| Choose storage | `app-persistence.md` |
| Implement SQL persistence | `app-repo-sql-store.md` |
| Implement vector search | `app-repo-vector-store.md` |
| Implement caching | `app-repo-memory-store.md` |
| Understand repository generically | `app-repo.md` |
| Build HTTP endpoint | `app-api.md` |

---

## Related Documentation

- **CLAUDE.md** (repo root) - Project overview and development commands
- **docs/architecture/ARCHITECTURE_OVERVIEW.md** - System architecture
- **docs/architecture/infra-svc/overview.md** - Why domains own infrastructure
- **domain/security/ARCHITECTURE.md** - Security domain deep dive
