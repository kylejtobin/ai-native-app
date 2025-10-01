# Application Documentation Guide

**How to navigate the application architecture effectively**

The application docs are organized by **architectural pattern** (types, models, services), not by learning path. This matches how the architecture is structured and makes them excellent reference material. But real development tasks often span multiple patterns.

This guide helps you traverse the documentation based on **what you're trying to accomplish**.

---

## The Core Documents

Each document covers one architectural pattern:

| Document | What It Covers | When To Read It |
|----------|----------------|-----------------|
| **[type-system.md](type-system.md)** | Smart enums, RootModel wrappers, semantic types, discriminated unions | Creating domain types |
| **[domain-models.md](domain-models.md)** | Aggregates, rich behavior, factories, domain primitives | Building domain logic |
| **[immutability.md](immutability.md)** | Frozen models, functional updates | Understanding state management |
| **[pipeline-pattern.md](pipeline-pattern.md)** | Multi-stage transformations, observability | Tracking complex workflows |
| **[service-patterns.md](service-patterns.md)** | Thin orchestration, boundaries | Building services |
| **[data-flow.md](data-flow.md)** | Explicit transformations, traceability | Understanding flow |
| **[llm-integration.md](llm-integration.md)** | Pydantic AI, structured outputs | Integrating LLMs |
| **[conversation-system.md](conversation-system.md)** | Complete system architecture | Understanding the full flow |
| **[testing.md](testing.md)** | What NOT to test, efficiency | Writing tests |

---

## Common Scenarios: Where to Start

### "I want to add a new domain model"

**Critical first question:** Is this an **aggregate** (business entity with identity) or a **domain primitive** (reusable abstraction)?

**If it's an aggregate (e.g., Order, User, Conversation):**

**Learning path:**
1. Read [type-system.md](type-system.md) → Understand semantic types
   - See "RootModel: Wrapping Primitives with Type Safety"
   - See "Smart Enums: Business Logic in Constants"
2. Read [domain-models.md](domain-models.md) → Understand rich models
   - See "The Aggregate Root Pattern"
   - See "Factory Methods: Smart Construction"
3. Read [immutability.md](immutability.md) → Understand frozen models
   - See "The Core Pattern: frozen=True"
   - See "Functional Updates with model_copy"

**Then:** Look at `src/app/domain/conversation.py` for a complete aggregate example.

**Key principle:** Business logic lives in models, not services. Your model should know its own rules.

**If it's a domain primitive (e.g., Pipeline, Money, DateRange):**

