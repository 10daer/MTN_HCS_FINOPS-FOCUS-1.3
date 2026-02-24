"""
HTTP client for the HCS ManageOne SC Northbound Interface.

Handles:
  1. Authentication via IAM (token acquisition).
  2. Querying metering/metrics data from SC API.

Wraps httpx with proper error handling mapped to our exception hierarchy.
"""

from datetime import datetime, timezone, timedelta
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
from app.schemas import (
    HCSMetricRecord,
    HCSMetricsResponse,
    HCSRegion,
    HCSRegionsResponse,
    HCSVDC,
    HCSVDCsResponse,
)

logger = get_logger(__name__)

_METRICS_ENDPOINT = "/rest/metering/v3.0/query-metrics-data"
_REGIONS_ENDPOINT = "/silvan/rest/v1.0/regions"
_VDCS_ENDPOINT = "/rest/vdc/v3.0/vdcs"


class HCSClient:
    """Async HTTP client for Huawei Cloud Stack ManageOne APIs."""

    # Refresh 60 s before actual expiry to avoid races
    _TOKEN_EXPIRY_BUFFER = timedelta(seconds=60)

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._client = http_client
        self._token: str | None = None
        self._token_expires_at: datetime | None = None

    def _is_token_valid(self) -> bool:
        """Return True if a non-expired token is cached."""
        if not self._token or self._token_expires_at is None:
            return False
        return datetime.now(tz=timezone.utc) < (
            self._token_expires_at - self._TOKEN_EXPIRY_BUFFER
        )

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
                message="IAM authentication request timed out.",
                details={"endpoint": url, "error": str(exc)},
            ) from exc
        except httpx.ConnectError as exc:
            raise SourceAPIConnectionException(
                details={"endpoint": url, "error": str(exc)},
            ) from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            body = exc.response.text[:500]
            # 4xx credential/auth errors → AuthenticationException (401 to client)
            if status in (401, 403):
                raise AuthenticationException(
                    message=f"IAM authentication rejected (HTTP {status}).",
                    details={"url": url, "body": body},
                ) from exc
            # 504 / upstream gateway timeout → SourceAPITimeoutException
            if status == 504:
                raise SourceAPITimeoutException(
                    message="IAM gateway timed out (504). Check network path to IAM.",
                    details={"url": url, "body": body},
                ) from exc
            # Any other non-2xx (5xx, etc.) → SourceAPIException (502 to client)
            raise SourceAPIException(
                message=f"IAM endpoint returned HTTP {status}.",
                details={"url": url, "status_code": status, "body": body},
            ) from exc
        except httpx.HTTPError as exc:
            raise SourceAPIConnectionException(
                details={"endpoint": url, "error": str(exc)},
            ) from exc

        token = response.headers.get("X-Subject-Token", "")
        if not token:
            raise AuthenticationException(
                message="IAM response missing X-Subject-Token header.",
            )

        self._token = token

        # Parse expiry and user info from the response body
        try:
            body_data = response.json()
            token_data = body_data.get("token", {})
            expires_at_str = token_data.get("expires_at", "")
            if expires_at_str:
                self._token_expires_at = datetime.fromisoformat(
                    expires_at_str.replace("Z", "+00:00")
                )
            user = token_data.get("user", {})
            logger.info(
                "HCS IAM authentication successful",
                extra={
                    "iam_user": user.get("name", ""),
                    "iam_domain": user.get("domain", {}).get("name", ""),
                    "token_expires_at": expires_at_str,
                },
            )
        except Exception:
            # Non-fatal — token itself is valid even if body parsing fails
            logger.warning("Could not parse IAM token response body.")

        return token

    # ── Regions ───────────────────────────────────────────────────────

    async def fetch_regions(self) -> list[HCSRegion]:
        """
        Return all regions from the SC Northbound Interface.

        GET https://{SC_DOMAIN}/silvan/rest/v1.0/regions

        Returns:
            List of HCSRegion objects (use .id as region_code).
        """
        if not self._is_token_valid():
            await self.authenticate()

        assert self._token is not None

        settings = get_settings()
        url = f"{settings.sc_domain}{_REGIONS_ENDPOINT}"

        logger.info("Fetching HCS regions", extra={"url": url})

        try:
            response = await self._client.get(
                url,
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
            if exc.response.status_code == 401:
                self._token = None
                self._token_expires_at = None
            raise SourceAPIException(
                message=f"SC API returned {exc.response.status_code} fetching regions.",
                details={"endpoint": url, "body": exc.response.text[:500]},
            ) from exc
        except httpx.HTTPError as exc:
            raise SourceAPIException(
                message="Unexpected HTTP error fetching regions.",
                details={"endpoint": url, "error": str(exc)},
            ) from exc

        try:
            regions_response = HCSRegionsResponse(**response.json())
        except Exception as exc:
            raise SourceAPIException(
                message="Failed to parse regions response.",
                details={"endpoint": url, "error": str(exc)},
            ) from exc

        logger.info(
            "HCS regions fetched",
            extra={"region_count": len(regions_response.regions)},
        )
        return regions_response.regions

    # ── VDCs ──────────────────────────────────────────────────────────

    async def fetch_vdcs(
        self,
        level: int | None = None,
        is_domain: str | None = None,
        limit: int = 1000,
    ) -> list[HCSVDC]:
        """
        Return VDCs (tenants) from the SC Northbound Interface, auto-paginating.

        GET https://{SC_DOMAIN}/rest/vdc/v3.0/vdcs

        Args:
            level:     Filter by VDC level (1 = top-level tenants).
            is_domain: "1" to return only tenants, "0" for sub-VDCs.
            limit:     Page size (1-1000).

        Returns:
            List of HCSVDC objects (use .domain_id as the tenant ID for metrics).
        """
        if not self._is_token_valid():
            await self.authenticate()

        assert self._token is not None

        settings = get_settings()
        base_url = f"{settings.sc_domain}{_VDCS_ENDPOINT}"

        all_vdcs: list[HCSVDC] = []
        start = 0

        while True:
            params: dict[str, Any] = {"start": start, "limit": limit}
            if level is not None:
                params["level"] = level
            if is_domain is not None:
                params["is_domain"] = is_domain

            logger.info(
                "Fetching HCS VDC page",
                extra={"url": base_url, "start": start, "limit": limit},
            )

            try:
                response = await self._client.get(
                    base_url,
                    params=params,
                    headers={
                        "Content-Type": "application/json",
                        "X-Auth-Token": self._token,
                    },
                )
                response.raise_for_status()
            except httpx.TimeoutException as exc:
                raise SourceAPITimeoutException(
                    details={"endpoint": base_url, "error": str(exc)}
                ) from exc
            except httpx.ConnectError as exc:
                raise SourceAPIConnectionException(
                    details={"endpoint": base_url, "error": str(exc)}
                ) from exc
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401:
                    self._token = None
                    self._token_expires_at = None
                raise SourceAPIException(
                    message=f"SC API returned {exc.response.status_code} fetching VDCs.",
                    details={"endpoint": base_url,
                             "body": exc.response.text[:500]},
                ) from exc
            except httpx.HTTPError as exc:
                raise SourceAPIException(
                    message="Unexpected HTTP error fetching VDCs.",
                    details={"endpoint": base_url, "error": str(exc)},
                ) from exc

            try:
                vdcs_response = HCSVDCsResponse(**response.json())
            except Exception as exc:
                raise SourceAPIException(
                    message="Failed to parse VDC list response.",
                    details={"endpoint": base_url, "error": str(exc)},
                ) from exc

            all_vdcs.extend(vdcs_response.vdcs)

            if len(all_vdcs) >= vdcs_response.total or not vdcs_response.vdcs:
                break
            start += limit

        logger.info("HCS VDCs fetched", extra={"vdc_count": len(all_vdcs)})
        return all_vdcs

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
        if not self._is_token_valid():
            await self.authenticate()

        assert self._token is not None

        settings = get_settings()
        url = f"{settings.sc_domain}{_METRICS_ENDPOINT}"

        all_records: list[HCSMetricRecord] = []
        total_reported = 0
        start = 0

        while True:
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
                "start": start,
            }

            logger.info(
                "Fetching HCS metrics page",
                extra={
                    "url": url,
                    "region": region_code,
                    "resource_type": resource_type_code,
                    "start": start,
                    "limit": limit,
                },
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
                    self._token_expires_at = None
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
                metrics_response = HCSMetricsResponse(**response.json())
            except Exception as exc:
                raise SourceAPIException(
                    message="Failed to parse SC API metrics response.",
                    details={"endpoint": url, "error": str(exc)},
                ) from exc

            all_records.extend(metrics_response.metrics)
            total_reported = metrics_response.total

            if len(all_records) >= total_reported or not metrics_response.metrics:
                break
            start += limit

        logger.info(
            "HCS metrics fetch complete",
            extra={"record_count": len(all_records), "total": total_reported},
        )
        return all_records
