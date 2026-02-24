"""
HTTP client for the HCS ManageOne SC Northbound Interface.

Handles:
  1. Authentication via IAM (token acquisition).
  2. Querying metering/metrics data from SC API.

Wraps httpx with proper error handling mapped to our exception hierarchy.
"""

from typing import Any

import httpx

from app.config import get_settings
from app.core.exceptions import (
    AuthenticationException,
    SourceAPIConnectionException,
    SourceAPIException,
    SourceAPITimeoutException,
)
from app.core.logging import get_logger
from app.schemas import HCSMetricRecord, HCSMetricsResponse

logger = get_logger(__name__)

_METRICS_ENDPOINT = "/rest/metering/v3.0/query-metrics-data"


class HCSClient:
    """Async HTTP client for Huawei Cloud Stack ManageOne APIs."""

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._client = http_client
        self._token: str | None = None

    # ── Authentication ────────────────────────────────────────────────

    async def authenticate(self) -> str:
        """
        Obtain an admin token from the IAM endpoint.

        POST https://{IAM_DOMAIN}/v3/auth/tokens

        Returns:
            The X-Subject-Token value.

        Raises:
            AuthenticationException: On auth failure.
        """
        settings = get_settings()
        url = f"{settings.iam_domain}/v3/auth/tokens"

        body = {
            "auth": {
                "identity": {
                    "methods": ["password"],
                    "password": {
                        "user": {
                            "domain": {"name": settings.iam_auth_domain},
                            "name": settings.iam_username,
                            "password": settings.iam_password,
                        }
                    },
                },
                "scope": {
                    "domain": {"name": settings.iam_auth_domain}
                },
            }
        }

        logger.info("Authenticating with HCS IAM", extra={"url": url})

        try:
            response = await self._client.post(
                url,
                json=body,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json;charset=UTF-8",
                },
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise SourceAPITimeoutException(
                details={"endpoint": url, "error": str(exc)}
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise AuthenticationException(
                message=f"IAM authentication failed (HTTP {exc.response.status_code}).",
                details={"url": url, "body": exc.response.text[:500]},
            ) from exc
        except httpx.HTTPError as exc:
            raise AuthenticationException(
                message="IAM authentication request failed.",
                details={"url": url, "error": str(exc)},
            ) from exc

        token = response.headers.get("X-Subject-Token", "")
        if not token:
            raise AuthenticationException(
                message="IAM response missing X-Subject-Token header.",
            )

        self._token = token
        logger.info("HCS IAM authentication successful.")
        return token

    # ── Metrics Query ─────────────────────────────────────────────────

    async def fetch_metrics(
        self,
        region_code: str,
        domain_id: str,
        start_time: str,
        end_time: str,
        resource_type_code: str,
        period: str = "daily",
        time_zone: str = "Africa/Lagos",
        locale: str = "en_US",
        limit: int = 1000,
    ) -> list[HCSMetricRecord]:
        """
        Query cloud service CDRs from the SC Northbound Interface.

        POST https://{SC_DOMAIN}/rest/metering/v3.0/query-metrics-data

        Args:
            region_code:        Region ID (from /silvan/rest/v1.0/regions).
            domain_id:          Tenant/VDC domain ID.
            start_time:         Start of period (YYYY-MM-DD HH:MM:SS).
            end_time:           End of period (YYYY-MM-DD HH:MM:SS).
            resource_type_code: e.g. "hws.resource.type.volume".
            period:             "hourly", "daily", or "monthly".
            time_zone:          Timezone string.
            locale:             "en_US" or "zh_CN".
            limit:              Page size (1-1000).

        Returns:
            List of validated HCSMetricRecord objects.
        """
        if not self._token:
            await self.authenticate()

        assert self._token is not None

        settings = get_settings()
        url = f"{settings.sc_domain}{_METRICS_ENDPOINT}"

        body = {
            "region_code": region_code,
            "start_time": start_time,
            "end_time": end_time,
            "time_zone": time_zone,
            "period": period,
            "locale": locale,
            "domain_id": domain_id,
            "resource_type_code": resource_type_code,
            "limit": limit,
        }

        logger.info(
            "Fetching HCS metrics",
            extra={"url": url, "region": region_code,
                   "resource_type": resource_type_code},
        )

        try:
            response = await self._client.post(
                url,
                json=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Auth-Token": self._token,
                },
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise SourceAPITimeoutException(
                details={"endpoint": url, "error": str(exc)}
            ) from exc
        except httpx.ConnectError as exc:
            raise SourceAPIConnectionException(
                details={"endpoint": url, "error": str(exc)}
            ) from exc
        except httpx.HTTPStatusError as exc:
            # If 401, token may have expired — clear it for retry
            if exc.response.status_code == 401:
                self._token = None
            raise SourceAPIException(
                message=f"SC API returned {exc.response.status_code}.",
                details={
                    "endpoint": url,
                    "status_code": exc.response.status_code,
                    "body": exc.response.text[:500],
                },
            ) from exc
        except httpx.HTTPError as exc:
            raise SourceAPIException(
                message="Unexpected HTTP error from SC API.",
                details={"endpoint": url, "error": str(exc)},
            ) from exc

        try:
            payload = response.json()
            metrics_response = HCSMetricsResponse(**payload)
        except Exception as exc:
            raise SourceAPIException(
                message="Failed to parse SC API metrics response.",
                details={"endpoint": url, "error": str(exc)},
            ) from exc

        logger.info(
            "HCS metrics fetch complete",
            extra={
                "record_count": len(metrics_response.metrics),
                "total": metrics_response.total,
            },
        )
        return metrics_response.metrics
