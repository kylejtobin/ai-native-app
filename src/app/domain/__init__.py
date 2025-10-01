"""Domain Layer - Business Logic and Rich Models.

This module provides the core domain layer built on Pydantic AI's native types.
Architecture follows Domain-Driven Design with immutable models and pure functions.

Key Components:
    - Conversation: Main aggregate root for conversation lifecycle
    - ModelPool: Efficient caching of LLM client connections
    - ModelClassifier/ToolClassifier: Two-phase routing for intelligent model and tool selection
    - ConversationHistory: Immutable conversation state with persistence identity
    - ModelCatalog: Type-safe, configuration-driven LLM model management

Design Principles:
    - Pydantic AI Native: Use Pydantic AI types directly, minimal wrapping
    - Immutable by Default: All domain models use frozen=True for algebraic operations
    - Explicit Dependencies: No hidden state, all dependencies passed explicitly
    - Type-Safe Throughout: Leverage Pydantic's validation at every boundary
"""

from .conversation import (
    Conversation,
    ModelClassifier,
    RouteDecision,
    ToolClassifier,
    ToolDecision,
)
from .domain_type import AIModelVendor, ConversationStatus, ModelRoute
from .domain_value import ConversationHistory, ConversationId, MessageId, StoredMessage
from .model_catalog import (
    FastModelOverrides,
    ModelCapability,
    ModelCatalog,
    ModelRegistry,
    ModelSpec,
    ModelVariant,
    VendorCatalog,
)
from .model_pool import ModelPool
from .tools import ALL_TOOLS, calculator, tavily_search

__all__ = [
    "ALL_TOOLS",
    "AIModelVendor",
    "Conversation",
    "ConversationHistory",
    "ConversationId",
    "ConversationStatus",
    "FastModelOverrides",
    "MessageId",
    "ModelCapability",
    "ModelCatalog",
    "ModelClassifier",
    "ModelPool",
    "ModelRegistry",
    "ModelRoute",
    "ModelSpec",
    "ModelVariant",
    "RouteDecision",
    "StoredMessage",
    "ToolClassifier",
    "ToolDecision",
    "VendorCatalog",
    "calculator",
    "tavily_search",
]
