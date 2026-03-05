"""
Tests for the /api/v1/transform endpoint.
"""

import pytest
import httpx


@pytest.mark.asyncio
async def test_health_check(client: httpx.AsyncClient) -> None:
    """Health endpoint should return 200 with app info."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


@pytest.mark.asyncio
async def test_transform_missing_required_fields(client: httpx.AsyncClient) -> None:
    """Transform should return 422 when required fields are missing."""
    response = await client.post("/api/v1/transform/", json={})
    assert response.status_code == 422
    data = response.json()
    assert data["error"] is True
    assert data["error_code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_transform_invalid_limit(client: httpx.AsyncClient) -> None:
    """Transform should return 422 for limit < 1."""
    response = await client.post(
        "/api/v1/transform/",
        json={
            "region_code": "test",
            "domain_id": "test",
            "start_time": "2025-04-01 00:00:00",
            "end_time": "2025-04-02 00:00:00",
            "resource_type_code": "hws.resource.type.volume",
            "limit": 0,
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"] is True
