# Pipeline Pattern: Type-Safe Multi-Stage Transformations

> **Domain primitives that users compose directly, without service orchestration**

This document explains the Pipeline abstraction—a generic, reusable pattern for tracking multi-stage data transformations with rich observability and type safety.

> **Principle: Every Transformation is Explicit and Observable**
>
> Complex workflows often hide their progression: did this step succeed? Why did it fail? What was skipped? Traditional error handling obscures the flow. Logs are unstructured. Debugging requires archaeology.
>
> Pipeline makes every stage explicit, every outcome typed, and every failure categorized. You can inspect state at any point, compare before/after, export structured metrics for observability platforms. The transformation history is the data structure.
>
> See: [philosophy.md](../philosophy.md) "Every Transformation is Explicit"

---

## What is Pipeline?

**Definition:** An immutable, type-safe abstraction for tracking multi-stage data transformations where each stage can succeed, fail, or be skipped.

**Not a framework.** Pipeline is a **domain primitive**—a library abstraction like `tuple` or `dict` that users compose into domain-specific workflows. No service layer needed.

From [`src/app/domain/pipeline.py`](../../src/app/domain/pipeline.py):

```python
class Pipeline(BaseModel):
    """Immutable pipeline orchestrator tracking multi-stage transformations.
    
    Core abstraction for type-safe, observable data transformation pipelines.
    Accumulates Stage discriminated unions as execution progresses.
    
    Design Principles:
        1. Immutability: append() returns new Pipeline, original unchanged
        2. Type Safety: Stages validated at construction, no raw data
        3. Observability: Rich metadata for Logfire tracing
        4. Composability: Build domain-specific pipelines from primitives
    """
    stages: tuple[Stage, ...] = ()  # Immutable collection
    
    model_config = ConfigDict(frozen=True)
    
    def append(self, stage: Stage) -> Pipeline:
        """Append stage immutably, returning new Pipeline instance."""
        return self.model_copy(update={"stages": (*self.stages, stage)})
```

**At 775 lines, it's the largest domain file—a sophisticated abstraction teaching advanced Pydantic patterns.**

---

## Why Use Pipeline?

### Decision Framework

**Use Pipeline when:**
- ✅ Multi-stage transformations with branching logic (success → continue, failure → halt)
- ✅ Need uniform tracking of successes, failures, and skips
- ✅ Want rich observability (duration, error categorization, flow visualization)
- ✅ Complex workflows where order and outcomes matter
- ✅ Building document processing, ETL, validation pipelines

**Don't use Pipeline when:**
- ❌ Simple single-step transformations (use direct function)
- ❌ Service orchestration across aggregates (use service layer)
- ❌ HTTP request/response cycles (use FastAPI routers)
- ❌ Simple sequential operations with no branching (overkill)
- ❌ Need mutable accumulation (Pipeline is immutable)

**Alternative patterns:**
- Simple function → For one transformation
- Service method → For cross-aggregate orchestration
- Workflow engine → For long-running, persistent workflows
- Pipeline → For in-memory, type-safe, observable transformations

---

## The Components

Pipeline is composed of several cohesive patterns working together.

### 1. Semantic Types (RootModel Wrappers)

From [`src/app/domain/pipeline.py`](../../src/app/domain/pipeline.py):

```python
class StageName(RootModel[str]):
    """Stage identifier with validation and semantic meaning.
    
    Validation Rules:
        - Non-empty (min 1 char)
        - Max 100 characters
        - Alphanumeric, hyphens, underscores only (safe for logs/metrics)
    
    Why RootModel?
        Provides semantic meaning without field overhead. Logfire
        displays as domain type, not generic string.
    """
    root: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    model_config = ConfigDict(frozen=True)


class ErrorMessage(RootModel[str]):
    """Explicit error message from failed transformation.
    
    Philosophy:
        Every failure must explain itself. An empty error message is
        as useless as no error at all. This type enforces that principle
        at construction time.
    """
    root: str = Field(min_length=1, max_length=1000)
    model_config = ConfigDict(frozen=True)


class CustomSkipReason(RootModel[str]):
    """Custom skip reason when standard SkipReason enums don't apply."""
    root: str = Field(min_length=1, max_length=500)
    model_config = ConfigDict(frozen=True)
```

