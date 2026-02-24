"""
Custom exception hierarchy for the application.

All application-specific exceptions inherit from AppException,
enabling consistent error handling and structured error responses.

Hierarchy:
    AppException
    ├── SourceAPIException       — Errors when calling the source API (API-A)
    ├── TransformationException  — Errors during data mapping / transformation
    ├── ValidationException      — Input/output data validation failures
    ├── NotFoundException        — Requested resource not found
    ├── AuthenticationException  — Auth/API-key failures
    └── RateLimitException       — Rate-limit exceeded (source or self)
"""

from typing import Any


class AppException(Exception):
    """
    Base exception for all application errors.

    Attributes:
        message:     Human-readable error description.
        status_code: HTTP status code to return to the client.
        error_code:  Machine-readable error identifier (e.g. "SOURCE_API_TIMEOUT").
        details:     Optional dict with extra context for debugging.
    """

    def __init__(
        self,
        message: str = "An unexpected error occurred.",
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the exception into a JSON-friendly dict."""
        payload: dict[str, Any] = {
            "error": True,
            "error_code": self.error_code,
            "message": self.message,
        }
        if self.details:
            payload["details"] = self.details
        return payload


# ─── Source API Errors ────────────────────────────────────────────────


class SourceAPIException(AppException):
    """Raised when the source API (API-A) returns an error or is unreachable."""

    def __init__(
        self,
        message: str = "Failed to fetch data from the source API.",
        status_code: int = 502,
        error_code: str = "SOURCE_API_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, status_code, error_code, details)


class SourceAPITimeoutException(SourceAPIException):
    """Raised when the source API request times out."""

    def __init__(
        self,
        message: str = "Source API request timed out.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=504,
            error_code="SOURCE_API_TIMEOUT",
            details=details,
        )


class SourceAPIConnectionException(SourceAPIException):
    """Raised when unable to establish connection to the source API."""

    def __init__(
        self,
        message: str = "Unable to connect to the source API.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=502,
            error_code="SOURCE_API_CONNECTION_ERROR",
            details=details,
        )


# ─── Transformation Errors ───────────────────────────────────────────


class TransformationException(AppException):
    """Raised when data transformation/mapping fails."""

    def __init__(
        self,
        message: str = "Data transformation failed.",
        status_code: int = 422,
        error_code: str = "TRANSFORMATION_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, status_code, error_code, details)


class MappingFieldException(TransformationException):
    """Raised when a specific field cannot be mapped."""

    def __init__(
        self,
        field_name: str,
        reason: str = "Field mapping failed.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=f"Failed to map field '{field_name}': {reason}",
            status_code=422,
            error_code="MAPPING_FIELD_ERROR",
            details={**(details or {}), "field": field_name},
        )


# ─── Validation Errors ───────────────────────────────────────────────


class ValidationException(AppException):
    """Raised when request or response data fails validation."""

    def __init__(
        self,
        message: str = "Validation error.",
        status_code: int = 422,
        error_code: str = "VALIDATION_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, status_code, error_code, details)


# ─── Not Found ────────────────────────────────────────────────────────


class NotFoundException(AppException):
    """Raised when a requested resource is not found."""

    def __init__(
        self,
        message: str = "Resource not found.",
        status_code: int = 404,
        error_code: str = "NOT_FOUND",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, status_code, error_code, details)


# ─── Authentication ──────────────────────────────────────────────────


class AuthenticationException(AppException):
    """Raised on authentication or authorization failures."""

    def __init__(
        self,
        message: str = "Authentication failed.",
        status_code: int = 401,
        error_code: str = "AUTH_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, status_code, error_code, details)


# ─── Rate Limiting ───────────────────────────────────────────────────


class RateLimitException(AppException):
    """Raised when a rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded. Please retry later.",
        status_code: int = 429,
        error_code: str = "RATE_LIMIT_EXCEEDED",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, status_code, error_code, details)
