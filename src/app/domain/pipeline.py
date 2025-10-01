"""Pipeline Domain Models - Type-Safe Transformation Tracking.

This module provides a generic pipeline abstraction for tracking multi-stage
data transformations with rich observability and type safety.

Key Concepts:
    - Discriminated unions for type-safe stage outcomes (Success/Failed/Skipped)
    - Immutable transformations with explicit state progression
    - Semantic types via RootModel wrappers for Logfire observability
    - Smart enums for categorization and error grouping

Architecture Pattern:
    Users compose these primitives into domain-specific pipelines.
    No service layer needed - this is a library abstraction like tuple or dict.

Example Usage:
    >>> # Define your data models
    >>> class ParsedDoc(BaseModel):
    ...     tokens: list[str]
    ...
    >>> # Build pipeline with explicit stages
    >>> pipeline = Pipeline()
    >>> stage = SuccessStage(
    ...     status=StageStatus.SUCCESS,
    ...     category=StageCategory.PARSING,
    ...     name=StageName("parse"),
    ...     data=ParsedDoc(tokens=["hello", "world"]),
    ...     start_time=start,
    ...     end_time=end
    ... )
    >>> pipeline = pipeline.append(stage)
    >>> # Rich observability
    >>> print(f"Total duration: {pipeline.total_duration_ms}ms")
    >>> print(f"Errors: {pipeline.error_summary.total_errors}")
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, computed_field, model_validator

from .domain_type import ErrorCategory, SkipReason, StageCategory, StageStatus


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

    Why RootModel?
        Provides semantic meaning without field overhead. A StageName is
        conceptually just a string, but with domain validation and type
        distinction in traces.

    Example:
        >>> name = StageName("parse-documents")
        >>> print(name.root)  # "parse-documents"
        >>> StageName("invalid name!")  # Raises ValidationError
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

    Example:
        >>> error = ErrorMessage("Database connection timeout after 30s")
        >>> failed_stage = FailedStage(
        ...     ...,
        ...     error=error,
        ...     error_category=ErrorCategory.TIMEOUT
        ... )
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

    Example:
        >>> reason = CustomSkipReason("User disabled email notifications in preferences")
        >>> skipped = SkippedStage(
        ...     skip_reason=SkipReason.CUSTOM,
        ...     custom_reason=reason,  # Required when CUSTOM
        ...     ...
        ... )
    """

    root: str = Field(min_length=1, max_length=500)
    model_config = ConfigDict(frozen=True)


class ErrorSummary(RootModel[dict[ErrorCategory, int]]):
    """Error count distribution by category for observability and alerting.

    Aggregates FailedStage instances by ErrorCategory to enable:
        - Dashboard queries: "Show me all validation errors this week"
        - Alerting: "Notify if timeout errors > 10"
        - Pattern detection: "Why did this pipeline fail?"

    Why not just dict?
        Computed properties (total_errors, most_common) add intelligence.
        Semantic type makes Logfire traces more meaningful.
        Validates structure at construction.

    Computed Properties:
        total_errors: Sum of all error counts across categories
        most_common: Category with highest count (for quick diagnosis)

    Example:
        >>> summary = pipeline.error_summary
        >>> print(f"Total: {summary.total_errors}")
        >>> print(f"Worst: {summary.most_common}")
        >>> if summary.root[ErrorCategory.TIMEOUT] > 5:
        ...     alert("High timeout rate detected")
    """

    root: dict[ErrorCategory, int] = Field(default_factory=dict)
    model_config = ConfigDict(frozen=True)

    @computed_field
    @property
    def total_errors(self) -> int:
        """Total failed stages across all categories.

        Returns:
            Sum of all error counts. Zero if no failures.
        """
        return sum(self.root.values())

    @computed_field
    @property
    def most_common(self) -> ErrorCategory | None:
        """Most frequent error category for quick diagnosis.

        Returns:
            ErrorCategory with highest count, or None if no errors.
            When tied, returns one deterministically based on dict order.
        """
        if not self.root:
            return None
        return max(self.root.items(), key=lambda x: x[1])[0]


class LogfireAttributes(RootModel[dict[str, Any]]):
    """Pipeline state exported as Logfire span attributes.

    Wraps dict[str, Any] to:
        - Provide semantic type for span attributes
        - Ensure consistent structure across pipeline traces
        - Enable type-safe unpacking into logfire.span()

    Structure (keys always present):
        - pipeline.total_stages: int
        - pipeline.succeeded: bool
        - pipeline.failed: bool
        - pipeline.total_duration_ms: float
        - pipeline.stage_flow: list[str] (category values)
        - pipeline.error_summary: dict[str, int] (category -> count)

    Why wrap dict[str, Any]?
        Logfire span attributes must be dict[str, Any] (protocol requirement).
        Wrapping provides type safety while maintaining compatibility.

    Example:
        >>> attrs = pipeline.to_logfire_attributes()
        >>> with logfire.span("pipeline_exec", **attrs.root):
        ...     # Pipeline state visible in trace
        ...     pass
    """

    root: dict[str, Any]
    model_config = ConfigDict(frozen=True)


class SuccessStage(BaseModel):
    """Successful pipeline stage with validated output data.

    Part of Stage discriminated union (Success | Failed | Skipped).
    Pydantic dispatches on 'status' field to determine concrete type.

    Represents:
        - Transformation completed successfully
        - Output data available and validated
        - Execution time tracked via timestamps

    Why Literal[StageStatus.SUCCESS]?
        Enables type narrowing. When isinstance(stage, SuccessStage),
        type checker knows status is SUCCESS and data field exists.
        This is type-safe dispatch at runtime.

    Attributes:
        status: Always SUCCESS (discriminator field)
        category: What kind of transformation (for observability)
        name: Stage identifier (semantic type)
        data: Validated output model (must be BaseModel subclass)
        start_time: When stage execution began
        end_time: When stage execution completed

    Computed Properties:
        duration_ms: Execution time derived from timestamps

    Example:
        >>> stage = SuccessStage(
        ...     status=StageStatus.SUCCESS,
        ...     category=StageCategory.PARSING,
        ...     name=StageName("parse-xml"),
        ...     data=ParsedDocument(nodes=[...]),
        ...     start_time=start,
        ...     end_time=end
        ... )
        >>> print(f"Parsed in {stage.duration_ms}ms")
    """

    status: Literal[StageStatus.SUCCESS]  # Discriminator for union type
    category: StageCategory  # What kind of transformation
    name: StageName  # Stage identifier (validated)
    data: BaseModel  # Output data (must be Pydantic model)
    start_time: datetime  # Execution start
    end_time: datetime  # Execution complete

    model_config = ConfigDict(frozen=True)

    @computed_field
    @property
    def duration_ms(self) -> float:
        """Execution duration computed from timestamps.

        Why computed vs stored?
            Single source of truth: timestamps are authoritative.
            Can't drift: duration always correct relative to times.
            Pydantic caches on frozen models: computed once, reused.

        Returns:
            Milliseconds between start_time and end_time.
        """
        delta = self.end_time - self.start_time
        return delta.total_seconds() * 1000


