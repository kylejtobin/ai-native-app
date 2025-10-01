"""Identity Layer - Persistence Identities for Pydantic AI Content.

This module provides the identity layer that wraps Pydantic AI's content types
with our own UUID-based identifiers for persistence and reference.

Architecture:
    - Identity (our layer): MessageId, ConversationId
    - Content (Pydantic AI): ModelMessage (ModelRequest | ModelResponse)
    - Metadata (our layer): ConversationStatus, token tracking

This separation allows us to:
1. Store and retrieve conversations by ID
2. Reference specific messages for editing/deletion
3. Track aggregate state (status, token usage) without modifying Pydantic AI types
"""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, RootModel
from pydantic_ai.messages import ModelMessage, ModelResponse

from .domain_type import ConversationStatus


class MessageId(RootModel[UUID]):
    """Unique Identifier for Individual Messages.

    Uses Pydantic's RootModel pattern to create a strongly-typed UUID wrapper.
    This provides type safety while maintaining UUID behavior for persistence.

    Usage:
        >>> msg_id = MessageId()  # Auto-generates UUID
        >>> str(msg_id.root)  # Access underlying UUID
        '550e8400-e29b-41d4-a716-446655440000'

    Note:
        Frozen for use as dictionary keys and in immutable data structures
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
    content: ModelMessage
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)


class ConversationHistory(BaseModel):
    """Complete Conversation State for Persistence.

    The serializable aggregate representing an entire conversation. This model
    bridges our identity layer (IDs, status) with Pydantic AI's content layer
    (ModelMessage types).

    Attributes:
        id: Unique conversation identifier for persistence
        messages: Ordered tuple of messages (immutable for functional updates)
        status: Current lifecycle state (active, archived, deleted)

    Design Notes:
        - Immutable (frozen=True) for safe sharing across async contexts
        - Uses tuple instead of list to enforce immutability
        - Serializes cleanly to JSON for Redis/database storage
        - Compatible with Pydantic AI's message history requirements

    Example:
        >>> history = ConversationHistory(id=ConversationId())
        >>> history = history.append_message(user_msg)
        >>> await agent.run(message_history=list(history.message_content))
    """

    id: ConversationId
    messages: tuple[StoredMessage, ...] = ()
    status: ConversationStatus = ConversationStatus.ACTIVE

    model_config = ConfigDict(frozen=True)

    @property
    def message_content(self) -> tuple[ModelMessage, ...]:
        """Extract Pydantic AI Messages for Agent Execution.

        Strips away our identity layer to get the raw ModelMessage objects
        that Pydantic AI agents expect in message_history parameter.

        Returns:
            Tuple of ModelMessage objects ready for agent.run()
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

    def append_message(self, msg: StoredMessage) -> ConversationHistory:
        """Append Message Immutably.

        Functional update pattern: creates new ConversationHistory with added message.
        Original instance remains unchanged, enabling safe concurrent access.

        Args:
            msg: StoredMessage to append to conversation

        Returns:
            New ConversationHistory instance with message added

        Example:
            >>> history1 = ConversationHistory(id=ConversationId())
            >>> history2 = history1.append_message(msg)
            >>> len(history1.messages)  # 0 - original unchanged
            >>> len(history2.messages)  # 1 - new instance has message
        """
        return self.model_copy(update={"messages": (*self.messages, msg)})


__all__ = ["ConversationHistory", "ConversationId", "MessageId", "StoredMessage"]