**Why wrap primitives?**
- **Type safety:** Can't pass `ErrorMessage` where `StageName` expected
- **Validation:** Enforced at construction, impossible to create invalid instances
- **Observability:** Logfire sees `StageName`, not generic `str`
- **Documentation:** Type signature tells you what kind of string

---

### 2. Stage Discriminated Union

The core pattern: three distinct outcome types unified in a type-safe union.

From [`src/app/domain/pipeline.py`](../../src/app/domain/pipeline.py):

```python
class SuccessStage(BaseModel):
    """Successful pipeline stage with validated output data."""
    
    status: Literal[StageStatus.SUCCESS]  # Discriminator
    category: StageCategory  # What kind of transformation
    name: StageName  # Stage identifier
    data: BaseModel  # Output data (validated)
    start_time: datetime
    end_time: datetime
    
    model_config = ConfigDict(frozen=True)
    
    @computed_field
    @property
    def duration_ms(self) -> float:
        """Execution duration computed from timestamps."""
        delta = self.end_time - self.start_time
        return delta.total_seconds() * 1000


class FailedStage(BaseModel):
    """Failed pipeline stage with categorized error for debugging."""
    
    status: Literal[StageStatus.FAILED]  # Discriminator
    category: StageCategory  # What was being attempted
    error_category: ErrorCategory  # Why it failed (for grouping)
    name: StageName
    error: ErrorMessage  # Required error description
    start_time: datetime
    end_time: datetime
    
    model_config = ConfigDict(frozen=True)
    
    @computed_field
    @property
    def duration_ms(self) -> float:
        """Time from start until failure occurred."""
        delta = self.end_time - self.start_time
        return delta.total_seconds() * 1000


class SkippedStage(BaseModel):
    """Skipped pipeline stage with categorized reason for conditional execution."""
    
    status: Literal[StageStatus.SKIPPED]  # Discriminator
    category: StageCategory  # What was being considered
    name: StageName
    skip_reason: SkipReason  # Standard reason enum
    custom_reason: CustomSkipReason | None = None  # Only with CUSTOM
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    model_config = ConfigDict(frozen=True)
    
    @model_validator(mode="after")
    def require_custom_reason_if_custom(self) -> SkippedStage:
        """Enforce relationship between skip_reason and custom_reason.
        
        Business Rules:
            1. SkipReason.CUSTOM requires custom_reason (explain yourself!)
            2. Other SkipReason values forbid custom_reason (use enum)
        """
        if self.skip_reason == SkipReason.CUSTOM and self.custom_reason is None:
            raise ValueError("custom_reason required when skip_reason is CUSTOM")
        if self.skip_reason != SkipReason.CUSTOM and self.custom_reason is not None:
            raise ValueError("custom_reason only allowed when skip_reason is CUSTOM")
        return self


# Discriminated Union: Pydantic dispatches on 'status' field
Stage = SuccessStage | FailedStage | SkippedStage
```

**Key insights:**
- **Different data shapes:** `SuccessStage` has `data`, `FailedStage` has `error`, `SkippedStage` has neither
- **Type narrowing:** `isinstance(stage, SuccessStage)` tells type checker `stage.data` exists
- **Exhaustive checking:** Type checker ensures all cases handled
- **No `type: ignore` needed:** Discriminated unions eliminate ambiguity

---

### 3. Enums for Categorization

From [`src/app/domain/domain_type.py`](../../src/app/domain/domain_type.py):