class FailedStage(BaseModel):
    """Failed pipeline stage with categorized error for debugging.

    Part of Stage discriminated union (Success | Failed | Skipped).
    Pydantic dispatches on 'status' field to determine concrete type.

    Represents:
        - Transformation failed with error
        - No output data available
        - Error categorized for grouping/alerting
        - Execution time tracked (how long until failure)

    Why two categories (category + error_category)?
        category: What was being attempted (parsing, enrichment, etc.)
        error_category: Why it failed (timeout, validation, etc.)
        This dual categorization enables queries like:
        "Show me all timeout errors in enrichment stages"

    Attributes:
        status: Always FAILED (discriminator field)
        category: What transformation was attempted
        error_category: Type of error for grouping (timeout, validation, etc.)
        name: Stage identifier
        error: Human-readable error message (required, validated)
        start_time: When stage execution began
        end_time: When failure occurred

    Computed Properties:
        duration_ms: Time until failure (for timeout analysis)

    Example:
        >>> stage = FailedStage(
        ...     status=StageStatus.FAILED,
        ...     category=StageCategory.ENRICHMENT,
        ...     error_category=ErrorCategory.EXTERNAL_SERVICE,
        ...     name=StageName("geocode"),
        ...     error=ErrorMessage("API rate limit exceeded (429)"),
        ...     start_time=start,
        ...     end_time=end
        ... )
        >>> if stage.error_category == ErrorCategory.EXTERNAL_SERVICE:
        ...     retry_with_backoff()
    """

    status: Literal[StageStatus.FAILED]  # Discriminator for union type
    category: StageCategory  # What was being attempted
    error_category: ErrorCategory  # Why it failed (for grouping)
    name: StageName  # Stage identifier (validated)
    error: ErrorMessage  # Required error description
    start_time: datetime  # Execution start
    end_time: datetime  # When failure occurred

    model_config = ConfigDict(frozen=True)

    @computed_field
    @property
    def duration_ms(self) -> float:
        """Time from start until failure occurred.

        Useful for:
            - Timeout analysis: Did we fail early or late?
            - Performance profiling: Which stages are slowest before failing?
            - Resource analysis: Partial work completed before error

        Returns:
            Milliseconds from start_time to end_time (failure point).
        """
        delta = self.end_time - self.start_time
        return delta.total_seconds() * 1000


