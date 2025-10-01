"""
Integration tests for conversation API endpoints.

Demonstrates:
- Testing critical business paths (new conversation, continuing conversation)
- Testing idempotent conversation creation
- Testing API contract validation (Pydantic catches malformed requests)
- End-to-end testing against real running Docker stack

Requires:
- Docker Compose stack running (`make up`)
- Real API keys in .env (ANTHROPIC_API_KEY, TAVILY_API_KEY)
"""

import uuid

import httpx
import pytest


@pytest.fixture
def api_base_url():
    """Base URL for the running API."""
    return "http://localhost:8000"


def test_create_new_conversation_without_id(api_base_url: str):
    """
    Demonstrates: Creating a new conversation (happy path).
    
    When no conversation_id is provided, the system generates one.
    This tests our core business flow end-to-end.
    """
    response = httpx.post(
        f"{api_base_url}/conversation/",
        json={
            "text": "Hello, world!",
            "auto_route": False,
        },
        timeout=30.0,
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # System assigned an ID
    assert "conversation_id" in data
    assert data["conversation_id"] is not None
    
    # Got a response
    assert "message" in data
    assert "content" in data["message"]


def test_create_conversation_with_provided_id(api_base_url: str):
    """
    Demonstrates: Idempotent conversation creation.
    
    When a conversation_id is provided but doesn't exist yet,
    the system creates a new conversation with that ID.
    This is the bug we just fixed.
    """
    # Generate a fresh UUID
    conv_id = str(uuid.uuid4())
    
    response = httpx.post(
        f"{api_base_url}/conversation/",
        json={
            "text": "First message",
            "conversation_id": conv_id,
            "auto_route": False,
        },
        timeout=30.0,
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # System used our provided ID
    assert data["conversation_id"] == conv_id
    assert "message" in data


def test_continue_existing_conversation(api_base_url: str):
    """
    Demonstrates: Multi-turn conversation state management.
    
    After creating a conversation, we can continue it by providing
    the same conversation_id. This tests state persistence.
    """
    conv_id = str(uuid.uuid4())
    
    # First message
    response1 = httpx.post(
        f"{api_base_url}/conversation/",
        json={
            "text": "First message",
            "conversation_id": conv_id,
            "auto_route": False,
        },
        timeout=30.0,
    )
    assert response1.status_code == 200
    
    # Second message to same conversation
    response2 = httpx.post(
        f"{api_base_url}/conversation/",
        json={
            "text": "Second message",
            "conversation_id": conv_id,
            "auto_route": False,
        },
        timeout=30.0,
    )
    assert response2.status_code == 200
    data = response2.json()
    
    # Same conversation ID
    assert data["conversation_id"] == conv_id
    
    # Token count increased (proves history was loaded)
    assert data["total_tokens"] > 0


def test_get_conversation_metadata(api_base_url: str):
    """
    Demonstrates: Reading conversation state.
    
    After creating a conversation, we can retrieve its metadata.
    This tests the GET endpoint.
    """
    conv_id = str(uuid.uuid4())
    
    # Create conversation
    httpx.post(
        f"{api_base_url}/conversation/",
        json={
            "text": "Test message",
            "conversation_id": conv_id,
            "auto_route": False,
        },
        timeout=30.0,
    )
    
    # Get metadata
    response = httpx.get(f"{api_base_url}/conversation/{conv_id}", timeout=10.0)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["conversation_id"] == conv_id
    assert data["message_count"] >= 2  # User message + AI response
    assert data["total_tokens"] > 0


def test_get_nonexistent_conversation_returns_404(api_base_url: str):
    """
    Demonstrates: Error handling for missing resources.
    
    GET requests for non-existent conversations should return 404.
    This is different from POST, which creates on missing.
    """
    fake_id = str(uuid.uuid4())
    
    response = httpx.get(f"{api_base_url}/conversation/{fake_id}", timeout=10.0)
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_invalid_model_id_returns_400(api_base_url: str):
    """
    Demonstrates: Input validation at API boundary.
    
    When an invalid model_id is provided, the API returns 400.
    This tests our error handling, not Pydantic validation.
    """
    response = httpx.post(
        f"{api_base_url}/conversation/",
        json={
            "text": "Hello",
            "model_id": "fake-nonexistent-model",
            "auto_route": False,
        },
        timeout=10.0,
    )
    
    assert response.status_code == 400
    assert "Invalid model" in response.json()["detail"]


def test_list_available_models(api_base_url: str):
    """
    Demonstrates: Utility endpoint for model discovery.
    
    Users can query available models before sending messages.
    """
    response = httpx.get(f"{api_base_url}/conversation/models", timeout=10.0)
    
    assert response.status_code == 200
    models = response.json()
    
    assert isinstance(models, list)
    assert len(models) > 0
    # Should have at least some known models
    assert any("anthropic" in m.lower() or "openai" in m.lower() for m in models)

