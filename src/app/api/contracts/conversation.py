# src/app/api/contracts/conversation.py
"""Conversation API contracts - use domain types directly."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ...domain.domain_value import ConversationId


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""

    text: str = Field(
        min_length=1,
        max_length=10_000,
        description="User message to send",
        examples=["What's happening in AI this week? Search the web."],
    )
    conversation_id: ConversationId | None = Field(
        default=None,
        description="Existing conversation ID to continue, or None to start new",
        examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    )
    model_id: str | None = Field(
        default=None,
        description="Optional model override in 'vendor:model_id' format (e.g. 'anthropic:claude-sonnet-4.5'). Leave empty for auto-routing.",
        examples=["anthropic:claude-sonnet-4.5"],
    )
    auto_route: bool = Field(
        default=True,
        description="Whether to use intelligent model routing (if configured)",
        examples=[True],
    )


class MessageResponse(BaseModel):
    """Response containing a single AI message."""

    content: str = Field(
        description="AI-generated response text",
    )


class SendMessageResponse(BaseModel):
    """Response from sending a message."""

    conversation_id: ConversationId = Field(
        description="Conversation ID for subsequent requests",
    )
    message: MessageResponse = Field(
        description="AI response message",
    )
    total_tokens: int = Field(
        ge=0,
        description="Total tokens used in conversation history",
    )


class ConversationHistoryResponse(BaseModel):
    """Response containing conversation history."""

    conversation_id: ConversationId
    message_count: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
