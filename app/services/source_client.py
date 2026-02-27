"""
HTTP client for the HCS ManageOne SC Northbound Interface.

Handles:
  1. Authentication via IAM (token acquisition).
  2. Querying metering/metrics data from SC API.

Uses curl (via subprocess) for all HTTP calls so system/VPN routing and
SSL bypass are inherited automatically — identical to running curl directly.
asyncio.to_thread() keeps the event loop unblocked.
"""

import asyncio
import json
import subprocess
from datetime import datetime, timezone, timedelta
from typing import Any
from urllib.parse import urlencode

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

_LOGIN_REDIRECT_MARKER = "authui/login"


# ── curl response container ───────────────────────────────────────────

class _CurlResponse:
    __slots__ = ("status_code", "headers", "text")

    def __init__(self, status_code: int, headers: dict[str, str], text: str) -> None:
        self.status_code = status_code
        self.headers = headers
        self.text = text

    def json(self) -> Any:
        return json.loads(self.text)


# ── low-level curl helper ─────────────────────────────────────────────

def _run_curl(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    body: dict | None = None,
    timeout: int = 30,
) -> _CurlResponse:
    """
    Execute a single curl request and return a _CurlResponse.
    Runs synchronously — call via asyncio.to_thread() from async code.

    Raises:
        SourceAPITimeoutException:    curl exit code 28 (operation timed out).
        SourceAPIConnectionException: curl exit code 7 (failed to connect).
        SourceAPIException:           any other non-zero curl exit code.
    """
    cmd = [
        "curl",
        "--insecure",          # disable SSL cert validation (internal certs)
        "--silent",
        "--show-error",
        "--max-time", str(timeout),
        "--request", method.upper(),
        "--url", url,
        "--dump-header", "-",  # write response headers to stdout before body
    ]

    for key, value in (headers or {}).items():
        cmd += ["--header", f"{key}: {value}"]

    if body is not None:
        if not headers or "Content-Type" not in headers:
            cmd += ["--header", "Content-Type: application/json"]
        cmd += ["--data", json.dumps(body)]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if result.returncode == 28:
            raise SourceAPITimeoutException(
                message=f"Request to {url} timed out after {timeout}s.",
                details={"endpoint": url, "error": stderr},
            )
        if result.returncode == 7:
            raise SourceAPIConnectionException(
                details={"endpoint": url, "error": stderr},
            )
        raise SourceAPIException(
            message=f"curl exited with code {result.returncode}.",
            details={"endpoint": url, "error": stderr},
        )

    output = result.stdout

    # curl --dump-header - may include multiple HTTP response blocks when the
    # server sends 100 Continue, 301/302 redirects, etc.  Always use the LAST
    # complete block so we parse the final status + body, not an intermediate one.
    #
    # Strategy: find the last occurrence of a line that starts "HTTP/" and take
    # everything from there as the final response block.
    last_http_pos = max(output.rfind("\r\nHTTP/"), output.rfind("\nHTTP/"))
    if last_http_pos != -1:
        # Skip the leading newline character(s)
        final_block = output[last_http_pos:].lstrip("\r\n")
    else:
        final_block = output

    # Split the final block into header section and body
    header_block, sep, body_text = final_block.partition("\r\n\r\n")
    if not sep:
        header_block, sep, body_text = final_block.partition("\n\n")

    # Parse status code from the status line, e.g. "HTTP/1.1 201 Created"
    status_code = 0
    parsed_headers: dict[str, str] = {}
    for line in header_block.splitlines():
        line = line.strip()
        if line.upper().startswith("HTTP/"):
            try:
                status_code = int(line.split()[1])
            except (IndexError, ValueError):
                pass
        elif ": " in line:
            k, _, v = line.partition(": ")
            parsed_headers[k.lower()] = v

    return _CurlResponse(
        status_code=status_code,
        headers=parsed_headers,
        text=body_text.strip(),
    )


# ── HCS client ────────────────────────────────────────────────────────

