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

Pydantic's `RootModel` lets you wrap primitives (UUID, str, int) with domain meaning, validation, and behavior.

**Why wrap primitives?**
- **Type safety:** Can't accidentally mix `MessageId` and `ConversationId` even though both are UUIDs
- **Validation:** Enforce constraints at construction (format, range, patterns)
- **Semantic meaning:** `StageName` is more expressive than `str`
- **Observability:** Logfire/OpenTelemetry see domain types, not generic primitives

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

### Semantic Types for Observability

From [`src/app/domain/pipeline.py`](../../src/app/domain/pipeline.py):

```python
class StageName(RootModel[str]):
    """Stage identifier with validation and semantic meaning.
    
    Wraps str to provide:
        - Type safety: Can't accidentally pass wrong string type
        - Validation: Enforces naming conventions at construction
        - Observability: Logfire displays as domain type, not generic string
    
    Validation Rules:
        - Non-empty (min 1 char)
        - Max 100 characters
        - Alphanumeric, hyphens, underscores only (safe for logs/metrics)
    """
    root: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    model_config = ConfigDict(frozen=True)


class ErrorMessage(RootModel[str]):
    """Explicit error message from failed transformation.
    
    Wraps error strings to:
        - Enforce non-empty requirement (failures must be documented)
        - Provide semantic type for Logfire error tracking
        - Set reasonable length limits for log storage
    
    Philosophy:
        Every failure must explain itself. An empty error message is
        as useless as no error at all. This type enforces that principle
        at construction time.
    """
    root: str = Field(min_length=1, max_length=1000)
    model_config = ConfigDict(frozen=True)


class CustomSkipReason(RootModel[str]):
    """Custom skip reason when standard SkipReason enums don't apply.
    
    Used exclusively with SkipReason.CUSTOM. Model validator on SkippedStage
    enforces this relationship at construction time.
    
    Why separate from ErrorMessage?
        Different semantic meaning: skip reasons explain conditional
        execution logic, error messages explain failures. Logfire can
        filter/group them independently.
    """
    root: str = Field(min_length=1, max_length=500)
    model_config = ConfigDict(frozen=True)
```

**Why not just use `str`?**

```python
# ❌ Without RootModel - no type safety or validation
def create_stage(name: str):
    # Can pass empty string, invalid chars, or wrong variable
    pass

create_stage("")  # Empty - but valid str!
create_stage("invalid name!")  # Special chars - but valid str!
create_stage(error_message)  # Wrong semantic type - but valid str!

# ✅ With RootModel - validated and type-safe
def create_stage(name: StageName):
    # Must pass StageName, which guarantees valid format
    pass

create_stage(StageName("parse-documents"))  # ✅ Valid
create_stage(StageName(""))  # ❌ ValidationError: min_length
create_stage(StageName("invalid name!"))  # ❌ ValidationError: pattern
create_stage(ErrorMessage("error text"))  # ❌ Type error: wrong semantic type
```

**Observability benefit:**

When you log or trace these values with Logfire/OpenTelemetry:
- **With RootModel:** `StageName("parse-documents")` → displays as `StageName` type
- **Without RootModel:** `"parse-documents"` → displays as generic `str`

This makes debugging easier: you can filter by "all StageName values" vs "all ErrorMessage values" in your observability platform, even though both are strings under the hood.

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

## Discriminated Unions: Type-Safe Dispatch

When an operation has multiple possible outcomes with different data shapes, use discriminated unions instead of Optional fields or conditional logic.

**What they are:** Union types where Pydantic automatically dispatches to the correct type based on a "discriminator" field.

