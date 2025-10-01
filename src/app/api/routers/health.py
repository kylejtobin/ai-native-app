"""Health check router

Provides health check endpoints for monitoring and service discovery.
Demonstrates minimal API endpoint with rich response types.

Endpoints:
- GET /health: Service health status and metadata

Health Check Philosophy:
- Simple status indication for monitoring systems
- Rich response model (not generic dict)

"""

from fastapi import APIRouter

from ...api.contracts import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """API health check"""
    return HealthResponse(status="healthy", service="ai-native-app")