```python
class StageStatus(StrEnum):
    """Outcome of any transformation stage."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class StageCategory(StrEnum):
    """Functional classification of transformation stages.
    
    Helps Logfire visualize pipeline flow by transformation type.
    """
    INGESTION = "ingestion"
    VALIDATION = "validation"
    PARSING = "parsing"
    TRANSFORMATION = "transformation"
    ENRICHMENT = "enrichment"
    CLASSIFICATION = "classification"
    PERSISTENCE = "persistence"
    NOTIFICATION = "notification"


class ErrorCategory(StrEnum):
    """Classification of pipeline errors for tracking and alerting.
    
    Enables Logfire to group errors by type for pattern detection.
    """
    VALIDATION = "validation"
    TRANSFORMATION = "transformation"
    EXTERNAL_SERVICE = "external"
    TIMEOUT = "timeout"
    RESOURCE = "resource"
    DEPENDENCY = "dependency"
    UNKNOWN = "unknown"


class SkipReason(StrEnum):
    """Standard reasons for skipping pipeline stages."""
    CONDITION_NOT_MET = "condition_not_met"
    ALREADY_PROCESSED = "already_processed"
    DISABLED = "disabled"
    DEPENDENCY_FAILED = "dependency_failed"
    OPTIONAL = "optional"
    CUSTOM = "custom"
```

**Why categorization matters:**
- **Observability:** Group by category in Logfire dashboards
- **Alerting:** "Notify if timeout errors > 10"
- **Pattern detection:** "Why are all enrichment stages failing?"
- **Analytics:** "Which stage types take longest?"

---

### 4. Observable Aggregates

From [`src/app/domain/pipeline.py`](../../src/app/domain/pipeline.py):

```python
class ErrorSummary(RootModel[dict[ErrorCategory, int]]):
    """Error count distribution by category for observability and alerting."""
    
    root: dict[ErrorCategory, int] = Field(default_factory=dict)
    model_config = ConfigDict(frozen=True)
    
    @computed_field
    @property
    def total_errors(self) -> int:
        """Total failed stages across all categories."""
        return sum(self.root.values())
    
    @computed_field
    @property
    def most_common(self) -> ErrorCategory | None:
        """Most frequent error category for quick diagnosis."""
        if not self.root:
            return None
        return max(self.root.items(), key=lambda x: x[1])[0]


class LogfireAttributes(RootModel[dict[str, Any]]):
    """Pipeline state exported as Logfire span attributes.
    
    Structure (keys always present):
        - pipeline.total_stages: int
        - pipeline.succeeded: bool
        - pipeline.failed: bool
        - pipeline.total_duration_ms: float
        - pipeline.stage_flow: list[str] (category values)
        - pipeline.error_summary: dict[str, int] (category → count)
    """
    root: dict[str, Any]
    model_config = ConfigDict(frozen=True)
```

**The pattern:**
- Computed properties add intelligence to raw data
- Wrapping in RootModel provides semantic type
- Logfire gets structured, queryable attributes

---

### 5. Pipeline Orchestrator

From [`src/app/domain/pipeline.py`](../../src/app/domain/pipeline.py):