**Why they matter:** Eliminates invalid states (can't have both success data and error), provides type narrowing (IDE knows which fields exist), and enables exhaustive pattern matching.

### The Pattern

From [`src/app/domain/pipeline.py`](../../src/app/domain/pipeline.py):

```python
# Three distinct outcomes, each with its own schema
class SuccessStage(BaseModel):
    status: Literal[StageStatus.SUCCESS]  # Discriminator value
    category: StageCategory
    name: StageName
    data: BaseModel  # Only success has data
    start_time: datetime
    end_time: datetime
    
    model_config = ConfigDict(frozen=True)
    
    @computed_field
    @property
    def duration_ms(self) -> float:
        """Only success and failed have duration."""
        delta = self.end_time - self.start_time
        return delta.total_seconds() * 1000


class FailedStage(BaseModel):
    status: Literal[StageStatus.FAILED]  # Discriminator value
    category: StageCategory
    name: StageName
    error: ErrorMessage  # Only failed has error
    error_category: ErrorCategory  # For grouping/alerting
    start_time: datetime
    end_time: datetime
    
    model_config = ConfigDict(frozen=True)
    
    @computed_field
    @property
    def duration_ms(self) -> float:
        """Time until failure occurred."""
        delta = self.end_time - self.start_time
        return delta.total_seconds() * 1000


class SkippedStage(BaseModel):
    status: Literal[StageStatus.SKIPPED]  # Discriminator value
    category: StageCategory
    name: StageName
    skip_reason: SkipReason
    custom_reason: CustomSkipReason | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    model_config = ConfigDict(frozen=True)


# Union: Pydantic dispatches on 'status' field
Stage = SuccessStage | FailedStage | SkippedStage
```

### Using Discriminated Unions

**Type narrowing with isinstance:**

```python
def process_stage(stage: Stage):
    """Exhaustive handling of all stage types."""
    if isinstance(stage, SuccessStage):
        # Type checker knows stage.data exists
        print(f"Success: {stage.data}")
        print(f"Duration: {stage.duration_ms}ms")
    elif isinstance(stage, FailedStage):
        # Type checker knows stage.error exists
        print(f"Failed: {stage.error.root}")
        print(f"Category: {stage.error_category.value}")
    elif isinstance(stage, SkippedStage):
        # Type checker knows stage.skip_reason exists
        print(f"Skipped: {stage.skip_reason.value}")
    # Type checker ensures all cases are handled!
```

**Automatic deserialization:**

```python
# Pydantic automatically picks the right type based on 'status' field
data = {"status": "success", "name": "parse", "data": {...}, ...}
stage = Stage.model_validate(data)  # → SuccessStage instance

data = {"status": "failed", "error": "Timeout", ...}
stage = Stage.model_validate(data)  # → FailedStage instance
```

### Decision Framework: When to Use

**Use discriminated unions when:**
- ✅ Multiple outcomes with different data shapes (success/failure/skipped)
- ✅ Need type safety (can't access .data on FailedStage)
- ✅ Want exhaustive checking (type checker ensures all cases handled)
- ✅ Clear discriminator field (status, type, kind)

**Use Optional fields when:**
- ✅ Field is truly optional (may or may not be present)
- ✅ Same data shape regardless
- ✅ No conditional logic based on presence

**DON'T use:**
- ❌ Multiple Optional fields for different outcomes (allows invalid states)
- ❌ Single class with type field and conditional logic (no type safety)
- ❌ Inheritance without union (loses automatic dispatch)

### Real-World Benefits

**From [`src/app/domain/pipeline.py`](../../src/app/domain/pipeline.py):**

```python
class Pipeline(BaseModel):
    """Tracks multi-stage transformations with type-safe outcomes."""
    
    stages: tuple[Stage, ...] = ()  # Can contain any stage type
    
    @property
    def latest_success(self) -> SuccessStage | None:
        """Find most recent successful stage."""
        for stage in reversed(self.stages):
            if isinstance(stage, SuccessStage):
                return stage  # Type narrowed to SuccessStage
        return None
    
    @property
    def latest_data(self) -> BaseModel:
        """Extract data from latest success (or raise)."""
        success = self.latest_success
        if success is None:
            raise ValueError("No successful stages in pipeline")
        return success.data  # Type checker knows .data exists
```

**No `type: ignore` needed. No runtime type checks. Just clean, safe code.**

---

## Model Validators: Cross-Field Business Rules

Use `@model_validator` when business rules require multiple fields to be correct together.

**What they are:** Validation functions that run during model construction and can access all fields simultaneously.

**Why they matter:** Enforces invariants at construction time, making it impossible to create instances in invalid states.

### Simple Cross-Field Validation

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

### Conditional Requirements

From [`src/app/domain/pipeline.py`](../../src/app/domain/pipeline.py):

```python
class SkippedStage(BaseModel):
    """Skipped pipeline stage with categorized reason."""
    
    status: Literal[StageStatus.SKIPPED]
    category: StageCategory
    name: StageName
    skip_reason: SkipReason  # Enum: DISABLED, CUSTOM, etc.
    custom_reason: CustomSkipReason | None = None  # Only with CUSTOM
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    model_config = ConfigDict(frozen=True)
    
    @model_validator(mode="after")
    def require_custom_reason_if_custom(self) -> SkippedStage:
        """Enforce relationship between skip_reason and custom_reason.
        
        Business Rules:
            1. SkipReason.CUSTOM requires custom_reason (explain yourself!)
            2. Other SkipReason values forbid custom_reason (use enum)
        
        Why enforce this?
            Prevents ambiguous states like:
            - CUSTOM with no explanation (unhelpful)
            - DISABLED with custom text (confusing: which is authoritative?)
        
        Raises:
            ValueError: If rules violated
        """
        if self.skip_reason == SkipReason.CUSTOM and self.custom_reason is None:
            raise ValueError("custom_reason required when skip_reason is CUSTOM")
        if self.skip_reason != SkipReason.CUSTOM and self.custom_reason is not None:
            raise ValueError("custom_reason only allowed when skip_reason is CUSTOM")
        return self
```

**Usage guarantees type safety:**

```python
# ✅ Valid - standard skip reason
skipped = SkippedStage(
    status=StageStatus.SKIPPED,
    category=StageCategory.NOTIFICATION,
    name=StageName("send-email"),
    skip_reason=SkipReason.DISABLED,
    custom_reason=None  # Must be None
)

# ✅ Valid - custom skip reason with explanation
skipped = SkippedStage(
    status=StageStatus.SKIPPED,
    category=StageCategory.ENRICHMENT,
    name=StageName("geocode"),
    skip_reason=SkipReason.CUSTOM,
    custom_reason=CustomSkipReason("Address already geocoded in cache")
)

# ❌ Raises ValidationError - CUSTOM without explanation
skipped = SkippedStage(
    skip_reason=SkipReason.CUSTOM,
    custom_reason=None  # Error!
    ...
)

# ❌ Raises ValidationError - DISABLED with custom reason
skipped = SkippedStage(
    skip_reason=SkipReason.DISABLED,
    custom_reason=CustomSkipReason("Custom text")  # Error!
    ...
)
```

### Decision Framework: Field vs Model Validators

**Use `@field_validator` when:**
- ✅ Validation concerns a single field
- ✅ No need to access other fields
- ✅ Simple constraints (range, format, length)
- Example: `@field_validator("email") def check_format(...)`

**Use `@model_validator` when:**
- ✅ Multiple fields must be correct together
- ✅ Conditional requirements between fields
- ✅ Complex business rules spanning fields
- Example: `start_date < end_date`, `if type == X then field Y required`

**Use `computed_field` when:**
- ✅ Value derivable from other fields
- ✅ No validation, just transformation
- ✅ Read-only (doesn't modify anything)
- Example: `@computed_field def full_name(self) -> str: return f"{self.first} {self.last}"`

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

## Composing Vendor Types: When to Wrap vs Compose

**When a vendor provides well-designed Pydantic types, compose them directly. Wrapper types that add no value are pure ceremony.**

Modern Python libraries (Pydantic AI, Qdrant, etc.) provide excellent Pydantic models as part of their API. The question becomes: should you wrap these types in your own domain models, or compose them directly?

**The Decision Framework:**

### Compose Vendor Types When:
- ✅ Vendor provides Pydantic models (not raw dicts or primitives)
- ✅ Types are well-designed and semantically meaningful
- ✅ No additional validation needed beyond vendor's
- ✅ Types represent domain concepts, not implementation details

### Wrap Vendor Types When:
- ✅ Adding domain-specific validation rules
- ✅ Adding computed properties or domain methods
- ✅ Vendor type is primitive (`str`, `int`, `dict`)
- ✅ Need semantic distinction (e.g., `DenseEmbeddingModel` vs `str`)

### Real Example: Vector Ingestion

From [`src/app/domain/vector_ingestion.py`](../../src/app/domain/vector_ingestion.py):

**❌ The Anti-Pattern (deleted from codebase):**

```python
# DON'T: Wrapper that adds zero value
class SparseVector(BaseModel):
    """Wrapper around Qdrant's SparseVector."""
    indices: list[int]
    values: list[float]
    model_config = ConfigDict(frozen=True)

# Now you need conversion everywhere
qdrant_sparse = QdrantSparseVector(
    indices=our_sparse.indices,
    values=our_sparse.values
)
```

**Problems:**
- Zero added value (no validation, no behavior, no domain meaning)
- Creates impedance mismatch (our type ↔ their type)
- Requires conversion at every boundary
- Obscures vendor semantics (Qdrant's type is already good)
- More code to maintain

**✅ The Right Pattern (current code):**

```python
# DO: Import and compose Qdrant's types directly
from qdrant_client.models import Payload, SparseVector, VectorStruct

class HybridEmbedding(BaseModel):
    """Text with dense and sparse vector representations."""
    text: str
    dense: list[float]
    sparse: SparseVector | None = None  # Qdrant's type, not ours
    
    model_config = ConfigDict(frozen=True)
```

**Benefits:**
- Zero conversion overhead
- Vendor semantics preserved (IDE shows Qdrant documentation)
- Type safety from composition
- AI comprehends vendor relationship
- Less code to maintain

### When Wrapping IS Appropriate

From the same file:

```python
# ✅ Wrapped: str → DenseEmbeddingModel (adds semantic meaning)
class DenseEmbeddingModel(RootModel[str]):
    """Semantic embedding model identifier for dense vectors."""
    root: str = Field(min_length=1, max_length=200)
    model_config = ConfigDict(frozen=True)
```

**Why wrap here?**
- Adds validation (length constraints)
- Provides semantic distinction (can't mix `DenseEmbeddingModel` with `SparseEmbeddingModel`)
- Vendor doesn't provide a type for this (it's just a string)
- Enhances observability (Logfire sees domain type, not generic string)

### Comparison: Pydantic AI Integration

From [`src/app/domain/domain_value.py`](../../src/app/domain/domain_value.py):

```python
class StoredMessage(BaseModel):
    """Message with Persistence Identity."""
    id: MessageId
    content: ModelMessage  # Pydantic AI's type - composed directly
    
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
```

**We compose `ModelMessage` directly** because:
- Pydantic AI provides well-designed discriminated unions
- No additional validation needed
- Wrapping would create conversion overhead
- We add our identity layer (`MessageId`) while composing their content layer

### The Storage Pattern

From [`src/app/service/storage.py`](../../src/app/service/storage.py):

```python
from redis import Redis as RedisClient
from psycopg import AsyncConnection as PostgresClient
from qdrant_client import QdrantClient

class StorageClients(BaseModel):
    """Composed vendor clients - no wrappers."""
    redis: RedisClient
    postgres: PostgresClient
    qdrant: QdrantClient
    # ... other clients
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
```

**Pattern: Compose clients, don't abstract them**
- Each client is the vendor's native type
- No repository pattern, no adapter layer
- Domain models take clients as dependencies
- Type system preserves vendor semantics

### Decision Tree

```
Should I create a wrapper type?
│
├─ Is it a vendor Pydantic type? ──YES──┐
│                                       │
│                                       ├─ Does it need validation? ──YES──> Wrap with validator
│                                       │
│                                       └─ Does it need methods? ──YES──> Wrap with methods
│                                           │
│                                           └─ NO ──> Compose directly
│
└─ Is it a primitive? ──YES──┐
                              │
                              ├─ Does it need semantic meaning? ──YES──> Wrap with RootModel
                              │
                              └─ Is it just data? ──YES──> Use BaseModel with explicit fields
```

### Anti-Pattern: Wrapper Repository Layers

**What NOT to do:**

```python
# ❌ Unnecessary abstraction layer
class VectorRepository:
    def __init__(self, client: QdrantClient):
        self._client = client
    
    def upsert_vector(self, embedding: OurVector) -> None:
        # Convert our types to Qdrant types
        qdrant_point = self._to_qdrant_point(embedding)
        self._client.upsert(...)
    
    def _to_qdrant_point(self, embedding: OurVector) -> QdrantPoint:
        # Conversion layer adds no value
        ...
```

**Why this is wrong:**
- Adds layer that just converts types
- Obscures Qdrant's API (can't use their docs directly)
- Makes it harder to use advanced features
- Violates "don't remake vendor types" principle

**What to do instead:**

```python
# ✅ Domain model takes client directly
class DocumentVectorIngestion(VectorIngestion):
    @classmethod
    async def ingest(
        cls,
        document: Document,
        qdrant: QdrantClient,  # Vendor client directly
    ) -> DocumentVectorIngestion:
        # Use Qdrant's types directly
        from qdrant_client.models import PointStruct, Payload
        
        point = PointStruct(
            id=str(uuid4()),
            vector=embedding_dict,
            payload=metadata.model_dump()  # Pydantic → dict → Payload
        )
        qdrant.upsert(collection_name="docs", points=[point])
```

**Benefits:**
- Domain logic owns persistence (not a separate repository)
- Uses vendor types directly (no conversion)
- Can use all Qdrant features (not limited by abstraction)
- Clear dependencies (takes QdrantClient)

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

❌ **DON'T use Optional fields for different outcomes**
- Single class with `data: BaseModel | None` and `error: str | None`
- Reality: Can construct with both or neither, runtime checks everywhere
- Use discriminated unions: `SuccessResult | FailedResult`

❌ **DON'T use type field without union**
- `result_type: str` with if/else to check type and cast
- Reality: No type safety, need `type: ignore`, easy to miss cases
- Use discriminated unions with `Literal` discriminator

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
- [`src/app/domain/pipeline.py`](../../src/app/domain/pipeline.py) - Discriminated unions, semantic types
- [`src/app/domain/vector_ingestion.py`](../../src/app/domain/vector_ingestion.py) - Composing Qdrant types
- [Semantic Search](semantic-search.md) - Vector ingestion and hybrid RAG patterns
- [Domain Models](domain-models.md) - Rich model patterns
- [Immutability](immutability.md) - Why frozen models matter

