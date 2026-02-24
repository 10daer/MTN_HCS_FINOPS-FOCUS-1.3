"""
FastAPI application factory.
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.logging import setup_logging, get_logger
from app.core.error_handlers import register_error_handlers
from app.core.middleware import RequestContextMiddleware
from app.api.routes import router as api_router

settings = get_settings()


# ─── Lifespan: startup / shutdown ─────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application-level resources."""
    logger = get_logger(__name__)

    # Startup
    setup_logging(level=settings.log_level, log_format=settings.log_format)
    logger.info(
        "Application starting",
        extra={
            "app": settings.app_name,
            "version": settings.app_version,
            "env": settings.app_env,
        },
    )

    yield

    # Shutdown
    logger.info("Application shut down gracefully.")


# ─── App factory ──────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        lifespan=lifespan,
    )

    # Middleware (order matters — outermost first)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(RequestContextMiddleware)

    # Error handlers
    register_error_handlers(application)

    # Routes
    application.include_router(api_router, prefix="/api/v1")

    # Health check
    @application.get("/health", tags=["Health"])
    async def health_check() -> dict:
        return {
            "status": "healthy",
            "app": settings.app_name,
            "version": settings.app_version,
        }

    return application


app = create_app()
