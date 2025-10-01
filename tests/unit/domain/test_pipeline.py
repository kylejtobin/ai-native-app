"""Unit tests for Pipeline domain models.

Tests focus on business logic, not Pydantic validation:
- Immutable state transformations
- Computed properties (duration, totals, summaries)
- Discriminated union behavior
- Model validator enforcement

No infrastructure dependencies - pure domain logic tests.
"""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import BaseModel, ValidationError

from app.domain.domain_type import ErrorCategory, SkipReason, StageCategory, StageStatus
from app.domain.pipeline import (
    CustomSkipReason,
    ErrorMessage,
    ErrorSummary,
    FailedStage,
    LogfireAttributes,
    Pipeline,
    SkippedStage,
    StageName,
    SuccessStage,
)


# Test fixtures - simple domain models for stage data
class ParsedData(BaseModel):
    """Test model for parsed stage output."""

    tokens: list[str]


class EnrichedData(BaseModel):
    """Test model for enriched stage output."""

    keywords: list[str]


# =============================================================================
# SuccessStage Tests
# =============================================================================


class TestSuccessStage:
    """Test successful stage behavior and computed properties."""

    def test_duration_computed_from_timestamps(self):
        """Verify duration_ms computed property calculates correctly."""
        start = datetime.now(UTC)
        end = start + timedelta(milliseconds=250.5)

        stage = SuccessStage(
            status=StageStatus.SUCCESS,
            category=StageCategory.PARSING,
            name=StageName("parse"),
            data=ParsedData(tokens=["hello", "world"]),
            start_time=start,
            end_time=end,
        )

        assert stage.duration_ms == 250.5

    def test_duration_handles_subsecond_precision(self):
        """Verify duration handles microsecond precision."""
        start = datetime.now(UTC)
        end = start + timedelta(milliseconds=42.123456)

        stage = SuccessStage(
            status=StageStatus.SUCCESS,
            category=StageCategory.TRANSFORMATION,
            name=StageName("transform"),
            data=ParsedData(tokens=["test"]),
            start_time=start,
            end_time=end,
        )

        assert abs(stage.duration_ms - 42.123456) < 0.001

    def test_frozen_prevents_mutation(self):
        """Verify frozen=True prevents field mutation."""
        stage = SuccessStage(
            status=StageStatus.SUCCESS,
            category=StageCategory.PARSING,
            name=StageName("parse"),
            data=ParsedData(tokens=["test"]),
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
        )

        with pytest.raises(ValidationError):
            stage.name = StageName("changed")  # type: ignore


# =============================================================================
# FailedStage Tests
# =============================================================================


class TestFailedStage:
    """Test failed stage behavior and error tracking."""

    def test_duration_computed_before_failure(self):
        """Verify duration_ms tracks time until failure occurred."""
        start = datetime.now(UTC)
        end = start + timedelta(milliseconds=150)

        stage = FailedStage(
            status=StageStatus.FAILED,
            category=StageCategory.PERSISTENCE,
            error_category=ErrorCategory.TIMEOUT,
            name=StageName("api-call"),
            error=ErrorMessage("Request timed out after 150ms"),
            start_time=start,
            end_time=end,
        )

        assert stage.duration_ms == 150.0

    def test_error_category_tracks_failure_type(self):
        """Verify error_category enables grouping failures."""
        validation_error = FailedStage(
            status=StageStatus.FAILED,
            category=StageCategory.VALIDATION,
            error_category=ErrorCategory.VALIDATION,
            name=StageName("validate"),
            error=ErrorMessage("Invalid schema"),
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
        )

        external_error = FailedStage(
            status=StageStatus.FAILED,
            category=StageCategory.PERSISTENCE,
            error_category=ErrorCategory.EXTERNAL_SERVICE,
            name=StageName("save"),
            error=ErrorMessage("Database connection failed"),
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
        )

        assert validation_error.error_category != external_error.error_category
        assert validation_error.error_category == ErrorCategory.VALIDATION
        assert external_error.error_category == ErrorCategory.EXTERNAL_SERVICE


# =============================================================================
# SkippedStage Tests
# =============================================================================


class TestSkippedStage:
    """Test skipped stage validation and reason tracking."""

    def test_requires_custom_reason_when_skip_reason_is_custom(self):
        """Verify model validator enforces custom_reason for CUSTOM skip_reason."""
        with pytest.raises(ValidationError, match="custom_reason required"):
            SkippedStage(
                status=StageStatus.SKIPPED,
                category=StageCategory.NOTIFICATION,
                name=StageName("notify"),
                skip_reason=SkipReason.CUSTOM,
                custom_reason=None,
            )

    def test_rejects_custom_reason_when_not_custom(self):
        """Verify custom_reason only allowed with CUSTOM skip_reason."""
        with pytest.raises(ValidationError, match="only allowed when skip_reason is CUSTOM"):
            SkippedStage(
                status=StageStatus.SKIPPED,
                category=StageCategory.NOTIFICATION,
                name=StageName("notify"),
                skip_reason=SkipReason.DISABLED,
                custom_reason=CustomSkipReason("Feature flag off"),
            )

    def test_accepts_custom_reason_with_custom_skip_reason(self):
        """Verify valid CUSTOM skip_reason with custom_reason."""
        stage = SkippedStage(
            status=StageStatus.SKIPPED,
            category=StageCategory.ENRICHMENT,
            name=StageName("enrich"),
            skip_reason=SkipReason.CUSTOM,
            custom_reason=CustomSkipReason("User opted out of enrichment"),
        )

        assert stage.skip_reason == SkipReason.CUSTOM
        assert stage.custom_reason.root == "User opted out of enrichment"

    def test_standard_skip_reasons_work_without_custom(self):
        """Verify standard skip reasons work without custom_reason."""
        stage = SkippedStage(
            status=StageStatus.SKIPPED,
            category=StageCategory.PERSISTENCE,
            name=StageName("save"),
            skip_reason=SkipReason.ALREADY_PROCESSED,
        )

        assert stage.skip_reason == SkipReason.ALREADY_PROCESSED
        assert stage.custom_reason is None


# =============================================================================
# ErrorSummary Tests
# =============================================================================


class TestErrorSummary:
    """Test error aggregation computed properties."""

    def test_total_errors_sums_all_counts(self):
        """Verify total_errors aggregates across categories."""
        summary = ErrorSummary(
            {
                ErrorCategory.VALIDATION: 3,
                ErrorCategory.TIMEOUT: 2,
                ErrorCategory.EXTERNAL_SERVICE: 1,
            }
        )

        assert summary.total_errors == 6

    def test_total_errors_zero_when_empty(self):
        """Verify total_errors returns 0 for empty summary."""
        summary = ErrorSummary({})

        assert summary.total_errors == 0

    def test_most_common_returns_highest_count_category(self):
        """Verify most_common identifies most frequent error."""
        summary = ErrorSummary(
            {
                ErrorCategory.VALIDATION: 5,
                ErrorCategory.TIMEOUT: 2,
                ErrorCategory.TRANSFORMATION: 1,
            }
        )

        assert summary.most_common == ErrorCategory.VALIDATION

    def test_most_common_returns_none_when_empty(self):
        """Verify most_common handles empty summary gracefully."""
        summary = ErrorSummary({})

        assert summary.most_common is None

    def test_most_common_handles_ties_deterministically(self):
        """Verify most_common returns one category when tied."""
        summary = ErrorSummary(
            {
                ErrorCategory.TIMEOUT: 3,
                ErrorCategory.VALIDATION: 3,
            }
        )

        # Returns one of them (dict iteration order dependent)
        assert summary.most_common in [ErrorCategory.TIMEOUT, ErrorCategory.VALIDATION]


# =============================================================================
# Pipeline Tests
# =============================================================================


class TestPipeline:
    """Test pipeline orchestration and aggregation logic."""

    def test_append_returns_new_instance(self):
        """Verify append immutably adds stage to pipeline."""
        pipeline = Pipeline()
        stage = SuccessStage(
            status=StageStatus.SUCCESS,
            category=StageCategory.PARSING,
            name=StageName("parse"),
            data=ParsedData(tokens=["hello"]),
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
        )

        new_pipeline = pipeline.append(stage)

        assert new_pipeline is not pipeline
        assert len(new_pipeline.stages) == 1
        assert len(pipeline.stages) == 0
        assert new_pipeline.stages[0] == stage

    def test_multiple_appends_chain_immutably(self):
        """Verify multiple appends create distinct instances."""
        pipeline = Pipeline()
        stage1 = SuccessStage(
            status=StageStatus.SUCCESS,
            category=StageCategory.PARSING,
            name=StageName("parse"),
            data=ParsedData(tokens=["hello"]),
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
        )
        stage2 = SuccessStage(
            status=StageStatus.SUCCESS,
            category=StageCategory.ENRICHMENT,
            name=StageName("enrich"),
            data=EnrichedData(keywords=["greeting"]),
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
        )

        pipeline1 = pipeline.append(stage1)
        pipeline2 = pipeline1.append(stage2)

        assert len(pipeline.stages) == 0
        assert len(pipeline1.stages) == 1
        assert len(pipeline2.stages) == 2

    def test_succeeded_true_when_all_stages_success(self):
        """Verify succeeded returns True when no failures."""
        pipeline = Pipeline()
        pipeline = pipeline.append(
            SuccessStage(
                status=StageStatus.SUCCESS,
                category=StageCategory.PARSING,
                name=StageName("parse"),
                data=ParsedData(tokens=[]),
                start_time=datetime.now(UTC),
                end_time=datetime.now(UTC),
            )
        )
        pipeline = pipeline.append(
            SuccessStage(
                status=StageStatus.SUCCESS,
                category=StageCategory.ENRICHMENT,
                name=StageName("enrich"),
                data=EnrichedData(keywords=[]),
                start_time=datetime.now(UTC),
                end_time=datetime.now(UTC),
            )
        )

        assert pipeline.succeeded is True
        assert pipeline.failed is False

    def test_succeeded_false_when_any_stage_fails(self):
        """Verify succeeded returns False when any stage fails."""
        pipeline = Pipeline()
        pipeline = pipeline.append(
            SuccessStage(
                status=StageStatus.SUCCESS,
                category=StageCategory.PARSING,
                name=StageName("parse"),
                data=ParsedData(tokens=[]),
                start_time=datetime.now(UTC),
                end_time=datetime.now(UTC),
            )
        )
        pipeline = pipeline.append(
            FailedStage(
                status=StageStatus.FAILED,
                category=StageCategory.ENRICHMENT,
                error_category=ErrorCategory.TRANSFORMATION,
                name=StageName("enrich"),
                error=ErrorMessage("Transformation failed"),
                start_time=datetime.now(UTC),
                end_time=datetime.now(UTC),
            )
        )

        assert pipeline.succeeded is False
        assert pipeline.failed is True

    def test_succeeded_false_when_pipeline_empty(self):
        """Verify succeeded returns False for empty pipeline."""
        pipeline = Pipeline()

        assert pipeline.succeeded is False

    def test_failed_true_when_any_stage_failed(self):
        """Verify failed detects any FailedStage."""
        pipeline = Pipeline()
        pipeline = pipeline.append(
            FailedStage(
                status=StageStatus.FAILED,
                category=StageCategory.VALIDATION,
                error_category=ErrorCategory.VALIDATION,
                name=StageName("validate"),
                error=ErrorMessage("Invalid input"),
                start_time=datetime.now(UTC),
                end_time=datetime.now(UTC),
            )
        )

        assert pipeline.failed is True

    def test_error_summary_counts_by_category(self):
        """Verify error_summary groups failures correctly."""
        pipeline = Pipeline()
        pipeline = pipeline.append(
            FailedStage(
                status=StageStatus.FAILED,
                category=StageCategory.VALIDATION,
                error_category=ErrorCategory.VALIDATION,
                name=StageName("validate1"),
                error=ErrorMessage("Error 1"),
                start_time=datetime.now(UTC),
                end_time=datetime.now(UTC),
            )
        )
        pipeline = pipeline.append(
            FailedStage(
                status=StageStatus.FAILED,
                category=StageCategory.VALIDATION,
                error_category=ErrorCategory.VALIDATION,
                name=StageName("validate2"),
                error=ErrorMessage("Error 2"),
                start_time=datetime.now(UTC),
                end_time=datetime.now(UTC),
            )
        )
        pipeline = pipeline.append(
            FailedStage(
                status=StageStatus.FAILED,
                category=StageCategory.PERSISTENCE,
                error_category=ErrorCategory.TIMEOUT,
                name=StageName("api-call"),
                error=ErrorMessage("Timeout"),
                start_time=datetime.now(UTC),
                end_time=datetime.now(UTC),
            )
        )

        summary = pipeline.error_summary

        assert summary.root[ErrorCategory.VALIDATION] == 2
        assert summary.root[ErrorCategory.TIMEOUT] == 1
        assert summary.total_errors == 3
        assert summary.most_common == ErrorCategory.VALIDATION

    def test_error_summary_empty_when_no_failures(self):
        """Verify error_summary returns empty dict when all success."""
        pipeline = Pipeline()
        pipeline = pipeline.append(
            SuccessStage(
                status=StageStatus.SUCCESS,
                category=StageCategory.PARSING,
                name=StageName("parse"),
                data=ParsedData(tokens=[]),
                start_time=datetime.now(UTC),
                end_time=datetime.now(UTC),
            )
        )

        summary = pipeline.error_summary

        assert len(summary.root) == 0
        assert summary.total_errors == 0
        assert summary.most_common is None

    def test_stage_categories_preserves_execution_order(self):
        """Verify stage_categories tracks pipeline topology."""
        pipeline = Pipeline()
        pipeline = pipeline.append(
            SuccessStage(
                status=StageStatus.SUCCESS,
                category=StageCategory.PARSING,
                name=StageName("parse"),
                data=ParsedData(tokens=[]),
                start_time=datetime.now(UTC),
                end_time=datetime.now(UTC),
            )
        )
        pipeline = pipeline.append(
            SuccessStage(
                status=StageStatus.SUCCESS,
                category=StageCategory.ENRICHMENT,
                name=StageName("enrich"),
                data=EnrichedData(keywords=[]),
                start_time=datetime.now(UTC),
                end_time=datetime.now(UTC),
            )
        )
        pipeline = pipeline.append(
            SuccessStage(
                status=StageStatus.SUCCESS,
                category=StageCategory.PERSISTENCE,
                name=StageName("save"),
                data=ParsedData(tokens=[]),
                start_time=datetime.now(UTC),
                end_time=datetime.now(UTC),
            )
        )

        assert pipeline.stage_categories == (
            StageCategory.PARSING,
            StageCategory.ENRICHMENT,
            StageCategory.PERSISTENCE,
        )

    def test_total_duration_sums_executed_stages(self):
        """Verify total_duration_ms aggregates success and failed stages."""
        start = datetime.now(UTC)

        success = SuccessStage(
            status=StageStatus.SUCCESS,
            category=StageCategory.PARSING,
            name=StageName("parse"),
            data=ParsedData(tokens=[]),
            start_time=start,
            end_time=start + timedelta(milliseconds=100),
        )
        failed = FailedStage(
            status=StageStatus.FAILED,
            category=StageCategory.ENRICHMENT,
            error_category=ErrorCategory.TRANSFORMATION,
            name=StageName("enrich"),
            error=ErrorMessage("Failed"),
            start_time=start,
            end_time=start + timedelta(milliseconds=50),
        )

        pipeline = Pipeline()
        pipeline = pipeline.append(success)
        pipeline = pipeline.append(failed)

        assert pipeline.total_duration_ms == 150.0

    def test_total_duration_excludes_skipped_stages(self):
        """Verify total_duration_ms ignores skipped stages."""
        start = datetime.now(UTC)

        success = SuccessStage(
            status=StageStatus.SUCCESS,
            category=StageCategory.PARSING,
            name=StageName("parse"),
            data=ParsedData(tokens=[]),
            start_time=start,
            end_time=start + timedelta(milliseconds=100),
        )
        skipped = SkippedStage(
            status=StageStatus.SKIPPED,
            category=StageCategory.NOTIFICATION,
            name=StageName("notify"),
            skip_reason=SkipReason.DISABLED,
        )

        pipeline = Pipeline()
        pipeline = pipeline.append(success)
        pipeline = pipeline.append(skipped)

        assert pipeline.total_duration_ms == 100.0

    def test_latest_stage_returns_most_recent(self):
        """Verify latest_stage returns last appended stage."""
        stage1 = SuccessStage(
            status=StageStatus.SUCCESS,
            category=StageCategory.PARSING,
            name=StageName("parse"),
            data=ParsedData(tokens=[]),
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
        )
        stage2 = SuccessStage(
            status=StageStatus.SUCCESS,
            category=StageCategory.ENRICHMENT,
            name=StageName("enrich"),
            data=EnrichedData(keywords=[]),
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
        )

        pipeline = Pipeline()
        pipeline = pipeline.append(stage1)
        pipeline = pipeline.append(stage2)

        assert pipeline.latest_stage == stage2

    def test_latest_stage_none_when_empty(self):
        """Verify latest_stage returns None for empty pipeline."""
        pipeline = Pipeline()

        assert pipeline.latest_stage is None

    def test_latest_success_finds_most_recent_success(self):
        """Verify latest_success returns most recent SuccessStage."""
        success1 = SuccessStage(
            status=StageStatus.SUCCESS,
            category=StageCategory.PARSING,
            name=StageName("parse"),
            data=ParsedData(tokens=[]),
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
        )
        success2 = SuccessStage(
            status=StageStatus.SUCCESS,
            category=StageCategory.ENRICHMENT,
            name=StageName("enrich"),
            data=EnrichedData(keywords=[]),
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
        )
        failed = FailedStage(
            status=StageStatus.FAILED,
            category=StageCategory.PERSISTENCE,
            error_category=ErrorCategory.EXTERNAL_SERVICE,
            name=StageName("save"),
            error=ErrorMessage("Failed"),
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
        )

        pipeline = Pipeline()
        pipeline = pipeline.append(success1)
        pipeline = pipeline.append(success2)
        pipeline = pipeline.append(failed)

        assert pipeline.latest_success == success2
        assert pipeline.latest_success.name.root == "enrich"

    def test_latest_success_skips_failures_and_skips(self):
        """Verify latest_success ignores non-success stages."""
        success = SuccessStage(
            status=StageStatus.SUCCESS,
            category=StageCategory.PARSING,
            name=StageName("parse"),
            data=ParsedData(tokens=[]),
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
        )
        failed = FailedStage(
            status=StageStatus.FAILED,
            category=StageCategory.ENRICHMENT,
            error_category=ErrorCategory.TRANSFORMATION,
            name=StageName("enrich"),
            error=ErrorMessage("Failed"),
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
        )
        skipped = SkippedStage(
            status=StageStatus.SKIPPED,
            category=StageCategory.NOTIFICATION,
            name=StageName("notify"),
            skip_reason=SkipReason.DISABLED,
        )

        pipeline = Pipeline()
        pipeline = pipeline.append(success)
        pipeline = pipeline.append(failed)
        pipeline = pipeline.append(skipped)

        assert pipeline.latest_success == success

    def test_latest_success_none_when_no_success(self):
        """Verify latest_success returns None when no successful stages."""
        pipeline = Pipeline()
        pipeline = pipeline.append(
            FailedStage(
                status=StageStatus.FAILED,
                category=StageCategory.VALIDATION,
                error_category=ErrorCategory.VALIDATION,
                name=StageName("validate"),
                error=ErrorMessage("Failed"),
                start_time=datetime.now(UTC),
                end_time=datetime.now(UTC),
            )
        )

        assert pipeline.latest_success is None

    def test_latest_data_extracts_from_latest_success(self):
        """Verify latest_data returns data from most recent success."""
        data = ParsedData(tokens=["hello", "world"])
        success = SuccessStage(
            status=StageStatus.SUCCESS,
            category=StageCategory.PARSING,
            name=StageName("parse"),
            data=data,
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
        )

        pipeline = Pipeline()
        pipeline = pipeline.append(success)

        assert pipeline.latest_data == data

    def test_latest_data_raises_when_no_success(self):
        """Verify latest_data raises ValueError when no successful stages."""
        pipeline = Pipeline()
        pipeline = pipeline.append(
            FailedStage(
                status=StageStatus.FAILED,
                category=StageCategory.VALIDATION,
                error_category=ErrorCategory.VALIDATION,
                name=StageName("validate"),
                error=ErrorMessage("Failed"),
                start_time=datetime.now(UTC),
                end_time=datetime.now(UTC),
            )
        )

        with pytest.raises(ValueError, match="No successful stages in pipeline"):
            _ = pipeline.latest_data

    def test_to_logfire_attributes_returns_wrapped_dict(self):
        """Verify to_logfire_attributes returns LogfireAttributes model."""
        pipeline = Pipeline()
        pipeline = pipeline.append(
            SuccessStage(
                status=StageStatus.SUCCESS,
                category=StageCategory.PARSING,
                name=StageName("parse"),
                data=ParsedData(tokens=[]),
                start_time=datetime.now(UTC),
                end_time=datetime.now(UTC),
            )
        )

        attrs = pipeline.to_logfire_attributes()

        assert isinstance(attrs, LogfireAttributes)
        assert isinstance(attrs.root, dict)

    def test_to_logfire_attributes_structure(self):
        """Verify Logfire attributes contain expected keys."""
        start = datetime.now(UTC)
        pipeline = Pipeline()
        pipeline = pipeline.append(
            SuccessStage(
                status=StageStatus.SUCCESS,
                category=StageCategory.PARSING,
                name=StageName("parse"),
                data=ParsedData(tokens=[]),
                start_time=start,
                end_time=start + timedelta(milliseconds=100),
            )
        )
        pipeline = pipeline.append(
            FailedStage(
                status=StageStatus.FAILED,
                category=StageCategory.ENRICHMENT,
                error_category=ErrorCategory.TRANSFORMATION,
                name=StageName("enrich"),
                error=ErrorMessage("Failed"),
                start_time=start,
                end_time=start + timedelta(milliseconds=50),
            )
        )

        attrs = pipeline.to_logfire_attributes()

        assert attrs.root["pipeline.total_stages"] == 2
        assert attrs.root["pipeline.succeeded"] is False
        assert attrs.root["pipeline.failed"] is True
        assert attrs.root["pipeline.total_duration_ms"] == 150.0
        assert attrs.root["pipeline.stage_flow"] == ["parsing", "enrichment"]
        assert attrs.root["pipeline.error_summary"] == {"transformation": 1}
