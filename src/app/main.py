"""AI-Native App Architecture

Reference FastAPI application demonstrating modern Python architecture patterns
with intelligent conditional primitives via LLM integration.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from .api.routers import conversation_router, health_router
from .config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan - startup and shutdown logic"""
    print(f"Starting {settings.app_name} v{settings.app_version}")
    yield
    print("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description=settings.app_description,
    version=settings.app_version,
    debug=settings.environment == "development",
    lifespan=lifespan,
)

# Add CORS middleware
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins.split(","),
        allow_credentials=settings.cors_credentials,
        allow_methods=settings.cors_methods.split(","),
        allow_headers=settings.cors_headers.split(","),
    )

# Import and include routers
app.include_router(health_router)
app.include_router(conversation_router)


@app.get("/")
async def root() -> RedirectResponse:
    """Redirect root to API docs"""
    return RedirectResponse(url="/docs")
