"""
Tests for HCSClient.
"""

import pytest
import httpx

from app.core.exceptions import (
    AuthenticationException,
    SourceAPITimeoutException,
    SourceAPIException,
)
from app.services.source_client import HCSClient


@pytest.mark.asyncio
async def test_fetch_metrics_timeout() -> None:
    """Should raise SourceAPITimeoutException on timeout."""

    async def _timeout_handler(request: httpx.Request) -> httpx.Response:
        # IAM auth succeeds, metrics times out
        if "/v3/auth/tokens" in str(request.url):
            return httpx.Response(
                201,
                json={},
                headers={"X-Subject-Token": "test-token"},
            )
        raise httpx.ReadTimeout("timed out")

    transport = httpx.MockTransport(_timeout_handler)
    async with httpx.AsyncClient(transport=transport) as hc:
        client = HCSClient(http_client=hc)
        with pytest.raises(SourceAPITimeoutException):
            await client.fetch_metrics(
                region_code="test-region",
                domain_id="test-domain",
                start_time="2025-04-01 00:00:00",
                end_time="2025-04-02 00:00:00",
                resource_type_code="hws.resource.type.volume",
            )


@pytest.mark.asyncio
async def test_fetch_metrics_http_error() -> None:
    """Should raise SourceAPIException on 500 from SC API."""

    def _handler(request: httpx.Request) -> httpx.Response:
        if "/v3/auth/tokens" in str(request.url):
            return httpx.Response(
                201,
                json={},
                headers={"X-Subject-Token": "test-token"},
            )
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(_handler)
    async with httpx.AsyncClient(transport=transport) as hc:
        client = HCSClient(http_client=hc)
        with pytest.raises(SourceAPIException):
            await client.fetch_metrics(
                region_code="test-region",
                domain_id="test-domain",
                start_time="2025-04-01 00:00:00",
                end_time="2025-04-02 00:00:00",
                resource_type_code="hws.resource.type.volume",
            )


@pytest.mark.asyncio
async def test_fetch_metrics_success() -> None:
    """Should parse valid HCS metrics response."""

    metrics_payload = {
        "metrics": [
            {
                "id": "c9e7dd89-70b1-46a0-8851-f519c07610c4",
                "record_type": "20",
                "user_id": "user-1",
                "region_code": "whdevp-env-5",
                "az_code": "az5.dc5",
                "cloud_service_type_code": "hws.service.type.evs",
                "resource_type_code": "hws.resource.type.volume",
                "resource_spec_code": "IPSAN",
                "resource_id": "4dcfaecc-ec31-424f-9811-32f33c811ce1",
                "resource_display_name": "xp02-volume-0000",
                "start_time": "2025-04-01 00:00:00",
                "end_time": "2025-04-02 00:00:00",
                "tag": "",
                "upper_vdc_id": "eba900c3",
                "vdc_id": "eba900c3",
                "enterprise_project_id": "0",
                "price": "4",
                "usage_duration": 86400,
                "accumulate_mode": "DURATION",
                "price_unit": "GB",
                "usage_value": 8,
            }
        ],
        "time_zone": "Africa/Lagos",
        "start_time": "2025-04-01 00:00:00",
        "end_time": "2025-04-02 00:00:00",
        "total": 1,
        "marker": "",
    }

    def _handler(request: httpx.Request) -> httpx.Response:
        if "/v3/auth/tokens" in str(request.url):
            return httpx.Response(
                201,
                json={},
                headers={"X-Subject-Token": "test-token"},
            )
        return httpx.Response(200, json=metrics_payload)

    transport = httpx.MockTransport(_handler)
    async with httpx.AsyncClient(transport=transport) as hc:
        client = HCSClient(http_client=hc)
        records = await client.fetch_metrics(
            region_code="whdevp-env-5",
            domain_id="test-domain",
            start_time="2025-04-01 00:00:00",
            end_time="2025-04-02 00:00:00",
            resource_type_code="hws.resource.type.volume",
        )
        assert len(records) == 1
        assert records[0].id == "c9e7dd89-70b1-46a0-8851-f519c07610c4"
        assert records[0].resource_display_name == "xp02-volume-0000"


@pytest.mark.asyncio
async def test_authenticate_failure() -> None:
    """Should raise AuthenticationException on IAM 401."""

    transport = httpx.MockTransport(
        lambda req: httpx.Response(401, text="Unauthorized")
    )
    async with httpx.AsyncClient(transport=transport) as hc:
        client = HCSClient(http_client=hc)
        with pytest.raises(AuthenticationException):
            await client.authenticate()
