"""Tests for PelicanClient using a mocked aiohttp backend."""

import aiohttp
import pytest
from aioresponses import aioresponses
from yarl import URL

from custom_components.pelican.api import (
    PelicanAuthError,
    PelicanClient,
    PelicanConnectionError,
)

BASE = "https://panel.example.com"


@pytest.fixture
async def client():
    async with aiohttp.ClientSession() as session:
        yield PelicanClient(session, BASE, "testkey")


async def test_get_servers_parses_attributes(client):
    with aioresponses() as m:
        m.get(
            f"{BASE}/api/client",
            payload={"data": [{"attributes": {"identifier": "abc", "uuid": "u", "name": "S"}}]},
        )
        servers = await client.async_get_servers()
    assert servers == [{"identifier": "abc", "uuid": "u", "name": "S"}]


async def test_get_utilization_returns_attributes(client):
    with aioresponses() as m:
        m.get(
            f"{BASE}/api/client/servers/abc/resources",
            payload={"attributes": {"current_state": "running", "resources": {}}},
        )
        util = await client.async_get_utilization("abc")
    assert util["current_state"] == "running"
    assert "resources" in util


async def test_send_power_posts_signal(client):
    with aioresponses() as m:
        m.post(f"{BASE}/api/client/servers/abc/power", status=204)
        await client.async_send_power("abc", "start")
    request = m.requests[("POST", URL(f"{BASE}/api/client/servers/abc/power"))][0]
    assert request.kwargs["json"] == {"signal": "start"}


async def test_401_raises_auth_error(client):
    with aioresponses() as m:
        m.get(f"{BASE}/api/client", status=401)
        with pytest.raises(PelicanAuthError):
            await client.async_get_servers()


async def test_http_error_raises_connection_error(client):
    with aioresponses() as m:
        m.get(f"{BASE}/api/client", status=500)
        with pytest.raises(PelicanConnectionError):
            await client.async_get_servers()


async def test_client_error_raises_connection_error(client):
    with aioresponses() as m:
        m.get(f"{BASE}/api/client", exception=aiohttp.ClientConnectionError("boom"))
        with pytest.raises(PelicanConnectionError):
            await client.async_get_servers()
