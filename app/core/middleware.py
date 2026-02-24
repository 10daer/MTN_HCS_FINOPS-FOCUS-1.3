"""
Application middleware.

RequestContextMiddleware:
  - Assigns a unique request_id (or reads X-Request-ID header).
  - Logs request start / finish with timing.
  - Injects request_id into every log record via a filter.
"""

import time
import uuid
import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request_id to every request and log timing."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Use incoming header or generate a new one
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex)
        request.state.request_id = request_id

        # Add request_id to all log records for this request
        ctx_filter = _RequestIdFilter(request_id)
        logging.getLogger().addFilter(ctx_filter)

        start = time.perf_counter()

        logger.info(
            "Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": str(request.url.path),
                "query": str(request.url.query),
            },
        )

        try:
            response = await call_next(request)
        except Exception:
            # Let the error handlers deal with it; just remove the filter
            raise
        finally:
            logging.getLogger().removeFilter(ctx_filter)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        logger.info(
            "Request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": str(request.url.path),
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        # Echo the request_id back to the caller
        response.headers["X-Request-ID"] = request_id
        return response


class _RequestIdFilter(logging.Filter):
    """Inject request_id into every log record."""

    def __init__(self, request_id: str) -> None:
        super().__init__()
        self.request_id = request_id

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = self.request_id  # type: ignore[attr-defined]
        return True
