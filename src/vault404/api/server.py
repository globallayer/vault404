"""
FastAPI server for the Vault404 REST API.

Provides HTTP endpoints for the collective AI coding agent brain.
Includes rate limiting, CORS, and API key authentication.
"""

import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .routes import (
    solutions_router,
    decisions_router,
    patterns_router,
    vulns_router,
    stats_router,
    API_VERSION,
)


# Rate limiting configuration
RATE_LIMIT_ENABLED = os.environ.get("VAULT404_RATE_LIMIT", "true").lower() in ("true", "1", "yes")
DEFAULT_RATE_LIMIT = os.environ.get("VAULT404_DEFAULT_RATE_LIMIT", "60/minute")

# CORS settings
CORS_ORIGINS = os.environ.get(
    "VAULT404_CORS_ORIGINS",
    "*",  # Default to allow all for development
).split(",")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    print(f"Vault404 API v{API_VERSION} starting...")
    if RATE_LIMIT_ENABLED:
        print(f"Rate limiting: enabled ({DEFAULT_RATE_LIMIT})")
    else:
        print("Rate limiting: disabled")

    auth_disabled = os.environ.get("VAULT404_AUTH_DISABLED", "").lower() in ("true", "1", "yes")
    if auth_disabled:
        print("WARNING: API key authentication is DISABLED")
    else:
        print("API key authentication: enabled for write operations")

    yield
    # Shutdown
    print("Vault404 API shutting down...")


def create_app(
    title: str = "Vault404 API",
    description: str = "Collective AI Coding Agent Brain - REST API",
    cors_origins: Optional[list] = None,
    enable_rate_limiting: Optional[bool] = None,
) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        title: API title for OpenAPI docs
        description: API description for OpenAPI docs
        cors_origins: List of allowed CORS origins
        enable_rate_limiting: Whether to enable rate limiting (default: from env)

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title=title,
        description=description,
        version=API_VERSION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=[
            {
                "name": "solutions",
                "description": "Search and log error fixes. Log/verify require API key.",
            },
            {
                "name": "decisions",
                "description": "Search and log architectural decisions. Log requires API key.",
            },
            {
                "name": "patterns",
                "description": "Search and log reusable patterns. Log requires API key.",
            },
            {
                "name": "vulnerabilities",
                "description": "AI-discovered vulnerability intelligence. Report/verify require API key. Feed/search are public with responsible disclosure (72h delay for unpatched).",
            },
            {
                "name": "stats",
                "description": "Statistics and health checks (public)",
            },
        ],
    )

    # Add CORS middleware
    origins = cors_origins or CORS_ORIGINS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting
    should_rate_limit = (
        enable_rate_limiting if enable_rate_limiting is not None else RATE_LIMIT_ENABLED
    )

    if should_rate_limit:
        try:
            from slowapi import Limiter, _rate_limit_exceeded_handler
            from slowapi.util import get_remote_address
            from slowapi.errors import RateLimitExceeded
            from slowapi.middleware import SlowAPIMiddleware

            limiter = Limiter(
                key_func=get_remote_address,
                default_limits=[DEFAULT_RATE_LIMIT],
                storage_uri="memory://",  # In-memory storage
            )
            app.state.limiter = limiter
            app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
            app.add_middleware(SlowAPIMiddleware)

        except ImportError:
            print("Warning: slowapi not installed, rate limiting disabled")
            print("Install with: pip install slowapi")

    # Custom exception handlers
    @app.exception_handler(422)
    async def validation_exception_handler(request: Request, exc):
        """Handle validation errors with cleaner messages."""
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation error",
                "errors": exc.errors() if hasattr(exc, "errors") else str(exc),
            },
        )

    # Include routers under /api/v1
    app.include_router(solutions_router, prefix="/api/v1")
    app.include_router(decisions_router, prefix="/api/v1")
    app.include_router(patterns_router, prefix="/api/v1")
    app.include_router(vulns_router, prefix="/api/v1")
    app.include_router(stats_router, prefix="/api/v1")

    # Root endpoint
    @app.get("/", tags=["root"])
    async def root():
        """Root endpoint with API information."""
        return {
            "name": "Vault404 API",
            "description": "Collective AI Coding Agent Brain",
            "version": API_VERSION,
            "docs": "/docs",
            "health": "/api/v1/health",
            "auth_info": "Write operations require X-API-Key header",
        }

    return app


# Create default app instance
app = create_app()


def run_server(
    host: str = "0.0.0.0",  # nosec B104 - intentional for development server
    port: int = 8000,
    reload: bool = False,
    log_level: str = "info",
):
    """
    Run the API server.

    Args:
        host: Host to bind to
        port: Port to listen on
        reload: Enable auto-reload for development
        log_level: Logging level
    """
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is required to run the server")
        print("Install it with: pip install uvicorn")
        return

    uvicorn.run(
        "vault404.api.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )


if __name__ == "__main__":
    run_server()