class SkippedStage(BaseModel):
    """Skipped pipeline stage with categorized reason for conditional execution.

    Part of Stage discriminated union (Success | Failed | Skipped).
    Pydantic dispatches on 'status' field to determine concrete type.

    Represents:
        - Stage intentionally bypassed (not an error)
        - Reason categorized for observability
        - No execution time (instant decision)

    When to Skip vs Fail?
        Skip: Conditional logic (feature flags, already processed)
        Fail: Unexpected error during execution
        Skips are normal control flow. Failures are problems.

    Model Validator Enforces:
        - If skip_reason is CUSTOM → custom_reason REQUIRED
        - If skip_reason is not CUSTOM → custom_reason FORBIDDEN
        This prevents ambiguous skip states at construction time.

    Attributes:
        status: Always SKIPPED (discriminator field)
        category: What transformation was considered
        name: Stage identifier
        skip_reason: Standard reason enum
        custom_reason: Free-text reason (only when CUSTOM)
        timestamp: When skip decision was made (UTC)

    Example:
        >>> # Standard skip reason
        >>> skipped = SkippedStage(
        ...     status=StageStatus.SKIPPED,
        ...     category=StageCategory.NOTIFICATION,
        ...     name=StageName("send-email"),
        ...     skip_reason=SkipReason.DISABLED,
        ...     custom_reason=None  # Not allowed with DISABLED
        ... )
        >>>
        >>> # Custom skip reason
        >>> skipped = SkippedStage(
        ...     status=StageStatus.SKIPPED,
        ...     category=StageCategory.ENRICHMENT,
        ...     name=StageName("geocode"),
        ...     skip_reason=SkipReason.CUSTOM,
        ...     custom_reason=CustomSkipReason("Address already geocoded in cache")
        ... )
    """

    status: Literal[StageStatus.SKIPPED]  # Discriminator for union type
    category: StageCategory  # What was being considered
    name: StageName  # Stage identifier (validated)
    skip_reason: SkipReason  # Standard reason enum
    custom_reason: CustomSkipReason | None = None  # Only with CUSTOM
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))  # When skipped

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

        Validation happens after field validation, so we can rely on
        skip_reason being a valid SkipReason enum value.

        Raises:
            ValueError: If rules violated
        """
        if self.skip_reason == SkipReason.CUSTOM and self.custom_reason is None:
            raise ValueError("custom_reason required when skip_reason is CUSTOM")
        if self.skip_reason != SkipReason.CUSTOM and self.custom_reason is not None:
            raise ValueError("custom_reason only allowed when skip_reason is CUSTOM")
        return self


# Discriminated Union: Type-Safe Stage Dispatch
# -----------------------------------------------
# Stage = SuccessStage | FailedStage | SkippedStage
#
# Pydantic automatically dispatches on the 'status' field (discriminator).
# When deserializing: {"status": "success", ...} → SuccessStage instance
# When type checking: isinstance(stage, SuccessStage) → narrows to SuccessStage
#
# Why this pattern?
#   - Type safety: Can't access .data on FailedStage (doesn't exist)
#   - Exhaustiveness: Type checker ensures all cases handled
#   - No type: ignore needed: Discriminated union eliminates ambiguity
#   - Self-documenting: Each outcome has its own schema
#
# Alternative patterns we rejected:
#   - Single Stage class with Optional fields → allows invalid states
#   - Separate hierarchies without union → loses type dispatch
#   - Generic Stage[T] → complex, doesn't help with failures
Stage = SuccessStage | FailedStage | SkippedStage


class Pipeline(BaseModel):
    """Immutable pipeline orchestrator tracking multi-stage transformations.

    Core abstraction for type-safe, observable data transformation pipelines.
    Accumulates Stage discriminated unions as execution progresses.

    Design Principles:
        1. Immutability: append() returns new Pipeline, original unchanged
        2. Type Safety: Stages validated at construction, no raw data
        3. Observability: Rich metadata for Logfire tracing
        4. Composability: Build domain-specific pipelines from primitives

    Architecture Pattern:
        This is a domain primitive, not a framework. Like tuple or dict,
        users compose it into their specific pipelines. No service layer
        needed - business logic lives in your transformation functions.

    Attributes:
        stages: Tuple of Stage discriminated union (Success/Failed/Skipped)
                Tuple enforces immutability - can't accidentally mutate.

    Computed Properties:
        succeeded: All stages succeeded (no failures)
        failed: Any stage failed
        error_summary: ErrorCategory distribution (for alerting)
        stage_categories: Execution flow topology (for visualization)
        total_duration_ms: Pipeline execution time

    Regular Properties:
        latest_stage: Most recent stage (any type)
        latest_success: Most recent successful stage
        latest_data: Extract data from latest_success (raises if none)

    Methods:
        append: Add stage immutably
        to_logfire_attributes: Export for tracing

    Example:
        >>> # Define transformation stages
        >>> def parse_stage(raw: RawInput) -> SuccessStage | FailedStage:
        ...     start = datetime.now(UTC)
        ...     try:
        ...         parsed = parse(raw)
        ...         return SuccessStage(
        ...             status=StageStatus.SUCCESS,
        ...             category=StageCategory.PARSING,
        ...             name=StageName("parse"),
        ...             data=parsed,
        ...             start_time=start,
        ...             end_time=datetime.now(UTC)
        ...         )
        ...     except Exception as e:
        ...         return FailedStage(
        ...             status=StageStatus.FAILED,
        ...             category=StageCategory.PARSING,
        ...             error_category=ErrorCategory.VALIDATION,
        ...             name=StageName("parse"),
        ...             error=ErrorMessage(str(e)),
        ...             start_time=start,
        ...             end_time=datetime.now(UTC)
        ...         )
        >>>
        >>> # Execute pipeline
        >>> pipeline = Pipeline()
        >>> stage = parse_stage(raw_input)
        >>> pipeline = pipeline.append(stage)
        >>>
        >>> # Check results
        >>> if pipeline.succeeded:
        ...     result = pipeline.latest_data
        >>> else:
        ...     print(f"Errors: {pipeline.error_summary.total_errors}")
    """

    stages: tuple[Stage, ...] = ()  # Immutable collection

    model_config = ConfigDict(frozen=True)

    def append(self, stage: Stage) -> Pipeline:
        """Append stage immutably, returning new Pipeline instance.

        Immutability Pattern:
            Original pipeline unchanged. Returns new Pipeline with stage added.
            This enables time-travel debugging and safe concurrent access.

        Args:
            stage: SuccessStage, FailedStage, or SkippedStage instance.
                   Caller constructs the appropriate type based on outcome.

        Returns:
            New Pipeline with stage appended to stages tuple.

        Example:
            >>> pipeline = Pipeline()
            >>> stage = SuccessStage(
            ...     status=StageStatus.SUCCESS,
            ...     category=StageCategory.PARSING,
            ...     name=StageName("parse"),
            ...     data=ParsedModel(...),
            ...     start_time=datetime.now(UTC),
            ...     end_time=datetime.now(UTC)
            ... )
            >>> pipeline = pipeline.append(stage)  # Reassign to capture new instance
            >>> assert len(pipeline.stages) == 1
        """
        # Tuple unpacking creates new tuple with appended stage
        # model_copy returns new Pipeline instance (frozen=True prevents mutation)
        return self.model_copy(update={"stages": (*self.stages, stage)})

    @computed_field
    @property
    def succeeded(self) -> bool:
        """True if all stages succeeded (no failures, at least one stage).

        Logic:
            Empty pipeline → False (nothing executed)
            All SuccessStage → True
            Any FailedStage → False
            Skipped stages don't affect success (conditional logic is normal)

        Returns:
            True if pipeline has stages and all are SuccessStage.
        """
        if not self.stages:
            return False  # Empty pipeline hasn't succeeded
        # Discriminated union: isinstance narrows to SuccessStage
        return all(isinstance(stage, SuccessStage) for stage in self.stages)

    @computed_field
    @property
    def failed(self) -> bool:
        """True if any stage failed (one failure fails the pipeline).

        Logic:
            Empty pipeline → False (nothing failed yet)
            Any FailedStage → True
            All Success/Skipped → False

        Returns:
            True if any stage is FailedStage.
        """
        # Discriminated union: isinstance narrows to FailedStage
        return any(isinstance(stage, FailedStage) for stage in self.stages)

    @computed_field
    @property
    def error_summary(self) -> ErrorSummary:
        """Aggregate errors by category for observability and alerting.

        Extracts ErrorCategory from all FailedStage instances and counts them.
        Enables Logfire queries like:
            - "How many validation errors this week?"
            - "Alert if timeout errors > threshold"

        Returns:
            ErrorSummary with category distribution and computed properties.
            Empty dict if no failures.

        Example:
            >>> summary = pipeline.error_summary
            >>> if summary.total_errors > 10:
            ...     alert(f"High error rate: {summary.most_common}")
        """
        # Extract error categories from failed stages only
        # Discriminated union: isinstance(stage, FailedStage) guarantees error_category exists
        errors = [stage.error_category for stage in self.stages if isinstance(stage, FailedStage)]
        # Counter builds dict[ErrorCategory, int], wrapped in ErrorSummary RootModel
        return ErrorSummary(dict(Counter(errors)))

    @computed_field
    @property
    def stage_categories(self) -> tuple[StageCategory, ...]:
        """Ordered sequence of stage categories for flow visualization.

        Extracts StageCategory from each stage to show pipeline topology.
        Useful for Logfire trace visualization: see execution path at a glance.

        Example Flow:
            (INGESTION, VALIDATION, PARSING, ENRICHMENT, PERSISTENCE)
            Shows this pipeline ingests → validates → parses → enriches → persists

        Returns:
            Tuple of StageCategory in execution order.
            Empty tuple if no stages.
        """
        return tuple(stage.category for stage in self.stages)

    @computed_field
    @property
    def total_duration_ms(self) -> float:
        """Total pipeline execution time (sum of all executed stages).

        Aggregation Logic:
            - SuccessStage: Include duration_ms
            - FailedStage: Include duration_ms (time until failure)
            - SkippedStage: Exclude (instant decision, no execution)

        Returns:
            Total milliseconds spent in executed stages. Zero if no stages.
        """
        total = 0.0
        for stage in self.stages:
            # Discriminated union: isinstance narrows types
            # Both Success and Failed have duration_ms computed property
            if isinstance(stage, (SuccessStage, FailedStage)):
                total += stage.duration_ms
        return total

    @property
    def latest_stage(self) -> Stage | None:
        """Most recent stage regardless of outcome.

        Returns:
            Last stage in pipeline, or None if empty.
            Return type is Stage union (Success | Failed | Skipped).

        Example:
            >>> if (stage := pipeline.latest_stage):
            ...     if isinstance(stage, FailedStage):
            ...         log_error(stage.error)
        """
        return self.stages[-1] if self.stages else None

    @property
    def latest_success(self) -> SuccessStage | None:
        """Most recent successful stage (walks backward from end).

        Useful for extracting data after mixed success/skip/fail sequence.

        Returns:
            Most recent SuccessStage, or None if no successful stages.
            Type narrowed to SuccessStage (guaranteed to have .data).

        Example:
            >>> if (success := pipeline.latest_success):
            ...     process(success.data)  # Type-safe: .data exists
        """
        # Walk backward to find most recent success
        for stage in reversed(self.stages):
            if isinstance(stage, SuccessStage):
                return stage  # Type narrowed to SuccessStage
        return None

    @property
    def latest_data(self) -> BaseModel:
        """Extract data from most recent successful stage.

        Convenience method for common pattern: "give me the latest output".

        Raises:
            ValueError: If no successful stages exist in pipeline.
                       Use latest_success if None-safe access needed.

        Returns:
            BaseModel data from most recent SuccessStage.

        Example:
            >>> try:
            ...     result = pipeline.latest_data
            ...     process(result)
            ... except ValueError:
            ...     handle_pipeline_failure()
        """
        success = self.latest_success
        if success is None:
            raise ValueError("No successful stages in pipeline")
        return success.data  # Type-safe: isinstance narrowed to SuccessStage

    def to_logfire_attributes(self) -> LogfireAttributes:
        """Export pipeline state as structured Logfire span attributes.

        Converts Pipeline to dict[str, Any] suitable for logfire.span().
        All keys use "pipeline." prefix for consistent Logfire namespace.

        Exported Attributes:
            - pipeline.total_stages: Stage count (int)
            - pipeline.succeeded: All stages succeeded (bool)
            - pipeline.failed: Any stage failed (bool)
            - pipeline.total_duration_ms: Execution time (float)
            - pipeline.stage_flow: Execution path (list[str])
            - pipeline.error_summary: Error distribution (dict[str, int])

        Why export enums as .value?
            Logfire attributes must be JSON-serializable.
            Enums → strings for compatibility.

        Returns:
            LogfireAttributes wrapping dict ready for span unpacking.

        Example:
            >>> import logfire
            >>> pipeline = execute_pipeline(input_data)
            >>> attrs = pipeline.to_logfire_attributes()
            >>> with logfire.span("pipeline_exec", **attrs.root):
            ...     # Pipeline state visible in Logfire trace
            ...     if pipeline.failed:
            ...         logfire.error("Pipeline failed", error_count=attrs.root["pipeline.error_summary"])
        """
        return LogfireAttributes(
            {
                # Basic metrics
                "pipeline.total_stages": len(self.stages),
                "pipeline.succeeded": self.succeeded,  # Computed property
                "pipeline.failed": self.failed,  # Computed property
                "pipeline.total_duration_ms": self.total_duration_ms,  # Computed property
                # Flow visualization: list of stage categories in order
                "pipeline.stage_flow": [cat.value for cat in self.stage_categories],
                # Error distribution: category → count mapping
                # Convert enum keys to strings for JSON compatibility
                "pipeline.error_summary": {k.value: v for k, v in self.error_summary.root.items()},
            }
        )


__all__ = [
    "CustomSkipReason",
    "ErrorMessage",
    "ErrorSummary",
    "FailedStage",
    "LogfireAttributes",
    "Pipeline",
    "SkippedStage",
    "Stage",
    "StageName",
    "SuccessStage",
]
