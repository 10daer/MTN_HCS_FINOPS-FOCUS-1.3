"""
Pytest configuration & shared fixtures.
"""

from collections.abc import AsyncIterator

import httpx
import pytest_asyncio
from fastapi import FastAPI

from app.main import create_app


@pytest_asyncio.fixture
async def app() -> AsyncIterator[FastAPI]:
    """Provide a fresh FastAPI app with lifespan managed."""
    application = create_app()

    # Manually trigger lifespan so app.state.http_client is set
    async with httpx.AsyncClient(
        base_url="http://fake-source",
        timeout=httpx.Timeout(5),
    ) as mock_http:
        application.state.http_client = mock_http
        yield application


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """Provide an async test client."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac
