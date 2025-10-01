"""Domain Type System - Core Enumerations.

Defines type-safe constants using Python's StrEnum for domain concepts.
Using StrEnum instead of plain Enum provides automatic string coercion
and better JSON serialization without custom encoders.
"""

from enum import StrEnum


class AIModelVendor(StrEnum):
    """LLM Provider Identifiers.

    Supported vendors for model execution. These values are used as keys
    in the model catalog and for parsing model specifications in the format
    "vendor:model-id".

    Note:
        Adding new vendors requires corresponding entries in model_metadata.json
    """

    ANTHROPIC = "anthropic"
    OPENAI = "openai"


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


class StageStatus(StrEnum):
    """Outcome of any transformation stage."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


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
    """Standard reasons for skipping pipeline stages.

    Explicit categories for conditional execution logic.
    """

    CONDITION_NOT_MET = "condition_not_met"
    ALREADY_PROCESSED = "already_processed"
    DISABLED = "disabled"
    DEPENDENCY_FAILED = "dependency_failed"
    OPTIONAL = "optional"
    CUSTOM = "custom"


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


__all__ = [
    "AIModelVendor",
    "ConversationStatus",
    "ErrorCategory",
    "ModelRoute",
    "SkipReason",
    "StageCategory",
    "StageStatus",
]