```python
class Pipeline(BaseModel):
    """Immutable pipeline orchestrator tracking multi-stage transformations."""
    
    stages: tuple[Stage, ...] = ()  # Immutable collection
    model_config = ConfigDict(frozen=True)
    
    def append(self, stage: Stage) -> Pipeline:
        """Append stage immutably, returning new Pipeline instance."""
        return self.model_copy(update={"stages": (*self.stages, stage)})
    
    @computed_field
    @property
    def succeeded(self) -> bool:
        """True if all stages succeeded (no failures, at least one stage)."""
        if not self.stages:
            return False
        return all(isinstance(stage, SuccessStage) for stage in self.stages)
    
    @computed_field
    @property
    def failed(self) -> bool:
        """True if any stage failed (one failure fails the pipeline)."""
        return any(isinstance(stage, FailedStage) for stage in self.stages)
    
    @computed_field
    @property
    def error_summary(self) -> ErrorSummary:
        """Aggregate errors by category for observability and alerting."""
        errors = [stage.error_category for stage in self.stages if isinstance(stage, FailedStage)]
        return ErrorSummary(dict(Counter(errors)))
    
    @computed_field
    @property
    def stage_categories(self) -> tuple[StageCategory, ...]:
        """Ordered sequence of stage categories for flow visualization."""
        return tuple(stage.category for stage in self.stages)
    
    @computed_field
    @property
    def total_duration_ms(self) -> float:
        """Total pipeline execution time (sum of all executed stages)."""
        total = 0.0
        for stage in self.stages:
            if isinstance(stage, (SuccessStage, FailedStage)):
                total += stage.duration_ms
        return total
    
    @property
    def latest_stage(self) -> Stage | None:
        """Most recent stage regardless of outcome."""
        return self.stages[-1] if self.stages else None
    
    @property
    def latest_success(self) -> SuccessStage | None:
        """Most recent successful stage (walks backward from end)."""
        for stage in reversed(self.stages):
            if isinstance(stage, SuccessStage):
                return stage
        return None
    
    @property
    def latest_data(self) -> BaseModel:
        """Extract data from most recent successful stage.
        
        Raises:
            ValueError: If no successful stages exist in pipeline.
        """
        success = self.latest_success
        if success is None:
            raise ValueError("No successful stages in pipeline")
        return success.data
    
    def to_logfire_attributes(self) -> LogfireAttributes:
        """Export pipeline state as structured Logfire span attributes."""
        return LogfireAttributes({
            "pipeline.total_stages": len(self.stages),
            "pipeline.succeeded": self.succeeded,
            "pipeline.failed": self.failed,
            "pipeline.total_duration_ms": self.total_duration_ms,
            "pipeline.stage_flow": [cat.value for cat in self.stage_categories],
            "pipeline.error_summary": {k.value: v for k, v in self.error_summary.root.items()},
        })
```

**Design highlights:**
- Immutable: `frozen=True` + `tuple` for stages
- Rich computed properties: `succeeded`, `failed`, `error_summary`
- Type-safe data access: `latest_data` raises if no success
- Observable: `to_logfire_attributes()` for tracing

---

## Usage Patterns

### Basic Pipeline Flow

From [`tests/unit/domain/test_pipeline.py`](../../tests/unit/domain/test_pipeline.py):

```python
from datetime import UTC, datetime
from app.domain.pipeline import Pipeline, SuccessStage, FailedStage, StageName
from app.domain.domain_type import StageStatus, StageCategory, ErrorCategory

# Test data model
class ParsedData(BaseModel):
    tokens: list[str]

# Start with empty pipeline
pipeline = Pipeline()

# Stage 1: Parse data
start = datetime.now(UTC)
try:
    tokens = ["hello", "world"]
    stage = SuccessStage(
        status=StageStatus.SUCCESS,
        category=StageCategory.PARSING,
        name=StageName("parse"),
        data=ParsedData(tokens=tokens),
        start_time=start,
        end_time=datetime.now(UTC)
    )
except Exception as e:
    stage = FailedStage(
        status=StageStatus.FAILED,
        category=StageCategory.PARSING,
        error_category=ErrorCategory.VALIDATION,
        name=StageName("parse"),
        error=ErrorMessage(str(e)),
        start_time=start,
        end_time=datetime.now(UTC)
    )

pipeline = pipeline.append(stage)

# Check if we can continue
if pipeline.failed:
    print(f"Pipeline failed: {pipeline.error_summary.total_errors} errors")
    print(f"Most common error: {pipeline.error_summary.most_common}")
    return pipeline

# Stage 2: Continue processing
data = pipeline.latest_data  # Type-safe: raises if no success
print(f"Parsed data: {data}")
```

### Transformation Function Pattern

**Encapsulate stages in functions that return Stage unions:**

```python
def parse_stage(raw: RawInput) -> SuccessStage | FailedStage:
    """Parse raw input into structured data.
    
    Returns:
        SuccessStage if parsing succeeds
        FailedStage if parsing fails
    """
    start = datetime.now(UTC)
    try:
        parsed = parse(raw)
        return SuccessStage(
            status=StageStatus.SUCCESS,
            category=StageCategory.PARSING,
            name=StageName("parse"),
            data=parsed,
            start_time=start,
            end_time=datetime.now(UTC)
        )
    except ValidationError as e:
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
```

