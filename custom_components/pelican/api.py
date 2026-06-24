"""Async client and data model for the Pelican Panel client API.

This module intentionally has no Home Assistant imports: the aiohttp session is
injected by the caller, so the logic here is unit-testable in isolation.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import aiohttp

REQUEST_TIMEOUT_SECONDS = 30


class PelicanError(Exception):
    """Base error for the Pelican client."""


class PelicanAuthError(PelicanError):
    """Raised when the API key is rejected (HTTP 401)."""


class PelicanConnectionError(PelicanError):
    """Raised when the panel cannot be reached or returns an error."""


@dataclass
class PelicanData:
    """Normalized state for a single server."""

    identifier: str
    uuid: str
    name: str
    state: str
    cpu: float
    cpu_limit: float | None
    memory: int
    memory_limit: int | None
    disk: int
    disk_limit: int | None
    network_rx: int
    network_tx: int
    uptime: float

    @classmethod
    def from_api(cls, server: dict, resources: dict) -> PelicanData:
        """Build from a server-list ``attributes`` dict and a resources ``attributes`` dict."""
        res = resources.get("resources", {})
        limits = server.get("limits", {})

        def mb_to_bytes(value: int | None) -> int | None:
            return int(value) * 1024 * 1024 if value else None

        return cls(
            identifier=server["identifier"],
            uuid=server["uuid"],
            name=server["name"],
            state=resources.get("current_state", "unknown"),
            cpu=float(res.get("cpu_absolute", 0.0)),
            cpu_limit=float(limits["cpu"]) if limits.get("cpu") else None,
            memory=int(res.get("memory_bytes", 0)),
            memory_limit=mb_to_bytes(limits.get("memory")),
            disk=int(res.get("disk_bytes", 0)),
            disk_limit=mb_to_bytes(limits.get("disk")),
            network_rx=int(res.get("network_rx_bytes", 0)),
            network_tx=int(res.get("network_tx_bytes", 0)),
            uptime=float(res.get("uptime", 0)) / 1000.0,
        )


class PelicanClient:
    """Minimal async wrapper over the Pelican Panel client API."""

    def __init__(
        self, session: aiohttp.ClientSession, base_url: str, api_key: str
    ) -> None:
        self._session = session
        self._base = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, json: dict | None = None) -> dict:
        url = f"{self._base}{path}"
        try:
            async with self._session.request(
                method,
                url,
                headers=self._headers,
                json=json,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS),
            ) as resp:
                if resp.status == 401:
                    raise PelicanAuthError("Invalid API key")
                if resp.status >= 400:
                    raise PelicanConnectionError(f"HTTP {resp.status}")
                if resp.status == 204 or (method == "POST" and resp.status < 400):
                    return {}
                return await resp.json()
        except PelicanError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise PelicanConnectionError(str(err)) from err

    async def async_get_servers(self) -> list[dict]:
        """Return each accessible server's ``attributes`` dict."""
        data = await self._request("GET", "/api/client")
        return [item["attributes"] for item in data.get("data", [])]

    async def async_get_utilization(self, identifier: str) -> dict:
        """Return the resources ``attributes`` (current_state + resources block)."""
        data = await self._request(
            "GET", f"/api/client/servers/{identifier}/resources"
        )
        try:
            return data["attributes"]
        except KeyError as err:
            raise PelicanConnectionError(
                "Unexpected response from resources endpoint"
            ) from err

    async def async_send_power(self, identifier: str, signal: str) -> None:
        """Send a power signal: start | stop | restart | kill."""
        await self._request(
            "POST",
            f"/api/client/servers/{identifier}/power",
            json={"signal": signal},
        )
