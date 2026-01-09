# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link to spec.md]
**Input**: Feature specification from `specs/[###-feature-name]/spec.md`

## Summary

[Brief summary: what this feature adds and why]

## Technical Context

**Platform Stack** (fixed):
- **Language**: Python 3.12+
- **Framework**: FastAPI (async HTTP)
- **Models**: Pydantic (domain models, validation)
- **Observability**: Logfire (tracing, metrics)
- **Testing**: pytest

**Storage** (select what this feature uses):
- [ ] PostgreSQL (relational data via SQLModel)
- [ ] Redis (cache, session state)
- [ ] NATS (event streaming, message queues)
- [ ] Qdrant (vector embeddings, semantic search)
- [ ] Neo4j (knowledge graph, relationships)
- [ ] MinIO (object storage, binary files)

**Performance Goals** (if applicable):
- [e.g., <100ms p95 latency, handle 1000 req/s, process 10k events/sec]

**Constraints** (if applicable):
- [e.g., must run on single node, <2GB memory, 7-year retention required]

## Constitution Check

**Architectural Laws** (must all pass):
- [ ] All domain models will be `frozen=True` (immutable)
- [ ] Outcomes use discriminated unions (no booleans/exceptions for business logic)
- [ ] All primitives wrapped in value objects (UserId not UUID, Amount not float)
- [ ] Smart enums contain behavior (not external if/else branching)
- [ ] Repository pattern for ALL storage (SQL, vector, graph, cache, object)
- [ ] Services orchestrate only (business logic in domain models)
- [ ] Cross-domain composition clean (no circular dependencies)
- [ ] Logfire instrumentation on all operations

**Violations** (if any - must be justified):
- [List any exceptions to above rules with justification]

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── spec.md              # Requirements (WHAT and WHY)
├── plan.md              # Architecture (HOW) - this file
└── tasks.md             # Implementation checklist (DO)
```

### Source Code (repository root)

**Domain-Centric Architecture:**

```text
src/app/
├── domain/
│   └── [context]/              # New domain context for this feature
│       ├── __init__.py
│       ├── value.py            # Value objects (IDs, typed primitives)
│       ├── type.py             # Smart enums with behavior
│       ├── [aggregate].py      # Rich domain models (frozen=True)
│       ├── event.py            # Domain events (if applicable)
│       └── repository.py       # Repository protocol + implementation
├── service/
│   └── [context].py            # Infrastructure adapter (owns clients)
└── api/
    └── [context]/              # HTTP layer (if applicable)
        ├── __init__.py
        └── routes.py

tests/
├── unit/
│   └── [context]/
│       ├── test_[aggregate].py      # Domain model tests
│       └── test_repository.py       # Repository tests
└── integration/
    └── [context]/
        └── test_[context]_service.py  # End-to-end tests
```

**Structure Notes:**
- **Domain context** = business capability boundary (e.g., `payment`, `notification`, `analytics`)
- **Cross-domain imports** = Allowed if dependency is clean (document below)
- **Repository location** = Lives in domain it serves (NOT separate infra/ layer)

## Domain Design

### Value Objects

<!--
  List IDs and typed primitives that need wrapping.
  Reference: docs/architecture/pattern/app.md
-->

- **[DomainId]**: UUID wrapper for aggregate root identity
- **[ConceptValue]**: Typed wrapper for domain concept (e.g., `Amount`, `EmailAddress`)

### Smart Enums

<!--
  List categorical fields that need behavior.
  Reference: docs/architecture/pattern/app.md
-->

- **[StatusEnum]**: [List states, describe behavior methods]
  - Methods: `is_terminal()`, `can_transition_to(target)`

### Domain Events

<!--
  List events this domain emits. Inherits from EventBase.
  Reference: domain/event/base.py
-->

- **[EventName]**: Emitted when [trigger condition]
  - Category: [SECURITY_AUDIT / WORKFLOW_LIFECYCLE / COGNITIVE_PIPELINE]
  - Retention: [7 years / 90 days]

### Repository Requirements

<!--
  Specify storage types needed.
  Reference: docs/architecture/pattern/app-persistence.md
-->

- **Storage Type**: [SQL / Vector / Graph / Cache / Object]
- **Operations**: [get, save, delete, query_by_X, etc.]
- **Instrumentation**: Logfire spans required on all operations

### Cross-Domain Dependencies

<!--
  Document what this domain imports from other domains.
  Ensures no circular dependencies.
-->

- **Imports from [domain_name]**: [What types/concepts and why]
  - Justification: [Why dependency is clean and necessary]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., Mutable model] | [specific need] | [why immutability doesn't work] |
| [e.g., Boolean outcome] | [specific case] | [why discriminated union doesn't work] |