See ["I want to track multi-stage transformations"](#i-want-to-track-multi-stage-transformations) below for the Pipeline example, or read [domain-models.md](domain-models.md) for the distinction between aggregates and primitives.

### "I want to add business logic"

**Critical decision point:** WHERE does this logic belong?

1. **If it's about one entity** (e.g., "can this user do X?")
   - Put it in the domain model as a method
   - Read [domain-models.md](domain-models.md) "Rich Behavior Methods"
   
2. **If it coordinates multiple entities** (e.g., "transfer funds between accounts")
   - Still domain model! Create a method on the aggregate root
   - Read [domain-models.md](domain-models.md) "The Aggregate Root Pattern"
   
3. **If it's pure orchestration** (load → call domain → persist)
   - Service layer, but NO business logic
   - Read [service-patterns.md](service-patterns.md) "The Four Responsibilities"

**Most common mistake:** Putting business logic in services. DON'T.

### "I want to integrate a new LLM provider"

**Integration path:**
1. Read [llm-integration.md](llm-integration.md) → Understand patterns
   - See "Pydantic AI as Type System Extension"
   - See "Multi-Provider Support"
2. Read [conversation-system.md](conversation-system.md) → Understand system
   - See "Model Catalog: Configuration Over Code"
   - See "Model Pool: Connection Caching Strategy"

**Implementation steps:**
1. Add provider to `domain/model_metadata.json`
2. Add API key to `secrets/api/provider-name`
3. Run `make config` to regenerate
4. Model pool automatically detects and creates clients

**Key principle:** No code changes needed. Configuration drives everything.

### "I'm getting type errors"

**Debugging path:**
1. Start with [type-system.md](type-system.md)
   - Check "Smart Enums" if enum-related
   - Check "RootModel" if UUID/ID-related
   - Check "Computed Properties" if property access
2. Check [immutability.md](immutability.md)
   - Are you trying to mutate a frozen model?
   - See "Common Patterns" for `model_copy()`

**Common issues:**
- Trying to mutate frozen model → Use `model_copy(update={...})`
- Wrong enum value → Check `domain_type.py` for valid values
- UUID as string → Wrap in `ConversationId()` or `MessageId()`
- Type mismatch → Check if you're using `Any` where you shouldn't

### "I want to add a new API endpoint"

**Implementation path:**
1. Read [service-patterns.md](service-patterns.md) → Understand boundaries
   - See "The Four Responsibilities"
   - See "API Layer: Thin HTTP Wrapper"
2. Read [domain-models.md](domain-models.md) → Implement domain logic
3. Read [data-flow.md](data-flow.md) → Understand transformation pipeline

**The pattern:**
```python
# 1. Define request/response contracts (api/contracts/)
class MyRequest(BaseModel):
    field: str

# 2. Implement domain logic (domain/)
class MyAggregate(BaseModel):
    def do_thing(self) -> MyAggregate:
        # Business logic here
        return self.model_copy(update={...})

# 3. Orchestrate in API (api/routers/)
@router.post("/thing")
async def do_thing(request: MyRequest) -> MyResponse:
    # Load domain
    aggregate = await MyAggregate.load(...)
    
    # Call domain method
    updated = await aggregate.do_thing()
    
    # Persist
    await updated.save(...)
    
    # Return
    return MyResponse.from_aggregate(updated)
```

### "I want to understand how it all fits together"

**Complete learning path (in order):**

1. Start with [type-system.md](type-system.md) → Foundation
   - Types are not just validators, they're documentation
   - Smart enums carry business rules
   - RootModel wrappers add semantic meaning

2. Then [domain-models.md](domain-models.md) → Core architecture
   - Models own their behavior
   - Aggregates coordinate related entities
   - Factories encapsulate construction logic

3. Then [immutability.md](immutability.md) → Critical constraint
   - Everything is frozen
   - State changes return new instances
   - Eliminates entire bug classes

4. Then [llm-integration.md](llm-integration.md) → AI patterns
   - Structured outputs for validation
   - Type-safe LLM responses
   - Tool definitions as async functions

5. Then [conversation-system.md](conversation-system.md) → Complete synthesis
   - Shows all patterns working together
   - Two-phase routing explained
   - Full conversation flow

6. Finally [service-patterns.md](service-patterns.md) → Boundaries
   - Services orchestrate, don't implement
   - Domain models contain logic
   - Clear separation of concerns

This mirrors the actual architecture: foundation (types) → core (models) → constraint (immutability) → integration (LLM) → complete system → boundaries (services).

### "I want to add state/data to a model"

**Critical decisions:**

**Q: Should this be stored or computed?**
- If derivable from other fields → Use `@computed_field` (see [Type System](type-system.md))
- If independent data → Add as field

**Q: Should this be mutable or immutable?**
- Domain models → Always `frozen=True` (see [Immutability](immutability.md))
- Configuration → `frozen=True`
- Infrastructure clients → Mutable (not domain models)

**Q: Should this be tuple or list?**
- If part of frozen model → Use `tuple` (immutable collection)
- If mutable container → Use `list` (but not in domain models!)

**Example:**
```python
class MyModel(BaseModel):
    # Stored field
    name: str
    
    # Stored collection (immutable)
    items: tuple[Item, ...] = ()
    
    # Computed field (derived)
    @computed_field
    @property
    def total(self) -> int:
        return sum(item.value for item in self.items)
    
    model_config = ConfigDict(frozen=True)
```

### "I want to track multi-stage transformations"

**Use case:** Document ingestion → validation → parsing → enrichment → persistence with error handling, skips, and observability.

**What you need:** The [Pipeline domain primitive](../../src/app/domain/pipeline.py) — a type-safe, immutable, observable abstraction for tracking transformations.

**Learning path:**

1. **Understand the pattern** → [pipeline-pattern.md](pipeline-pattern.md)
   - Complete guide to Pipeline abstraction
   - When to use vs alternatives
   - All components explained with examples
   - Anti-patterns and testing strategies

2. **Understand discriminated unions** → [type-system.md#discriminated-unions-type-safe-dispatch](type-system.md#discriminated-unions-type-safe-dispatch)
   - How `Stage = SuccessStage | FailedStage | SkippedStage` works
   - Type narrowing with `isinstance()`
   - Exhaustive pattern matching

3. **See Pipeline in context** → [data-flow.md#the-pipeline-domain-model](data-flow.md#the-pipeline-domain-model)
   - Pipeline as explicit transformation flow
   - Integration with Logfire
   - When to use vs when NOT to use

4. **Study the implementation** → [`src/app/domain/pipeline.py`](../../src/app/domain/pipeline.py)
   - Full implementation (775 lines)
   - RootModel wrappers, model validators, computed properties
   - Rich observability patterns

5. **See real tests** → [`tests/unit/domain/test_pipeline.py`](../../tests/unit/domain/test_pipeline.py)
   - How to build stages
   - How to test discriminated unions
   - How to test model validators

**Key pattern:** Build transformation functions that return `Stage` union based on outcome, then `pipeline.append()` immutably tracks the flow.

**Example structure:**

```python
def parse_stage(raw_input: RawData) -> SuccessStage | FailedStage:
    """Transformation function returns Stage union."""
    start = datetime.now(UTC)
    try:
        parsed = parse(raw_input)
        return SuccessStage(
            status=StageStatus.SUCCESS,
            category=StageCategory.PARSING,
            name=StageName("parse"),
            data=parsed,
            start_time=start,
            end_time=datetime.now(UTC)
        )
    except Exception as e:
        return FailedStage(
            status=StageStatus.FAILED,
            category=StageCategory.PARSING,
            error_category=ErrorCategory.VALIDATION,
            name=StageName("parse"),
            error=ErrorMessage(str(e)),
            start_time=start,
            end_time=datetime.now(UTC)
        )

# Execute pipeline
pipeline = Pipeline()
stage = parse_stage(raw_input)
pipeline = pipeline.append(stage)

# Check results
if pipeline.succeeded:
    result = pipeline.latest_data  # Type-safe
else:
    print(f"Errors: {pipeline.error_summary.total_errors}")
```

**Why Pipeline is a domain primitive, not an aggregate:**
- No identity (two pipelines with same stages are equal)
- No lifecycle (created and immutably transformed)
- No service coordination (users compose directly)
- Ephemeral (used for computation, not persisted as entity)

This is a **library abstraction** like `tuple` or `dict`, not a business entity like `Conversation`.

---

## Cross-Cutting Concepts

Some concepts appear in multiple documents because they're fundamental:

### Immutability
- **Defined in:** [immutability.md](immutability.md) "Why Immutability?"
- **Used in:** All domain models
- **Key pattern:** `model_copy(update={...})`
- **Purpose:** Eliminate race conditions, enable traceability

### Type Safety
- **Defined in:** [type-system.md](type-system.md) throughout
- **Used in:** Everywhere
- **Key patterns:** Smart enums, RootModel, Field validators
- **Purpose:** Invalid states become impossible

### Rich Behavior
- **Defined in:** [domain-models.md](domain-models.md) "Rich Behavior Methods"
- **Used in:** All aggregates
- **Key principle:** Behavior near data
- **Purpose:** Cohesive domain logic

### Explicit Transformations
- **Defined in:** [data-flow.md](data-flow.md) "Explicit Transformation Pipeline"
- **Used in:** All state changes
- **Key pattern:** `State → Operation → NewState`
- **Purpose:** Traceability and debugging

### Domain-Owned Persistence
- **Defined in:** [domain-models.md](domain-models.md) "Domain-Owned Persistence"
- **Implemented in:** `Conversation.save()`, `Conversation.load()`
- **Key principle:** Models know how to persist themselves
- **Purpose:** Keep domain logic cohesive

---

## Philosophy Connection

Every pattern in these docs traces back to principles in [philosophy.md](../philosophy.md):

| Application Pattern | Philosophy Principle |
|---------------------|----------------------|
| Smart enums, semantic types | "Every Type Teaches" |
| Rich domain models | "Every Business Rule Lives With Its Data" |
| Frozen models, model_copy | "Every State Change Returns New Data" |
| Thin services | Services orchestrate; domain models implement |
| Explicit transformations | "Every Transformation is Explicit" |
| Type-safe boundaries | "Every Boundary is Type-Safe" |

When you're making architecture decisions, reference [Philosophy](../philosophy.md) to understand the **why** behind the patterns.

---

## Relationship to Infrastructure

The application layer sits on top of infrastructure:

```
Application (this guide)
├── Domain models (business logic)
├── Services (orchestration)
└── API (HTTP boundary)
    ↓
Infrastructure (see infra/guide.md)
├── Databases (PostgreSQL, Redis, Neo4j, etc.)
├── Containers (Docker orchestration)
└── Configuration (secrets management)
```

**Key insight:** The patterns are the same at both levels.
- Infrastructure: Declarative services, specialized tools, orchestrated startup
- Application: Declarative types, specialized models, orchestrated flow

Both follow: **Make implicit explicit. Make hidden visible. Everything teaches.**

---

## Quick Command Reference

Common development operations:

```bash
# Start the stack
make dev

# Run tests
uv run pytest

# Type check
uv run mypy src/

# Interactive API testing
open http://localhost:8000/docs

# Shell into API container
docker compose exec api bash

# View API logs
docker compose logs -f api

# Python REPL with project context
docker compose exec api python
```

---

## When These Patterns Don't Apply

This architecture is optimized for:
- **Domain-rich applications** with complex business rules
- **Type-driven development** where correctness matters
- **AI-native systems** with LLM integration
- **Maintainable codebases** that teach themselves

These patterns are NOT optimal for:
- Throwaway scripts or one-off tools
- Simple CRUD with minimal business logic
- Performance-critical code that needs manual optimization
- Rapid prototyping where you're still discovering the domain

**For those cases:**
- Skip the rich domain models, use plain functions
- Skip immutability if you need in-place updates for performance
- Skip the elaborate type system, use basic types

But the **principles remain valid** even if you simplify the implementation.

---

## Next Steps

After understanding the application patterns:

1. **Read the actual code** - Start with `src/app/domain/conversation.py`
2. **Try the API** - http://localhost:8000/docs
3. **Read the tests** - See `tests/unit/domain/` for examples
4. **Read philosophy** - [philosophy.md](../philosophy.md) for the "why"

The patterns exist to support the philosophy. Once you understand why we build this way, the how becomes obvious.

**Remember:** These docs are reference material organized by pattern. Jump to what you need, follow cross-references, and use this guide to navigate back when you need broader context.

The goal isn't to read every doc linearly—it's to find the answer to your current question and understand how it connects to the larger architecture.

