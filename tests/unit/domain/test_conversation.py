"""
Tests for ConversationHistory domain model.

These tests demonstrate:
- Testing immutability patterns (not testing frozen=True itself)
- Testing business logic (not testing Pydantic validation)
- Testing transformations (append, empty factory)
"""

from datetime import UTC, datetime
from uuid import uuid4

from pydantic_ai.messages import ModelRequest, TextPart

from app.domain.conversation import ConversationHistory
from app.domain.domain_value import ConversationId, MessageId, StoredMessage


def test_empty_creates_zero_length_history():
    """
    Demonstrates: Testing constructor behavior.

    We don't test that ConversationHistory validates its fields—that's Pydantic's job.
    We test that creating an empty history works correctly.
    """
    history = ConversationHistory(id=ConversationId(uuid4()), messages=())

    assert len(history.messages) == 0
    assert history.messages == ()  # Empty tuple, not None


def test_append_message_returns_new_instance():
    """
    Demonstrates: Testing immutability pattern without testing frozen=True.

    We're testing the business behavior (append returns new instance)
    not the mechanism (frozen=True raises on mutation).
    """
    history = ConversationHistory(id=ConversationId(uuid4()), messages=())
    message = StoredMessage(
        id=MessageId(uuid4()),
        content=ModelRequest(parts=[TextPart(content="Hello")]),
        timestamp=datetime.now(UTC),
    )

    new_history = history.append_message(message)

    # Core assertion: different instances
    assert new_history is not history
    # Business assertion: new instance has message
    assert len(new_history.messages) == 1
    # Immutability assertion: original unchanged
    assert len(history.messages) == 0


def test_append_message_preserves_existing_messages():
    """
    Demonstrates: Testing business logic (message ordering/preservation).

    This is domain behavior—messages accumulate in order.
    We don't test serialization or validation.
    """
    history = ConversationHistory(id=ConversationId(uuid4()), messages=())
    msg1 = StoredMessage(
        id=MessageId(uuid4()),
        content=ModelRequest(parts=[TextPart(content="First")]),
        timestamp=datetime.now(UTC),
    )
    msg2 = StoredMessage(
        id=MessageId(uuid4()),
        content=ModelRequest(parts=[TextPart(content="Second")]),
        timestamp=datetime.now(UTC),
    )

    history = history.append_message(msg1).append_message(msg2)

    assert len(history.messages) == 2
    assert history.messages[0] == msg1
    assert history.messages[1] == msg2


def test_append_multiple_messages_maintains_order():
    """
    Demonstrates: Testing domain invariant (append order).

    This tests our business rule: messages appear in the order appended.
    We trust Pydantic to handle tuple immutability.
    """
    history = ConversationHistory(id=ConversationId(uuid4()), messages=())
    messages = []

    # Append 5 messages
    for i in range(5):
        msg = StoredMessage(
            id=MessageId(uuid4()),
            content=ModelRequest(parts=[TextPart(content=f"Message {i}")]),
        )
        messages.append(msg)
        history = history.append_message(msg)

    assert len(history.messages) == 5

    # Verify order is maintained (same order as appended)
    for i in range(5):
        assert history.messages[i] == messages[i]