### Conditional Stages with Skips

```python
def enrich_stage(data: ParsedData) -> SuccessStage | SkippedStage:
    """Enrich data with external API if enabled.
    
    Returns:
        SuccessStage if enrichment succeeds
        SkippedStage if enrichment disabled or already enriched
    """
    if not ENRICHMENT_ENABLED:
        return SkippedStage(
            status=StageStatus.SKIPPED,
            category=StageCategory.ENRICHMENT,
            name=StageName("enrich"),
            skip_reason=SkipReason.DISABLED,
            timestamp=datetime.now(UTC)
        )
    
    if data.already_enriched:
        return SkippedStage(
            status=StageStatus.SKIPPED,
            category=StageCategory.ENRICHMENT,
            name=StageName("enrich"),
            skip_reason=SkipReason.ALREADY_PROCESSED,
            timestamp=datetime.now(UTC)
        )
    
    start = datetime.now(UTC)
    enriched = call_external_api(data)
    return SuccessStage(
        status=StageStatus.SUCCESS,
        category=StageCategory.ENRICHMENT,
        name=StageName("enrich"),
        data=enriched,
        start_time=start,
        end_time=datetime.now(UTC)
    )
```

### Complete Multi-Stage Pipeline

```python
def execute_pipeline(raw_input: RawInput) -> Pipeline:
    """Execute complete data processing pipeline."""
    pipeline = Pipeline()
    
    # Stage 1: Ingest
    stage = ingest_stage(raw_input)
    pipeline = pipeline.append(stage)
    if pipeline.failed:
        return pipeline
    
    # Stage 2: Validate
    data = pipeline.latest_data
    stage = validate_stage(data)
    pipeline = pipeline.append(stage)
    if pipeline.failed:
        return pipeline
    
    # Stage 3: Parse
    data = pipeline.latest_data
    stage = parse_stage(data)
    pipeline = pipeline.append(stage)
    if pipeline.failed:
        return pipeline
    
    # Stage 4: Enrich (optional)
    data = pipeline.latest_data
    stage = enrich_stage(data)
    pipeline = pipeline.append(stage)
    # Continue even if skipped
    
    # Stage 5: Persist
    data = pipeline.latest_data
    stage = persist_stage(data)
    pipeline = pipeline.append(stage)
    
    return pipeline


# Use pipeline
pipeline = execute_pipeline(raw_input)

if pipeline.succeeded:
    print(f"Success! Processed in {pipeline.total_duration_ms}ms")
    print(f"Flow: {' → '.join(c.value for c in pipeline.stage_categories)}")
else:
    print(f"Failed with {pipeline.error_summary.total_errors} errors")
    print(f"Most common: {pipeline.error_summary.most_common}")
    
    # Export for observability
    attrs = pipeline.to_logfire_attributes()
    with logfire.span("pipeline_execution", **attrs.root):
        logfire.error("Pipeline failed", pipeline=pipeline)
```

---

## Integration with Logfire

Export pipeline state as structured observability data:

```python
import logfire

# Execute pipeline
pipeline = execute_pipeline(input_data)

# Export to Logfire
attrs = pipeline.to_logfire_attributes()

with logfire.span("data_pipeline", **attrs.root):
    if pipeline.failed:
        logfire.error(
            "Pipeline execution failed",
            total_errors=attrs.root["pipeline.error_summary"],
            stage_flow=attrs.root["pipeline.stage_flow"]
        )
    else:
        logfire.info(
            "Pipeline execution succeeded",
            total_duration=attrs.root["pipeline.total_duration_ms"],
            total_stages=attrs.root["pipeline.total_stages"]
        )
```

**In Logfire, you can query:**
- "Show all pipelines with timeout errors"
- "What's the average duration for parsing stages?"
- "Which stage categories fail most often?"
- "Visualize pipeline flow for failed executions"

---

## Anti-Patterns: What NOT to Do

❌ **DON'T mutate stages after creation**
- Stages are `frozen=True` for immutability
- Reality: Raises `ValidationError` on mutation attempt
- Pattern: Create new stage with different data

