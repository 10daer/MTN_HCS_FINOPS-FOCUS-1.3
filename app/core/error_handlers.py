"""
Global error handlers registered on the FastAPI application.

These handlers catch exceptions and return uniform JSON error responses
so clients always receive a predictable error shape:

    {
        "error": true,
        "error_code": "SOURCE_API_TIMEOUT",
        "message": "Source API request timed out.",
        "details": { ... },
        "request_id": "abc-123"
    }
"""

import uuid
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppException
from app.core.logging import get_logger

logger = get_logger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    """Attach all global exception handlers to the FastAPI app."""

    # ── 1. Handle our custom AppException hierarchy ───────────────────

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        request_id = _get_request_id(request)

        logger.error(
            "Application error",
            extra={
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "message": exc.message,
                "details": exc.details,
                "request_id": request_id,
                "path": str(request.url),
                "method": request.method,
            },
        )

        body = exc.to_dict()
        body["request_id"] = request_id
        return JSONResponse(status_code=exc.status_code, content=body)

    # ── 2. Handle Pydantic / FastAPI request validation errors ────────

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = _get_request_id(request)

        errors = []
        for err in exc.errors():
            errors.append(
                {
                    "field": " → ".join(str(loc) for loc in err.get("loc", [])),
                    "message": err.get("msg", ""),
                    "type": err.get("type", ""),
                }
            )

        logger.warning(
            "Request validation failed",
            extra={
                "request_id": request_id,
                "path": str(request.url),
                "method": request.method,
                "validation_errors": errors,
            },
        )

        return JSONResponse(
            status_code=422,
            content={
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "Request validation failed.",
                "details": {"errors": errors},
                "request_id": request_id,
            },
        )

    # ── 3. Handle Starlette / generic HTTP exceptions ─────────────────

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        request_id = _get_request_id(request)

        logger.warning(
            "HTTP error",
            extra={
                "status_code": exc.status_code,
                "detail": exc.detail,
                "request_id": request_id,
                "path": str(request.url),
                "method": request.method,
            },
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "error_code": "HTTP_ERROR",
                "message": str(exc.detail),
                "request_id": request_id,
            },
        )

    # ── 4. Catch-all for truly unexpected exceptions ──────────────────

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        request_id = _get_request_id(request)

        logger.critical(
            "Unhandled exception",
            extra={
                "request_id": request_id,
                "path": str(request.url),
                "method": request.method,
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
            },
            exc_info=True,  # full traceback in logs
        )

        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "error_code": "INTERNAL_ERROR",
                "message": "An unexpected internal error occurred.",
                "request_id": request_id,
            },
        )


# ─── Helpers ──────────────────────────────────────────────────────────


def _get_request_id(request: Request) -> str:
    """
    Return the request ID from state (set by middleware) or generate one.
    """
    return getattr(request.state, "request_id", uuid.uuid4().hex)
