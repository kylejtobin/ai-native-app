"""
Shared test fixtures and configuration.

Environment strategy:
- Unit tests: Use .env.test (isolated, no real infra needed)
- Integration tests: Use .env (real Docker stack with actual credentials)
"""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import load_dotenv

# Determine which env file to use based on test type
# Integration tests need real infrastructure credentials
if "integration" in str(Path(__file__).parent):
    ENV_FILE = Path(__file__).parent.parent / ".env"
else:
    # Default to .env for all tests - integration tests need real stack
    ENV_FILE = Path(__file__).parent.parent / ".env"

load_dotenv(ENV_FILE, override=True)

from pydantic_ai.messages import ModelRequest, TextPart

from app.domain.conversation import ConversationHistory
from app.domain.domain_value import ConversationId, MessageId, StoredMessage


@pytest.fixture
def message_id() -> MessageId:
    """Generate a valid MessageId for testing."""
    return MessageId(uuid4())


@pytest.fixture
def conversation_id() -> ConversationId:
    """Generate a valid ConversationId for testing."""
    return ConversationId(uuid4())


@pytest.fixture
def stored_message(message_id: MessageId) -> StoredMessage:
    """Create a valid StoredMessage for testing."""
    return StoredMessage(
        id=message_id,
        content=ModelRequest(parts=[TextPart(content="Test message")]),
        timestamp=datetime.now(UTC),
    )


@pytest.fixture
def empty_history(conversation_id: ConversationId) -> ConversationHistory:
    """Create an empty ConversationHistory for testing."""
    return ConversationHistory(id=conversation_id, messages=())


@pytest.fixture
def history_with_messages(conversation_id: ConversationId, stored_message: StoredMessage) -> ConversationHistory:
    """Create a ConversationHistory with one message for testing."""
    return ConversationHistory(id=conversation_id, messages=()).append_message(stored_message)
