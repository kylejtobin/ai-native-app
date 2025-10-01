# Type System Patterns

> **Using Python's type system to encode business logic and eliminate invalid states**

This document shows the type-driven patterns we use in this codebase, with real examples from `src/app/domain/`.

> **Principle: Every Type Teaches**
>
> Most codebases use primitive types everywhere—strings, ints, dicts—that tell you nothing about business meaning. This architecture uses smart enums for constrained choices, RootModel wrappers for semantic meaning, computed properties for derived values, and composition for complex structures.
>
> Types become self-documenting, invalid states become impossible, and the domain logic lives with the data.
>
> The shift from primitive obsession to semantic types, from runtime validation to compile-time safety, from documentation that goes stale to types that can't lie.
>
> See: [philosophy.md](../philosophy.md) "Every Type Teaches"

---

## Decision Framework: Choosing the Right Type Pattern

Before creating a new type, consider:

**Use StrEnum when:**
- ✅ Fixed set of known values (status, categories)
- ✅ Values need to be JSON-serializable strings
- ✅ Type safety prevents typos/invalid values
- ✅ Might add behavior later (methods on enum)

**Use RootModel when:**
- ✅ Wrapping a primitive with domain meaning (UUID → ConversationId)
- ✅ Need validation on construction
- ✅ Want to add methods to primitive types
- ✅ Type should be opaque (can't accidentally mix IDs)

**Use BaseModel when:**
- ✅ Multiple related fields
- ✅ Need computed properties
- ✅ Complex validation across fields
- ✅ Composition of multiple concepts

**Use computed_field when:**
- ✅ Value derivable from other fields
- ✅ No need to store separately
- ✅ Always correct (can't drift from source)
- ✅ Expensive to compute (cached by Pydantic)

**Use Literal when:**
- ✅ Single-use discriminator in union
- ✅ Type narrowing for pattern matching
- ✅ No need for enum overhead

**Examples from our codebase:**
- **ConversationStatus** → StrEnum (fixed states, might add state machine logic)
- **MessageId** → RootModel[UUID] (semantic meaning, opaque ID)
- **Conversation** → BaseModel (complex aggregate with multiple fields)
- **ConversationHistory.message_content** → computed_field (derived from messages tuple)

---

## Smart Enums: Business Logic in Constants

Enums aren't just string constants—they're behavioral types that encode business rules.

### Simple Lifecycle Enum

From [`src/app/domain/domain_type.py`](../../src/app/domain/domain_type.py):

```python
class ConversationStatus(StrEnum):
    """Conversation Lifecycle States.
    
    Tracks the operational status of a conversation for management and cleanup.
    
    States:
        ACTIVE: Normal conversation in progress
        ARCHIVED: Completed but retained for history/analytics
        DELETED: Soft-deleted, ready for garbage collection
    """
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"
```

**Why StrEnum?**
- Automatic string coercion for JSON serialization
- No custom encoders needed
- Type-safe in code, strings in storage

### Routing Enum with Domain Logic

From [`src/app/domain/domain_type.py`](../../src/app/domain/domain_type.py):

```python
class ModelRoute(StrEnum):
    """Model Routing Destinations.
    
    Enum of execution models that the ModelClassifier can select from.
    These represent the "strong" models used for actual query processing.
    
    Architecture Note:
        Fast models (Haiku, GPT-4o-mini) are used for routing decisions only
        and are not included here. This keeps routing overhead minimal while
        reserving expensive models for complex queries.
    
    Format:
        Values follow "vendor:model-id" format matching model_metadata.json entries
    """
    ANTHROPIC_SONNET = "anthropic:claude-sonnet-4-5-20250929"
    OPENAI_GPT5 = "openai:gpt-5"
```

**The Pattern:**
- Enum values encode the actual routing destinations
- Documentation explains the architectural decision (no fast models here)
- Format convention is enforced in the value itself
- Changes to routing strategy only require updating this enum

## RootModel: Wrapping Primitives with Type Safety

Pydantic's `RootModel` lets you wrap primitives (UUID, str, int) with domain meaning and behavior.

### Type-Safe Identifiers

From [`src/app/domain/domain_value.py`](../../src/app/domain/domain_value.py):

```python
class MessageId(RootModel[UUID]):
    """Unique Identifier for Individual Messages.
    
    Uses Pydantic's RootModel pattern to create a strongly-typed UUID wrapper.
    This provides type safety while maintaining UUID behavior for persistence.
    
    Usage:
        >>> msg_id = MessageId()  # Auto-generates UUID
        >>> str(msg_id.root)  # Access underlying UUID
        '550e8400-e29b-41d4-a716-446655440000'
    """
    root: UUID = Field(default_factory=uuid4)
    model_config = ConfigDict(frozen=True)


class ConversationId(RootModel[UUID]):
    """Unique Identifier for Conversations.
    
    Primary key for conversation persistence in Redis/database. Using RootModel
    provides type distinction from MessageId while keeping UUID semantics.
    
    Usage:
        >>> conv_id = ConversationId()
        >>> redis_key = f"conversation:{conv_id.root}"
    """
    root: UUID = Field(default_factory=uuid4)
    model_config = ConfigDict(frozen=True)
```

**Why separate types?**
- `MessageId` and `ConversationId` are both UUIDs, but represent different domain concepts
- Type system prevents you from passing a `MessageId` where a `ConversationId` is expected
- Both have UUID behavior (serialization, comparison) but distinct types
- Auto-generates UUIDs on construction with `default_factory`

### Wrapped Dictionary with Validation

From [`src/app/domain/model_catalog.py`](../../src/app/domain/model_catalog.py):

```python
class ModelCatalog(RootModel[dict[AIModelVendor, VendorCatalog]]):
    """Catalog of vendors - wraps dict for type safety and validation."""
    
    root: dict[AIModelVendor, VendorCatalog]
    model_config = ConfigDict(frozen=True)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelCatalog:
        """Load catalog from dict, explicitly injecting vendor keys."""
        enriched = {
            vendor_key: {**vendor_data, "vendor": vendor_key} 
            for vendor_key, vendor_data in data.items()
        }
        return cls.model_validate(enriched)
    
    def vendor(self, vendor: AIModelVendor) -> VendorCatalog:
        """O(1) dict lookup - vendor enum as key!"""
        if vendor not in self.root:
            raise KeyError(f"Vendor '{vendor.value}' not registered")
        return self.root[vendor]
```

**The Pattern:**
- Wraps a dict but provides type-safe accessors
- Validates structure on construction
- Enum keys ensure type safety at compile time
- Can't accidentally pass wrong vendor type

## Computed Properties: Derived Data with Caching

Use `@computed_field` for data derived from other fields. Pydantic caches these on frozen models.

### O(1) Lookup Dictionary

From [`src/app/domain/model_catalog.py`](../../src/app/domain/model_catalog.py):

```python
class VendorCatalog(BaseModel):
    """Per-Provider Model Catalog with Metadata."""
    
    vendor: AIModelVendor
    available_models: tuple[ModelVariant, ...] = ()
    
    model_config = ConfigDict(frozen=True)
    
    @computed_field
    @property
    def _variant_lookup(self) -> dict[str, ModelVariant]:
        """O(1) Lookup Dictionary (Cached by Pydantic).
        
        Builds a flattened dictionary mapping every identifier (id, api_id, alias)
        to its ModelVariant. This allows instant lookups instead of iterating
        through all variants and checking identifiers.
        
        Performance:
            - Construction: O(n × m) where n=variants, m=identifiers per variant
            - Lookup: O(1) constant time
            - Memory: O(n × m) for the dict
        
        Pydantic caches this on frozen models, so it's computed once per instance.
        """
        return {
            id: variant 
            for variant in self.available_models 
            for id in variant.identifiers
        }
    
    def find_variant(self, identifier: str) -> ModelVariant:
        """Find Model Variant by Any Valid Identifier.
        
        Performs O(1) lookup using the cached _variant_lookup dictionary.
        """
        variant = self._variant_lookup.get(identifier.strip())
        if variant is None:
            raise KeyError(
                f"Model '{identifier}' not registered for vendor '{self.vendor.value}'"
            )
        return variant
```

**Why this works:**
1. `model_config = {"frozen": True}` makes the model immutable
2. Pydantic caches `@computed_field` values on frozen models
3. Dictionary is computed once, reused for all lookups
4. Trades memory for speed—classic CS tradeoff

### Extracting Nested Content

From [`src/app/domain/domain_value.py`](../../src/app/domain/domain_value.py):

```python
class ConversationHistory(BaseModel):
    """Complete Conversation State for Persistence."""
    
    id: ConversationId
    messages: tuple[StoredMessage, ...] = ()
    status: ConversationStatus = ConversationStatus.ACTIVE
    
    model_config = ConfigDict(frozen=True)
    
    @property
    def message_content(self) -> tuple[ModelMessage, ...]:
        """Extract Pydantic AI Messages for Model Execution.
        
        Strips away our identity layer to get the raw ModelMessage objects
        that Pydantic AI expects in message_history parameter.
        
        Returns:
            Tuple of ModelMessage objects ready for model.run()
        """
        return tuple(msg.content for msg in self.messages)
    
    @property
    def used_tokens(self) -> int:
        """Calculate Total Token Usage Across All Messages.
        
        Aggregates token counts from all ModelResponse messages for analytics
        and cost tracking. This is a read-only property computed on demand.
        
        Important:
            This is for observability ONLY. Budget enforcement should use
            Pydantic AI's built-in UsageLimits feature, not this property.
        
        Returns:
            Total tokens consumed by LLM calls in this conversation
        """
        total = 0
        for msg in self.messages:
            # Only ModelResponse messages contain usage data
            if isinstance(msg.content, ModelResponse) and msg.content.usage:
                total += msg.content.usage.total_tokens
        return total
```

**Design note:**
- `message_content` is a view transformation—no expensive computation
- `used_tokens` aggregates on each access—fine for occasional analytics
- If called frequently, could be promoted to `@computed_field` for caching

## Composition: Building Complex from Simple

Compose small, focused models into larger aggregates.

### Identity Layer Wrapping Content Layer

From [`src/app/domain/domain_value.py`](../../src/app/domain/domain_value.py):

```python
class StoredMessage(BaseModel):
    """Message with Persistence Identity.
    
    Wraps Pydantic AI's ModelMessage with our own MessageId for storage and reference.
    This allows us to:
    - Store conversations in persistent storage (Redis, PostgreSQL)
    - Reference specific messages for editing or deletion
    - Track message-level metadata without modifying Pydantic AI types
    
    Attributes:
        id: Our unique identifier for this message
        content: Pydantic AI's ModelMessage (discriminated union of Request/Response)
    
    Note:
        arbitrary_types_allowed is required because ModelMessage is a Pydantic AI type
        that we don't own, but we want to compose it into our domain model
    """
    id: MessageId
    content: ModelMessage  # Pydantic AI's type
    
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
```

**The Separation:**
- **Identity** (ours): `MessageId`, `ConversationId`
- **Content** (Pydantic AI's): `ModelMessage`, `ModelRequest`, `ModelResponse`
- **Metadata** (ours): `ConversationStatus`, token tracking

We don't duplicate Pydantic AI's types—we compose them.

### Registry Pattern with Validation

From [`src/app/domain/model_catalog.py`](../../src/app/domain/model_catalog.py):

```python
class ModelRegistry(BaseModel):
    """Allow-listed set of models scoped to a single catalog."""
    
    catalog: ModelCatalog
    default: ModelSpec
    available: tuple[ModelSpec, ...]
    
    model_config = ConfigDict(frozen=True)
    
    @field_validator("available", mode="after")
    @classmethod
    def _deduplicate_and_ensure_default(
        cls, 
        v: tuple[ModelSpec, ...], 
        info: ValidationInfo
    ) -> tuple[ModelSpec, ...]:
        """Deduplicate specs and ensure default is first."""
        default = info.data.get("default")
        if not default:
            return v
        
        # Deduplicate while preserving order, ensure default is first
        seen: set[ModelSpec] = set()
        ordered: list[ModelSpec] = []
        
        if default in v:
            ordered.append(default)
            seen.add(default)
        
        for spec in v:
            if spec not in seen:
                ordered.append(spec)
                seen.add(spec)
        
        return tuple(ordered)
    
    def resolve_or_default(self, spec: ModelSpec | None) -> ModelSpec:
        """Use provided spec or fall back to default."""
        return self.default if spec is None else self.resolve_spec(spec)
```

**Composition Benefits:**
- `ModelRegistry` composes `ModelCatalog` + allowed specs
- Validation ensures default is in available list
- Business logic (resolve_or_default) uses composed data
- Single source of truth for model availability

## Model Validators: Cross-Field Business Rules

Use `@model_validator` when business rules span multiple fields.

From [`src/app/domain/model_catalog.py`](../../src/app/domain/model_catalog.py):

```python
class VendorCatalog(BaseModel):
    """Per-Provider Model Catalog with Metadata."""
    
    vendor: AIModelVendor
    available_models: tuple[ModelVariant, ...] = ()
    
    model_config = ConfigDict(frozen=True)
    
    @model_validator(mode="after")
    def check_duplicate_identifiers(self) -> VendorCatalog:
        """Validate No Duplicate Model Identifiers.
        
        Runs after model construction to ensure all model identifiers
        (including aliases) are unique within this vendor's catalog.
        
        Raises:
            ValueError: If any identifier appears in multiple variants
        """
        # Flatten all identifiers from all variants
        all_ids = [
            id 
            for variant in self.available_models 
            for id in variant.identifiers
        ]
        unique_ids = set(all_ids)
        
        # Check for duplicates
        if len(all_ids) != len(unique_ids):
            duplicates = [x for x in unique_ids if all_ids.count(x) > 1]
            raise ValueError(
                f"Duplicate model identifiers for vendor '{self.vendor.value}': "
                f"{sorted(duplicates)}"
            )
        return self
```

**Why `mode="after"`?**
- Runs after all fields are validated and set
- Can access all model data via `self`
- Can raise errors for invalid combinations
- Model construction fails fast if rules are violated

## Benefits of This Approach

**Type Safety:**
- `MessageId` ≠ `ConversationId` even though both are UUIDs
- Can't pass wrong enum value to functions
- IDE autocomplete knows exactly what's valid

**Performance:**
- Computed properties cache expensive operations
- O(1) lookups instead of O(n) searches
- Pay construction cost once, get fast lookups forever

**Correctness:**
- Invalid states can't be constructed
- Business rules enforced at type level
- Fail fast on violations

**Maintainability:**
- Types document intent
- Changes isolated to specific types
- Refactoring is safe

---

## Anti-Patterns: What NOT to Do

❌ **DON'T use `dict[str, Any]` for domain data**
- "I'll just use a dict, it's flexible"
- Reality: No validation, no IDE help, typos become runtime errors
- Use BaseModel with explicit fields

❌ **DON'T use strings where enums prevent typos**
- `status: str` with comments saying "must be 'active', 'archived', or 'deleted'"
- Reality: Typos cause bugs, no autocomplete, invalid states possible
- Use StrEnum: `status: ConversationStatus`

❌ **DON'T skip field validators for complex rules**
- "I'll just validate in the service layer"
- Reality: Models can be constructed in invalid states, validation scattered
- Use `@field_validator` and `@model_validator` in the model

❌ **DON'T use Optional without default**
- `field: str | None` with no `= None`
- Reality: Confusing API, unclear if None is valid or error
- Either `field: str` (required) or `field: str | None = None` (optional with default)

❌ **DON'T put business logic outside the type**
- Helper functions that operate on models: `def calculate_total(conversation): ...`
- Reality: Logic divorced from data, scattered across codebase
- Add methods to the model: `conversation.calculate_total()`

❌ **DON'T use mutable collections in frozen models**
- `messages: list[Message] = []` in a `frozen=True` model
- Reality: Can still mutate the list even though model is frozen
- Use `tuple[Message, ...] = ()` for immutable collections

❌ **DON'T create "wrapper" types that add no value**
- `class UserName(RootModel[str]): ...` with no validation or methods
- Reality: Just ceremony, no benefit
- Only wrap primitives when adding semantic meaning or behavior

❌ **DON'T use computed_field for expensive operations without caching**
- Computed property that does database queries or heavy computation
- Reality: Accessed multiple times, recomputes each time
- Pydantic caches computed_field on frozen models, but still avoid heavy ops

---

**See Also:**
- [`src/app/domain/domain_type.py`](../../src/app/domain/domain_type.py) - Smart enums
- [`src/app/domain/domain_value.py`](../../src/app/domain/domain_value.py) - RootModel patterns
- [`src/app/domain/model_catalog.py`](../../src/app/domain/model_catalog.py) - Complex composition
- [Domain Models](domain-models.md) - Rich model patterns
- [Immutability](immutability.md) - Why frozen models matter

