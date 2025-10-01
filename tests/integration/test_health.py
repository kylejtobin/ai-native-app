"""
Integration test for health endpoint.

Demonstrates:
- Testing critical path (API is reachable)
- Testing contracts (response structure matches SendMessageResponse schema)
- Minimal integration test that proves the stack works
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create FastAPI test client."""
    from app.main import app

    return TestClient(app)


def test_health_endpoint_returns_200(client: TestClient):
    """
    Demonstrates: Integration test for critical path.

    This proves the FastAPI app is configured correctly and can handle requests.
    We don't test framework behavior—we test our integration is correct.
    """
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "ai-native-app"


def test_health_endpoint_uses_correct_content_type(client: TestClient):
    """
    Demonstrates: Testing HTTP concerns at API boundary.

    This is an API layer responsibility—ensure correct content-type header.
    We don't test FastAPI itself, we test our endpoint configuration.
    """
    response = client.get("/health")

    assert "application/json" in response.headers["content-type"]