❌ **DON'T use Pipeline for service orchestration**
- Pipeline is for in-memory transformations, not cross-aggregate coordination
- Reality: Services should coordinate aggregates, not use Pipeline
- Pattern: Service orchestrates; Pipeline tracks transformations within one flow

❌ **DON'T skip error categorization**
- Defeats observability: can't filter/group errors
- Reality: All errors show as "unknown," no insights
- Pattern: Always use appropriate `ErrorCategory`

❌ **DON'T access .data without checking**
```python
# ❌ Bad - will fail if stage is not SuccessStage
data = stage.data  # AttributeError if FailedStage!

# ✅ Good - type narrowing ensures .data exists
if isinstance(stage, SuccessStage):
    data = stage.data  # Type-safe
```

❌ **DON'T use list for stages**
```python
# ❌ Bad - mutable collection
class Pipeline(BaseModel):
    stages: list[Stage] = []

# ✅ Good - immutable collection
class Pipeline(BaseModel):
    stages: tuple[Stage, ...] = ()
```

❌ **DON'T forget to reassign after append**
```python
# ❌ Bad - append returns new instance, original unchanged
pipeline = Pipeline()
pipeline.append(stage)  # Returns new Pipeline, but not assigned!
print(len(pipeline.stages))  # 0 - original pipeline unchanged

# ✅ Good - reassign to capture new instance
pipeline = Pipeline()
pipeline = pipeline.append(stage)
print(len(pipeline.stages))  # 1
```

❌ **DON'T use Pipeline for simple operations**
- If it's just one transformation, use a function
- Reality: Pipeline overhead (stage construction, tracking) is unnecessary
- Pattern: Pipeline for multi-stage flows, functions for single steps

❌ **DON'T persist Pipeline as entity**
- Pipeline is ephemeral, used for computation
- Reality: If you need to persist, persist the outcome, not the Pipeline
- Pattern: Log pipeline state to observability, persist final result to database

---

## Comparison to Alternatives

### vs. Simple Function

**Function:**
```python
def process(raw: RawInput) -> ProcessedData:
    data = parse(raw)
    enriched = enrich(data)
    return persist(enriched)
```

**When function is better:** Single responsibility, no branching, no observability needed

**When Pipeline is better:** Multi-stage with errors/skips, need observability

### vs. Service Layer

**Service:**
```python
async def process_order(order_id: OrderId) -> None:
    order = await Order.load(order_id, db)
    payment = await Payment.process(order.total, gateway)
    shipping = await Shipping.schedule(order, warehouse)
    await order.mark_complete(db)
```

**When service is better:** Cross-aggregate orchestration, async I/O, persistence

**When Pipeline is better:** In-memory transformations, sync processing, observability

### vs. Workflow Engine (Temporal, Celery)

**Workflow Engine:**
- Long-running workflows (hours, days)
- Persistent state between steps
- Retries, timeouts, distributed execution

**Pipeline:**
- In-memory transformations (seconds)
- Ephemeral state
- Type-safe, synchronous

**Use both:** Workflow engine calls Pipeline for in-memory transformations

---

## Testing

From [`tests/unit/domain/test_pipeline.py`](../../tests/unit/domain/test_pipeline.py):

