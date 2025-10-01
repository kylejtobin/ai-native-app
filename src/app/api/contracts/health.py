"""Health check response model"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """API health check response"""

    status: str
    service: str
