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
from typing import Any, AsyncIterator
from urllib.parse import urlencode

from app.config import get_settings
from app.core.exceptions import (
    AuthenticationException,
    SourceAPIConnectionException,
    SourceAPIException,
    SourceAPITimeoutException,
)
from app.core.logging import get_logger
from app.utils.helpers import save_api_response
from app.schemas import (
    HCSMetricRecord,
    HCSMetricsResponse,
    HCSRegion,
    HCSRegionsResponse,
    HCSVDC,
    HCSVDCsResponse,
)
from app.schemas.tag_schema import (
    QueryResourceTagsResponse,
    ListTagsResponse,
    PreDefineTagsResponse,
)

logger = get_logger(__name__)

_METRICS_ENDPOINT = "/rest/metering/v3.0/query-metrics-data"
_REGIONS_ENDPOINT = "/silvan/rest/v1.0/regions"
_VDCS_ENDPOINT = "/rest/vdc/v3.0/vdcs"

_TAGS_RESOURCES_ACTION_ENDPOINT = "/rest/tag/v3.0/tags/resources/action"
_TAGS_ENDPOINT = "/rest/tag/v3.0/tags"
_TAGS_AUTHEN_ENDPOINT = "/rest/tag/v3.0/tags/authen"
_PREDEFINE_TAGS_ENDPOINT = "/v1.0/predefine_tags"

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

    async def fetch_metrics_pages(
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
    ) -> AsyncIterator[list[HCSMetricRecord]]:
        """
        Async generator that yields one page of HCS metric records at a time.

        Uses marker-based pagination: the loop continues until the API
        returns an empty marker string.
        """
        if not self._is_token_valid():
            await self.authenticate()

        assert self._token is not None

        settings = get_settings()
        url = f"{settings.sc_domain}{_METRICS_ENDPOINT}"

        marker: str | None = None  # None = first request; "" = done

        while True:
            body: dict[str, Any] = {
                "region_code": region_code,
                "start_time": start_time,
                "end_time": end_time,
                "time_zone": time_zone,
                "period": period,
                "locale": locale,
                "domain_id": domain_id,
            }
            if marker:
                body["marker"] = marker
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
                    "marker": marker,
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
                    extra={"endpoint": url, "marker": marker},
                )
                return

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

            if metrics_response.metrics:
                yield metrics_response.metrics

            # Empty marker means no more pages
            if not metrics_response.marker:
                return

            marker = metrics_response.marker

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
        Convenience wrapper: fetches ALL pages and returns a flat list.

        For streaming use cases prefer ``fetch_metrics_pages()``.
        """
        all_records: list[HCSMetricRecord] = []
        async for page in self.fetch_metrics_pages(
            region_code=region_code,
            domain_id=domain_id,
            start_time=start_time,
            end_time=end_time,
            resource_type_code=resource_type_code,
            period=period,
            time_zone=time_zone,
            locale=locale,
            limit=limit,
        ):
            all_records.extend(page)

        logger.info(
            "HCS metrics fetch complete",
            extra={"record_count": len(all_records)},
        )

        saved_path = save_api_response(
            method="POST",
            url=f"{get_settings().sc_domain}{_METRICS_ENDPOINT}",
            status_code=200,
            headers={},
            body=json.dumps(
                {
                    "region_code": region_code,
                    "domain_id": domain_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "resource_type_code": resource_type_code,
                    "period": period,
                    "time_zone": time_zone,
                    "locale": locale,
                    "limit": limit,
                    "record_count": len(all_records),
                    "records": [record.model_dump() for record in all_records],
                },
                ensure_ascii=False,
            ),
        )
        logger.debug("Saved metrics API response", extra={"file_path": str(saved_path)})

        return all_records

    # ── Tags: Query resources associated with a tag (14.2) ────────────

    async def query_resource_tags(self, body: dict) -> QueryResourceTagsResponse:
        """
        Query the list of resources bound to a tag.

        POST https://{SC_DOMAIN}/rest/tag/v3.0/tags/resources/action
        """
        if not self._is_token_valid():
            await self.authenticate()

        settings = get_settings()
        url = f"{settings.sc_domain}{_TAGS_RESOURCES_ACTION_ENDPOINT}"

        logger.info("Querying resource tags", extra={"url": url, "action": body.get("action")})

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
                message="SC API returned login redirect after re-auth.",
                details={"endpoint": url, "raw_body": response.text[:500]},
            )
        if response.status_code != 200:
            raise SourceAPIException(
                message=f"SC API returned {response.status_code} querying resource tags.",
                details={"endpoint": url, "body": response.text[:500]},
            )

        try:
            result = QueryResourceTagsResponse(**response.json())
        except Exception as exc:
            raise SourceAPIException(
                message="Failed to parse resource tags response.",
                details={"endpoint": url, "error": str(exc)},
            ) from exc

        logger.info("Resource tags queried", extra={"total": result.total})
        return result

    # ── Tags: Query predefined tags — new (14.3) ──────────────────────

    async def fetch_predefined_tags(
        self,
        key: str | None = None,
        value: str | None = None,
        limit: int | None = None,
        marker: str | None = None,
        order_field: str | None = None,
        order_method: str | None = None,
    ) -> PreDefineTagsResponse:
        """
        Query predefined tags (new).

        GET https://{SC_DOMAIN}/v1.0/predefine_tags
        """
        if not self._is_token_valid():
            await self.authenticate()

        settings = get_settings()
        params: dict[str, Any] = {}
        if key is not None:
            params["key"] = key
        if value is not None:
            params["value"] = value
        if limit is not None:
            params["limit"] = limit
        if marker is not None:
            params["marker"] = marker
        if order_field is not None:
            params["order_field"] = order_field
        if order_method is not None:
            params["order_method"] = order_method

        base_url = f"{settings.sc_domain}{_PREDEFINE_TAGS_ENDPOINT}"
        url = f"{base_url}?{urlencode(params)}" if params else base_url

        logger.info("Fetching predefined tags (new)", extra={"url": base_url})

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
                message="SC API returned login redirect after re-auth.",
                details={"endpoint": base_url, "raw_body": response.text[:500]},
            )
        if response.status_code != 200:
            raise SourceAPIException(
                message=f"SC API returned {response.status_code} fetching predefined tags.",
                details={"endpoint": base_url, "body": response.text[:500]},
            )

        try:
            result = PreDefineTagsResponse(**response.json())
        except Exception as exc:
            raise SourceAPIException(
                message="Failed to parse predefined tags response.",
                details={"endpoint": base_url, "error": str(exc)},
            ) from exc

        logger.info("Predefined tags fetched", extra={"total": result.total_count})
        return result

    # ── Tags: Query list of tags (14.5) ───────────────────────────────

    async def fetch_tags(
        self,
        key: str | None = None,
        value: str | None = None,
        start: str | None = None,
        limit: str | None = None,
        order_field: str | None = None,
        order_method: str | None = None,
    ) -> ListTagsResponse:
        """
        Query the tag list with optional filtering, pagination, and sorting.

        GET https://{SC_DOMAIN}/rest/tag/v3.0/tags
        """
        if not self._is_token_valid():
            await self.authenticate()

        settings = get_settings()
        params: dict[str, Any] = {}
        if key is not None:
            params["key"] = key
        if value is not None:
            params["value"] = value
        if start is not None:
            params["start"] = start
        if limit is not None:
            params["limit"] = limit
        if order_field is not None:
            params["order_field"] = order_field
        if order_method is not None:
            params["order_method"] = order_method

        base_url = f"{settings.sc_domain}{_TAGS_ENDPOINT}"
        url = f"{base_url}?{urlencode(params)}" if params else base_url

        logger.info("Fetching tags list", extra={"url": base_url})

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
                message="SC API returned login redirect after re-auth.",
                details={"endpoint": base_url, "raw_body": response.text[:500]},
            )
        if response.status_code != 200:
            raise SourceAPIException(
                message=f"SC API returned {response.status_code} fetching tags.",
                details={"endpoint": base_url, "body": response.text[:500]},
            )

        try:
            result = ListTagsResponse(**response.json())
        except Exception as exc:
            raise SourceAPIException(
                message="Failed to parse tags response.",
                details={"endpoint": base_url, "error": str(exc)},
            ) from exc

        logger.info("Tags list fetched", extra={"total": result.total})
        return result

    # ── Tags: Create or delete in batches (14.6) ──────────────────────

    async def batch_create_delete_tags(self, action: str, tags: list[dict]) -> None:
        """
        Create or delete tags in batches.

        POST https://{SC_DOMAIN}/rest/tag/v3.0/tags
        """
        if not self._is_token_valid():
            await self.authenticate()

        settings = get_settings()
        url = f"{settings.sc_domain}{_TAGS_ENDPOINT}"

        body = {"action": action, "tags": tags}

        logger.info("Batch tag operation", extra={"url": url, "action": action})

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
                message="SC API returned login redirect after re-auth.",
                details={"endpoint": url, "raw_body": response.text[:500]},
            )
        if response.status_code not in (200, 204):
            raise SourceAPIException(
                message=f"SC API returned {response.status_code} in batch tag operation.",
                details={"endpoint": url, "body": response.text[:500]},
            )

        logger.info("Batch tag operation succeeded", extra={"action": action})

    # ── Tags: Verify permissions (14.7) ───────────────────────────────

    async def verify_tag_permissions(self, body: dict) -> None:
        """
        Verify permissions on resources before tag association/disassociation.

        POST https://{SC_DOMAIN}/rest/tag/v3.0/tags/authen
        """
        if not self._is_token_valid():
            await self.authenticate()

        settings = get_settings()
        url = f"{settings.sc_domain}{_TAGS_AUTHEN_ENDPOINT}"

        logger.info("Verifying tag permissions", extra={"url": url})

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
                message="SC API returned login redirect after re-auth.",
                details={"endpoint": url, "raw_body": response.text[:500]},
            )
        if response.status_code != 200:
            raise SourceAPIException(
                message=f"SC API returned {response.status_code} verifying tag permissions.",
                details={"endpoint": url, "body": response.text[:500]},
            )

        logger.info("Tag permissions verified successfully")