```python
class TestPipeline:
    """Test pipeline orchestration and computed properties."""
    
    def test_empty_pipeline_not_succeeded(self):
        """Empty pipeline hasn't succeeded (nothing executed)."""
        pipeline = Pipeline()
        assert not pipeline.succeeded
        assert not pipeline.failed
    
    def test_all_success_means_succeeded(self):
        """All SuccessStage instances means pipeline succeeded."""
        pipeline = Pipeline()
        
        stage1 = SuccessStage(
            status=StageStatus.SUCCESS,
            category=StageCategory.PARSING,
            name=StageName("parse"),
            data=ParsedData(tokens=["hello"]),
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC)
        )
        
        stage2 = SuccessStage(
            status=StageStatus.SUCCESS,
            category=StageCategory.ENRICHMENT,
            name=StageName("enrich"),
            data=EnrichedData(keywords=["greeting"]),
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC)
        )
        
        pipeline = pipeline.append(stage1).append(stage2)
        
        assert pipeline.succeeded
        assert not pipeline.failed
        assert len(pipeline.stages) == 2
    
    def test_any_failure_means_failed(self):
        """Any FailedStage means pipeline failed."""
        pipeline = Pipeline()
        
        success = SuccessStage(
            status=StageStatus.SUCCESS,
            category=StageCategory.PARSING,
            name=StageName("parse"),
            data=ParsedData(tokens=["hello"]),
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC)
        )
        
        failed = FailedStage(
            status=StageStatus.FAILED,
            category=StageCategory.ENRICHMENT,
            error_category=ErrorCategory.EXTERNAL_SERVICE,
            name=StageName("enrich"),
            error=ErrorMessage("API timeout"),
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC)
        )
        
        pipeline = pipeline.append(success).append(failed)
        
        assert not pipeline.succeeded
        assert pipeline.failed
        assert pipeline.error_summary.total_errors == 1
    
    def test_latest_data_raises_if_no_success(self):
        """latest_data property raises if no successful stages."""
        pipeline = Pipeline()
        
        with pytest.raises(ValueError, match="No successful stages"):
            _ = pipeline.latest_data
```

**Testing strategy:**
- Test discriminated union behavior (isinstance checks)
- Test computed properties (error_summary, succeeded, failed)
- Test immutability (frozen=True enforcement)
- Test model validators (SkippedStage conditional requirements)

---

## Related Patterns

- **[Type System: Discriminated Unions](type-system.md#discriminated-unions-type-safe-dispatch)** - How Stage union works
- **[Type System: RootModel](type-system.md#semantic-types-for-observability)** - Semantic types pattern
- **[Type System: Model Validators](type-system.md#conditional-requirements)** - Cross-field validation
- **[Domain Models](domain-models.md)** - Domain primitives vs aggregates
- **[Immutability](immutability.md)** - Why frozen=True and tuple matter
- **[Data Flow](data-flow.md#the-pipeline-domain-model)** - Pipeline in data transformation context

---

## When to Create Your Own Domain Primitive

Pipeline demonstrates the pattern. When should you create similar abstractions?

**Create a domain primitive when:**
- ✅ Reusable abstraction needed across multiple domains
- ✅ No identity (two instances with same data are equal)
- ✅ No lifecycle (no create/update/delete operations)
- ✅ Users compose directly (no service layer)
- ✅ Ephemeral (computed, not persisted as entity)

**Examples:**
- `Money` - amount + currency with arithmetic operations
- `DateRange` - start + end with overlap checking
- `EmailAddress` - validated email with domain extraction
- `Pipeline` - multi-stage transformations with observability

**Don't create when:**
- ❌ Needs persistence as entity (use aggregate)
- ❌ Has identity (use aggregate root)
- ❌ Needs service coordination (use aggregate + service)
- ❌ One-off pattern (inline the logic)

---

## Summary

**Pipeline is a domain primitive that demonstrates:**
1. **Discriminated unions** for type-safe multi-outcome operations
2. **RootModel wrappers** for semantic types with validation
3. **Model validators** for conditional cross-field requirements
4. **Computed properties** for derived observable state
5. **Immutability** for safe concurrent access and traceability
6. **Rich behavior** in domain models (not services)

**Use it as:**
- A working example of advanced Pydantic patterns
- A template for building your own domain primitives
- A practical tool for multi-stage transformations

**Remember:**
- Pipeline is a library, not a framework
- Users compose it directly into workflows
- It's ephemeral, not persisted
- It teaches by example

---

**For more details:**
- [`src/app/domain/pipeline.py`](../../src/app/domain/pipeline.py) - Full implementation (775 lines)
- [`tests/unit/domain/test_pipeline.py`](../../tests/unit/domain/test_pipeline.py) - Comprehensive test suite
- [`src/app/domain/domain_type.py`](../../src/app/domain/domain_type.py) - Enum definitions