class HCSClient:
    """curl-backed client for Huawei Cloud Stack ManageOne APIs."""

    # Refresh 60 s before actual expiry to avoid races
    _TOKEN_EXPIRY_BUFFER = timedelta(seconds=60)

    def __init__(self) -> None:
        self._token: str | None = None
        self._token_expires_at: datetime | None = None

    def _is_token_valid(self) -> bool:
        """Return True if a non-expired token is cached."""
        if not self._token or self._token_expires_at is None:
            return False
        return datetime.now(tz=timezone.utc) < (
            self._token_expires_at - self._TOKEN_EXPIRY_BUFFER
        )

    def _invalidate_token(self) -> None:
        self._token = None
        self._token_expires_at = None

    def _sc_headers(self) -> dict[str, str]:
        """Standard headers for SC Northbound API calls."""
        assert self._token is not None
        return {
            "X-Auth-Token": self._token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @staticmethod
    def _is_login_redirect(response: _CurlResponse) -> bool:
        """Detect HTML login-redirect pages the gateway returns for unauthed requests."""
        return (
            _LOGIN_REDIRECT_MARKER in response.text
            or response.text.lstrip().startswith("<")
        )

    # ── Authentication ────────────────────────────────────────────────

    async def authenticate(self) -> str:
        """
        Obtain an admin token from the IAM endpoint.

        POST https://{IAM_DOMAIN}/v3/auth/tokens
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
                "scope": {"domain": {"name": settings.iam_auth_domain}},
            }
        }

        logger.info("Authenticating with HCS IAM", extra={"url": url})

        response = await asyncio.to_thread(
            _run_curl, "POST", url,
            headers={"Accept": "application/json"},
            body=body,
            timeout=settings.sc_api_timeout,
        )

        status = response.status_code
        if status in (401, 403):
            raise AuthenticationException(
                message=f"IAM authentication rejected (HTTP {status}).",
                details={"url": url, "body": response.text[:500]},
            )
        if status == 504:
            raise SourceAPITimeoutException(
                message="IAM gateway timed out (504). Check network path to IAM.",
                details={"url": url, "body": response.text[:500]},
            )
        if status not in (200, 201):
            raise SourceAPIException(
                message=f"IAM endpoint returned HTTP {status}.",
                details={"url": url, "status_code": status,
                         "body": response.text[:500]},
            )

        token = response.headers.get("x-subject-token", "")
        if not token:
            raise AuthenticationException(
                message="IAM response missing X-Subject-Token header.",
            )

        self._token = token

        # Parse expiry and user info from the response body
        try:
            token_data = response.json().get("token", {})
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
            logger.warning("Could not parse IAM token response body.")

        return token

    # ── Regions ───────────────────────────────────────────────────────

    async def fetch_regions(self) -> list[HCSRegion]:
        """
        Return all regions from the SC Northbound Interface.

        GET https://{SC_DOMAIN}/silvan/rest/v1.0/regions
        """
        if not self._is_token_valid():
            await self.authenticate()

        assert self._token is not None

        settings = get_settings()
        url = f"{settings.sc_domain}{_REGIONS_ENDPOINT}"

        logger.info("Fetching HCS regions", extra={"url": url})

        response = await asyncio.to_thread(
            _run_curl, "GET", url,
            headers=self._sc_headers(),
            timeout=settings.sc_api_timeout,
        )

        if response.status_code == 401 or self._is_login_redirect(response):
            self._invalidate_token()
            await self.authenticate()
            response = await asyncio.to_thread(
                _run_curl, "GET", url,
                headers=self._sc_headers(),
                timeout=settings.sc_api_timeout,
            )

        if self._is_login_redirect(response):
            raise AuthenticationException(
                message="SC API returned login redirect after re-auth. Token not accepted.",
                details={"endpoint": url, "raw_body": response.text[:500]},
            )
        if response.status_code != 200:
            raise SourceAPIException(
                message=f"SC API returned {response.status_code} fetching regions.",
                details={"endpoint": url, "body": response.text[:500]},
            )

        try:
            regions_response = HCSRegionsResponse(**response.json())
        except Exception as exc:
            raise SourceAPIException(
                message="Failed to parse regions response.",
                details={"endpoint": url, "error": str(exc)},
            ) from exc

        logger.info("HCS regions fetched",
                    extra={"region_count": len(regions_response.regions)})
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

            url = f"{base_url}?{urlencode(params)}"

            logger.info("Fetching HCS VDC page",
                        extra={"url": base_url, "start": start, "limit": limit})

            response = await asyncio.to_thread(
                _run_curl, "GET", url,
                headers=self._sc_headers(),
                timeout=settings.sc_api_timeout,
            )

            if response.status_code == 401 or self._is_login_redirect(response):
                self._invalidate_token()
                await self.authenticate()
                response = await asyncio.to_thread(
                    _run_curl, "GET", url,
                    headers=self._sc_headers(),
                    timeout=settings.sc_api_timeout,
                )

            if self._is_login_redirect(response):
                raise AuthenticationException(
                    message="SC API returned login redirect after re-auth. Token not accepted.",
                    details={"endpoint": base_url,
                             "raw_body": response.text[:500]},
                )
            if response.status_code != 200:
                raise SourceAPIException(
                    message=f"SC API returned {response.status_code} fetching VDCs.",
                    details={"endpoint": base_url,
                             "body": response.text[:500]},
                )

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
        resource_type_code: str | None = None,
        period: str = "daily",
        time_zone: str = "Africa/Lagos",
        locale: str = "en_US",
        limit: int | None = None,
    ) -> list[HCSMetricRecord]:
        """
        Query cloud service CDRs from the SC Northbound Interface, auto-paginating.

        POST https://{SC_DOMAIN}/rest/metering/v3.0/query-metrics-data
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
            body: dict[str, Any] = {
                "region_code": region_code,
                "start_time": start_time,
                "end_time": end_time,
                "time_zone": time_zone,
                "period": period,
                "locale": locale,
                "domain_id": domain_id,
                "start": start,
            }
            if resource_type_code:
                body["resource_type_code"] = resource_type_code
            if limit is not None:
                body["limit"] = limit

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

            response = await asyncio.to_thread(
                _run_curl, "POST", url,
                headers=self._sc_headers(),
                body=body,
                timeout=settings.sc_api_timeout,
            )

            if response.status_code == 401 or self._is_login_redirect(response):
                self._invalidate_token()
                await self.authenticate()
                response = await asyncio.to_thread(
                    _run_curl, "POST", url,
                    headers=self._sc_headers(),
                    body=body,
                    timeout=settings.sc_api_timeout,
                )

            if self._is_login_redirect(response):
                raise AuthenticationException(
                    message="SC API returned login redirect after re-auth. Token not accepted.",
                    details={"endpoint": url, "raw_body": response.text[:500]},
                )
            if response.status_code != 200:
                raise SourceAPIException(
                    message=f"SC API returned {response.status_code}.",
                    details={
                        "endpoint": url,
                        "status_code": response.status_code,
                        "body": response.text[:500],
                    },
                )

            # A 200 with an empty body means no records for this query
            if not response.text:
                logger.warning(
                    "SC API returned 200 with empty body — treating as zero records",
                    extra={"endpoint": url, "start": start},
                )
                break

            try:
                metrics_response = HCSMetricsResponse(**response.json())
            except Exception as exc:
                raise SourceAPIException(
                    message="Failed to parse SC API metrics response.",
                    details={
                        "endpoint": url,
                        "error": str(exc),
                        "raw_body": response.text[:500],
                    },
                ) from exc

            all_records.extend(metrics_response.metrics)
            total_reported = metrics_response.total

            if len(all_records) >= total_reported or not metrics_response.metrics:
                break
            # Default SC API page size is 20 when limit is not specified
            start += limit if limit is not None else len(
                metrics_response.metrics)

        logger.info(
            "HCS metrics fetch complete",
            extra={"record_count": len(all_records), "total": total_reported},
        )
        return all_records
