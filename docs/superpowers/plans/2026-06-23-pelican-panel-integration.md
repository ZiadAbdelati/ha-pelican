# Pelican Panel Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Home Assistant custom integration (`pelican`) that monitors and controls game servers managed by a Pelican Panel instance, via Pelican's Client API.

**Architecture:** A single config entry (one panel) creates one HA device per server. A `DataUpdateCoordinator` polls the panel every 60s (one server-list call + one `/resources` call per server). A small async API client (`aiohttp`, HA's shared session injected) talks to four Client API endpoints. Entities (binary_sensor, sensor, switch, button) are thin `CoordinatorEntity` subclasses driven by a normalized `PelicanData` dataclass.

**Tech Stack:** Python 3.12+, Home Assistant 2024.12+ (`runtime_data`, modern config-flow helpers), `aiohttp`. Dev/test: `pytest`, `pytest-asyncio`, `aioresponses`, `ruff`.

---

## Conventions

- **Every commit message** ends with this trailer (omitted from the per-step commands below for brevity):

  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  ```
- Run all commands from the repo root: `C:\Users\aliab\projects\ha-pelican`.
- The integration lives under `custom_components/pelican/` so the repo is HACS-installable as-is.

## Testing strategy (read once)

- **Pure logic** — `api.py` (`PelicanClient`, `PelicanData.from_api`) has **no Home Assistant imports** (the aiohttp session is injected). It is fully unit-tested with `pytest` + `aioresponses` on Windows. Follow TDD here: test first.
- **HA-glue** — `coordinator.py`, `entity.py`, platforms, `config_flow.py`, `__init__.py` import Home Assistant and are **not** unit-tested locally (the HA test harness is impractical on Windows). They are verified by: (1) `ruff check` + `python -m py_compile` (catches syntax errors, undefined names, unused imports without importing HA), and (2) the live end-to-end task at the end.
- **Optional CI** (Task 16) runs HA's `hassfest`, the HACS validator, and the unit tests on a Linux GitHub runner — the right place for full HA validation when publishing.

---

## Task 1: Scaffold project and dev environment

**Files:**
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `requirements-dev.txt`
- Create: `custom_components/pelican/const.py`
- Create: `tests/__init__.py` (empty)

- [ ] **Step 1: Create `.gitignore`**

```gitignore
__pycache__/
*.py[cod]
.venv/
venv/
.pytest_cache/
.ruff_cache/
*.egg-info/
.coverage
htmlcov/
.scratch/
```

- [ ] **Step 2: Create `requirements-dev.txt`**

```text
aiohttp
aioresponses
pytest
pytest-asyncio
ruff
```

- [ ] **Step 3: Create `pyproject.toml`**

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["."]
testpaths = ["tests"]

[tool.ruff]
target-version = "py312"
line-length = 100
```

- [ ] **Step 4: Create `custom_components/pelican/const.py`**

```python
"""Constants for the Pelican Panel integration."""

from homeassistant.const import Platform

DOMAIN = "pelican"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.SWITCH,
]
```

- [ ] **Step 5: Create empty `tests/__init__.py`**

Create the file with no content.

- [ ] **Step 6: Create and populate a virtual environment**

Run (PowerShell, from repo root):
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```
Expected: installs complete without error. Confirm with `.\.venv\Scripts\python.exe -m pytest --version` (prints a pytest version).

> Use `.\.venv\Scripts\python.exe` (or activate the venv) for all later `python`/`pytest`/`ruff` commands.

- [ ] **Step 7: Verify pytest collects cleanly (no tests yet)**

Run: `.\.venv\Scripts\python.exe -m pytest`
Expected: exit code 5, "no tests ran".

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "chore: scaffold project, dev env, and constants"
```

---

## Task 2: API exceptions and `PelicanData` (pure, TDD)

**Files:**
- Create: `custom_components/pelican/api.py`
- Create: `tests/test_data.py`

- [ ] **Step 1: Write the failing test** — `tests/test_data.py`

```python
"""Tests for PelicanData mapping (pure, no Home Assistant)."""

from custom_components.pelican.api import PelicanData

SERVER = {
    "identifier": "a1b2c3d4",
    "uuid": "a1b2c3d4-1111-2222-3333-444455556666",
    "name": "Example",
    "limits": {"memory": 256, "swap": 0, "disk": 512, "io": 500, "cpu": 200},
}
RESOURCES = {
    "current_state": "running",
    "is_suspended": False,
    "resources": {
        "memory_bytes": 134217728,
        "cpu_absolute": 25.5,
        "disk_bytes": 1048576,
        "network_rx_bytes": 2048,
        "network_tx_bytes": 4096,
        "uptime": 3600000,
    },
}


def test_from_api_maps_and_converts():
    data = PelicanData.from_api(SERVER, RESOURCES)
    assert data.identifier == "a1b2c3d4"
    assert data.uuid == "a1b2c3d4-1111-2222-3333-444455556666"
    assert data.name == "Example"
    assert data.state == "running"
    assert data.cpu == 25.5
    assert data.cpu_limit == 200.0
    assert data.memory == 134217728
    assert data.memory_limit == 256 * 1024 * 1024
    assert data.disk == 1048576
    assert data.disk_limit == 512 * 1024 * 1024
    assert data.network_rx == 2048
    assert data.network_tx == 4096
    assert data.uptime == 3600.0


def test_from_api_unlimited_limits_become_none():
    server = {**SERVER, "limits": {"memory": 0, "disk": 0, "cpu": 0}}
    data = PelicanData.from_api(server, RESOURCES)
    assert data.memory_limit is None
    assert data.disk_limit is None
    assert data.cpu_limit is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_data.py -v`
Expected: FAIL — `ModuleNotFoundError` / cannot import `PelicanData`.

- [ ] **Step 3: Create `custom_components/pelican/api.py` with exceptions and the dataclass**

```python
"""Async client and data model for the Pelican Panel client API.

This module intentionally has no Home Assistant imports: the aiohttp session is
injected by the caller, so the logic here is unit-testable in isolation.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import aiohttp

REQUEST_TIMEOUT = 30


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

        def mb_to_bytes(value: object) -> int | None:
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_data.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add custom_components/pelican/api.py tests/test_data.py
git commit -m "feat(api): add exceptions and PelicanData mapping"
```

---

## Task 3: `PelicanClient` HTTP methods (pure, TDD)

**Files:**
- Modify: `custom_components/pelican/api.py` (append the client class)
- Create: `tests/test_api.py`

- [ ] **Step 1: Write the failing test** — `tests/test_api.py`

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_api.py -v`
Expected: FAIL — cannot import `PelicanClient`.

- [ ] **Step 3: Append `PelicanClient` to `custom_components/pelican/api.py`**

Add at the end of the file:

```python
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
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                if resp.status == 401:
                    raise PelicanAuthError("Invalid API key")
                if resp.status >= 400:
                    raise PelicanConnectionError(f"HTTP {resp.status}")
                if method == "POST" or resp.status == 204:
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
        return data["attributes"]

    async def async_send_power(self, identifier: str, signal: str) -> None:
        """Send a power signal: start | stop | restart | kill."""
        await self._request(
            "POST",
            f"/api/client/servers/{identifier}/power",
            json={"signal": signal},
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest -v`
Expected: PASS (all tests, including Task 2's).

- [ ] **Step 5: Lint**

Run: `.\.venv\Scripts\ruff.exe check custom_components/pelican/api.py`
Expected: "All checks passed!"

- [ ] **Step 6: Commit**

```bash
git add custom_components/pelican/api.py tests/test_api.py
git commit -m "feat(api): add async PelicanClient for the four client endpoints"
```

---

## Task 4: Manifest and HACS metadata

**Files:**
- Create: `custom_components/pelican/manifest.json`
- Create: `hacs.json`

- [ ] **Step 1: Create `custom_components/pelican/manifest.json`**

```json
{
  "domain": "pelican",
  "name": "Pelican Panel",
  "codeowners": ["@ZiadAbdelati"],
  "config_flow": true,
  "documentation": "https://github.com/ZiadAbdelati/ha-pelican",
  "integration_type": "service",
  "iot_class": "local_polling",
  "issue_tracker": "https://github.com/ZiadAbdelati/ha-pelican/issues",
  "requirements": [],
  "version": "0.1.0"
}
```

- [ ] **Step 2: Create `hacs.json`**

```json
{
  "name": "Pelican Panel",
  "homeassistant": "2024.12.0",
  "render_readme": true
}
```

- [ ] **Step 3: Validate JSON**

Run:
```powershell
.\.venv\Scripts\python.exe -m json.tool custom_components/pelican/manifest.json
.\.venv\Scripts\python.exe -m json.tool hacs.json
```
Expected: both pretty-print without error.

- [ ] **Step 4: Commit**

```bash
git add custom_components/pelican/manifest.json hacs.json
git commit -m "feat: add integration manifest and HACS metadata"
```

---

## Task 5: Data update coordinator

**Files:**
- Create: `custom_components/pelican/coordinator.py`

- [ ] **Step 1: Create `custom_components/pelican/coordinator.py`**

```python
"""Data update coordinator for the Pelican Panel integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    PelicanAuthError,
    PelicanClient,
    PelicanConnectionError,
    PelicanData,
)

SCAN_INTERVAL = timedelta(seconds=60)
_LOGGER = logging.getLogger(__name__)

type PelicanConfigEntry = ConfigEntry[PelicanCoordinator]


class PelicanCoordinator(DataUpdateCoordinator[dict[str, PelicanData]]):
    """Polls a Pelican panel for all servers the API key can access."""

    config_entry: PelicanConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: PelicanConfigEntry
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=config_entry.data[CONF_URL],
            config_entry=config_entry,
            update_interval=SCAN_INTERVAL,
        )
        self.base_url = config_entry.data[CONF_URL].rstrip("/")
        self.client = PelicanClient(
            async_get_clientsession(hass),
            self.base_url,
            config_entry.data[CONF_API_KEY],
        )

    async def _async_update_data(self) -> dict[str, PelicanData]:
        try:
            servers = await self.client.async_get_servers()
            result: dict[str, PelicanData] = {}
            for server in servers:
                identifier = server["identifier"]
                resources = await self.client.async_get_utilization(identifier)
                result[identifier] = PelicanData.from_api(server, resources)
            return result
        except PelicanAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except PelicanConnectionError as err:
            raise UpdateFailed(str(err)) from err

    async def async_send_power(self, identifier: str, signal: str) -> None:
        """Send a power signal, then refresh so entities update promptly."""
        try:
            await self.client.async_send_power(identifier, signal)
        except PelicanAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except PelicanConnectionError as err:
            raise UpdateFailed(str(err)) from err
        await self.async_request_refresh()
```

- [ ] **Step 2: Static check**

Run:
```powershell
.\.venv\Scripts\ruff.exe check custom_components/pelican/coordinator.py
.\.venv\Scripts\python.exe -m py_compile custom_components/pelican/coordinator.py
```
Expected: ruff "All checks passed!"; py_compile no output (success).

- [ ] **Step 3: Commit**

```bash
git add custom_components/pelican/coordinator.py
git commit -m "feat: add Pelican data update coordinator"
```

---

## Task 6: Base entity

**Files:**
- Create: `custom_components/pelican/entity.py`

- [ ] **Step 1: Create `custom_components/pelican/entity.py`**

```python
"""Base entity for the Pelican Panel integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import PelicanData
from .const import DOMAIN
from .coordinator import PelicanCoordinator


class PelicanEntity(CoordinatorEntity[PelicanCoordinator]):
    """Base class for entities tied to a single Pelican server."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PelicanCoordinator, identifier: str) -> None:
        super().__init__(coordinator)
        self._identifier = identifier
        server = coordinator.data[identifier]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, server.uuid)},
            name=server.name,
            manufacturer="Pelican",
            model="Game Server",
            configuration_url=f"{coordinator.base_url}/server/{identifier}",
        )

    @property
    def data(self) -> PelicanData:
        """Current data for this server."""
        return self.coordinator.data[self._identifier]

    @property
    def available(self) -> bool:
        return super().available and self._identifier in self.coordinator.data
```

- [ ] **Step 2: Static check**

Run:
```powershell
.\.venv\Scripts\ruff.exe check custom_components/pelican/entity.py
.\.venv\Scripts\python.exe -m py_compile custom_components/pelican/entity.py
```
Expected: pass.

- [ ] **Step 3: Commit**

```bash
git add custom_components/pelican/entity.py
git commit -m "feat: add base Pelican entity with per-server device info"
```

---

## Task 7: Integration setup/unload

**Files:**
- Create: `custom_components/pelican/__init__.py`

- [ ] **Step 1: Create `custom_components/pelican/__init__.py`**

```python
"""The Pelican Panel integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import PelicanConfigEntry, PelicanCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: PelicanConfigEntry) -> bool:
    """Set up Pelican Panel from a config entry."""
    coordinator = PelicanCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PelicanConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
```

- [ ] **Step 2: Static check**

Run:
```powershell
.\.venv\Scripts\ruff.exe check custom_components/pelican/__init__.py
.\.venv\Scripts\python.exe -m py_compile custom_components/pelican/__init__.py
```
Expected: pass.

- [ ] **Step 3: Commit**

```bash
git add custom_components/pelican/__init__.py
git commit -m "feat: wire up config entry setup and unload"
```

---

## Task 8: Binary sensor (Running)

**Files:**
- Create: `custom_components/pelican/binary_sensor.py`

- [ ] **Step 1: Create `custom_components/pelican/binary_sensor.py`**

```python
"""Binary sensor platform for Pelican Panel: server running state."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PelicanConfigEntry, PelicanCoordinator
from .entity import PelicanEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PelicanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the running binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        PelicanRunningSensor(coordinator, identifier)
        for identifier in coordinator.data
    )


class PelicanRunningSensor(PelicanEntity, BinarySensorEntity):
    """Reports whether a server is running."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_translation_key = "running"

    def __init__(self, coordinator: PelicanCoordinator, identifier: str) -> None:
        super().__init__(coordinator, identifier)
        self._attr_unique_id = f"{identifier}_running"

    @property
    def is_on(self) -> bool:
        return self.data.state == "running"
```

- [ ] **Step 2: Static check**

Run:
```powershell
.\.venv\Scripts\ruff.exe check custom_components/pelican/binary_sensor.py
.\.venv\Scripts\python.exe -m py_compile custom_components/pelican/binary_sensor.py
```
Expected: pass.

- [ ] **Step 3: Commit**

```bash
git add custom_components/pelican/binary_sensor.py
git commit -m "feat: add running binary sensor"
```

---

## Task 9: Sensors (status, CPU, memory, disk, network, uptime)

**Files:**
- Create: `custom_components/pelican/sensor.py`

- [ ] **Step 1: Create `custom_components/pelican/sensor.py`**

```python
"""Sensor platform for Pelican Panel servers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import PelicanData
from .coordinator import PelicanConfigEntry, PelicanCoordinator
from .entity import PelicanEntity


@dataclass(frozen=True, kw_only=True)
class PelicanSensorDescription(SensorEntityDescription):
    """Sensor description with a value extractor."""

    value_fn: Callable[[PelicanData], float | int | str | datetime | None]
    attrs_fn: Callable[[PelicanData], dict[str, Any]] | None = None


def _uptime(data: PelicanData) -> datetime | None:
    if data.state != "running" or not data.uptime:
        return None
    return dt_util.utcnow() - timedelta(seconds=data.uptime)


SENSORS: tuple[PelicanSensorDescription, ...] = (
    PelicanSensorDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=["running", "starting", "stopping", "offline"],
        value_fn=lambda d: d.state,
    ),
    PelicanSensorDescription(
        key="cpu",
        translation_key="cpu",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.cpu,
        attrs_fn=lambda d: {"limit": d.cpu_limit},
    ),
    PelicanSensorDescription(
        key="memory",
        translation_key="memory",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda d: d.memory,
        attrs_fn=lambda d: {"limit": d.memory_limit},
    ),
    PelicanSensorDescription(
        key="disk",
        translation_key="disk",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda d: d.disk,
        attrs_fn=lambda d: {"limit": d.disk_limit},
    ),
    PelicanSensorDescription(
        key="network_rx",
        translation_key="network_rx",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda d: d.network_rx,
    ),
    PelicanSensorDescription(
        key="network_tx",
        translation_key="network_tx",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda d: d.network_tx,
    ),
    PelicanSensorDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_uptime,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PelicanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Pelican sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        PelicanSensor(coordinator, identifier, description)
        for identifier in coordinator.data
        for description in SENSORS
    )


class PelicanSensor(PelicanEntity, SensorEntity):
    """A single Pelican server metric."""

    entity_description: PelicanSensorDescription

    def __init__(
        self,
        coordinator: PelicanCoordinator,
        identifier: str,
        description: PelicanSensorDescription,
    ) -> None:
        super().__init__(coordinator, identifier)
        self.entity_description = description
        self._attr_unique_id = f"{identifier}_{description.key}"

    @property
    def native_value(self) -> float | int | str | datetime | None:
        return self.entity_description.value_fn(self.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.data)
```

- [ ] **Step 2: Static check**

Run:
```powershell
.\.venv\Scripts\ruff.exe check custom_components/pelican/sensor.py
.\.venv\Scripts\python.exe -m py_compile custom_components/pelican/sensor.py
```
Expected: pass.

- [ ] **Step 3: Commit**

```bash
git add custom_components/pelican/sensor.py
git commit -m "feat: add server resource sensors"
```

---

## Task 10: Power switch

**Files:**
- Create: `custom_components/pelican/switch.py`

- [ ] **Step 1: Create `custom_components/pelican/switch.py`**

```python
"""Switch platform for Pelican Panel: power a server on/off."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PelicanConfigEntry, PelicanCoordinator
from .entity import PelicanEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PelicanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the power switches."""
    coordinator = entry.runtime_data
    async_add_entities(
        PelicanPowerSwitch(coordinator, identifier)
        for identifier in coordinator.data
    )


class PelicanPowerSwitch(PelicanEntity, SwitchEntity):
    """Start/stop a server via a switch."""

    _attr_translation_key = "power"

    def __init__(self, coordinator: PelicanCoordinator, identifier: str) -> None:
        super().__init__(coordinator, identifier)
        self._attr_unique_id = f"{identifier}_power"

    @property
    def is_on(self) -> bool:
        return self.data.state in ("running", "starting")

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_send_power(self._identifier, "start")

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_send_power(self._identifier, "stop")
```

- [ ] **Step 2: Static check**

Run:
```powershell
.\.venv\Scripts\ruff.exe check custom_components/pelican/switch.py
.\.venv\Scripts\python.exe -m py_compile custom_components/pelican/switch.py
```
Expected: pass.

- [ ] **Step 3: Commit**

```bash
git add custom_components/pelican/switch.py
git commit -m "feat: add power switch (start/stop)"
```

---

## Task 11: Power buttons

**Files:**
- Create: `custom_components/pelican/button.py`

- [ ] **Step 1: Create `custom_components/pelican/button.py`**

```python
"""Button platform for Pelican Panel: power signals."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PelicanConfigEntry, PelicanCoordinator
from .entity import PelicanEntity


@dataclass(frozen=True, kw_only=True)
class PelicanButtonDescription(ButtonEntityDescription):
    """Button description carrying the power signal to send."""

    signal: str


BUTTONS: tuple[PelicanButtonDescription, ...] = (
    PelicanButtonDescription(key="start", translation_key="start", signal="start"),
    PelicanButtonDescription(key="stop", translation_key="stop", signal="stop"),
    PelicanButtonDescription(
        key="restart",
        translation_key="restart",
        device_class=ButtonDeviceClass.RESTART,
        signal="restart",
    ),
    PelicanButtonDescription(key="kill", translation_key="kill", signal="kill"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PelicanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the power buttons."""
    coordinator = entry.runtime_data
    async_add_entities(
        PelicanButton(coordinator, identifier, description)
        for identifier in coordinator.data
        for description in BUTTONS
    )


class PelicanButton(PelicanEntity, ButtonEntity):
    """Sends a single power signal when pressed."""

    entity_description: PelicanButtonDescription

    def __init__(
        self,
        coordinator: PelicanCoordinator,
        identifier: str,
        description: PelicanButtonDescription,
    ) -> None:
        super().__init__(coordinator, identifier)
        self.entity_description = description
        self._attr_unique_id = f"{identifier}_{description.key}"

    async def async_press(self) -> None:
        await self.coordinator.async_send_power(
            self._identifier, self.entity_description.signal
        )
```

- [ ] **Step 2: Static check**

Run:
```powershell
.\.venv\Scripts\ruff.exe check custom_components/pelican/button.py
.\.venv\Scripts\python.exe -m py_compile custom_components/pelican/button.py
```
Expected: pass.

- [ ] **Step 3: Commit**

```bash
git add custom_components/pelican/button.py
git commit -m "feat: add power buttons (start/stop/restart/kill)"
```

---

## Task 12: Config flow and strings

**Files:**
- Create: `custom_components/pelican/config_flow.py`
- Create: `custom_components/pelican/strings.json`

- [ ] **Step 1: Create `custom_components/pelican/config_flow.py`**

```python
"""Config flow for the Pelican Panel integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PelicanAuthError, PelicanClient, PelicanConnectionError
from .const import DOMAIN

USER_SCHEMA = vol.Schema(
    {vol.Required(CONF_URL): str, vol.Required(CONF_API_KEY): str}
)
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


class PelicanConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Pelican Panel config flow."""

    async def _validate(self, url: str, api_key: str) -> dict[str, str]:
        """Return an errors dict ({} means success)."""
        client = PelicanClient(async_get_clientsession(self.hass), url, api_key)
        errors: dict[str, str] = {}
        try:
            await client.async_get_servers()
        except PelicanAuthError:
            errors["base"] = "invalid_auth"
        except PelicanConnectionError:
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            errors["base"] = "unknown"
        return errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()
            errors = await self._validate(url, user_input[CONF_API_KEY])
            if not errors:
                return self.async_create_entry(
                    title=url,
                    data={CONF_URL: url, CONF_API_KEY: user_input[CONF_API_KEY]},
                )
        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            errors = await self._validate(
                reauth_entry.data[CONF_URL], user_input[CONF_API_KEY]
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_API_KEY: user_input[CONF_API_KEY]},
                )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=REAUTH_SCHEMA, errors=errors
        )
```

- [ ] **Step 2: Create `custom_components/pelican/strings.json`**

```json
{
  "config": {
    "step": {
      "user": {
        "data": {
          "url": "URL",
          "api_key": "API key"
        },
        "data_description": {
          "url": "Base URL of your Pelican panel, e.g. https://panel.example.com",
          "api_key": "A client API key from your panel: Profile → API Keys"
        }
      },
      "reauth_confirm": {
        "description": "The API key for {url} is no longer valid. Enter a new one.",
        "data": {
          "api_key": "API key"
        }
      }
    },
    "error": {
      "invalid_auth": "Invalid API key",
      "cannot_connect": "Failed to connect",
      "unknown": "Unexpected error"
    },
    "abort": {
      "already_configured": "This panel is already configured",
      "reauth_successful": "Re-authentication was successful"
    }
  },
  "entity": {
    "binary_sensor": {
      "running": { "name": "Running" }
    },
    "switch": {
      "power": { "name": "Power" }
    },
    "button": {
      "start": { "name": "Start" },
      "stop": { "name": "Stop" },
      "restart": { "name": "Restart" },
      "kill": { "name": "Kill" }
    },
    "sensor": {
      "status": {
        "name": "Status",
        "state": {
          "running": "Running",
          "starting": "Starting",
          "stopping": "Stopping",
          "offline": "Offline"
        }
      },
      "cpu": { "name": "CPU utilization" },
      "memory": { "name": "Memory" },
      "disk": { "name": "Disk" },
      "network_rx": { "name": "Network in" },
      "network_tx": { "name": "Network out" },
      "uptime": { "name": "Uptime" }
    }
  }
}
```

- [ ] **Step 3: Static checks**

Run:
```powershell
.\.venv\Scripts\ruff.exe check custom_components/pelican/config_flow.py
.\.venv\Scripts\python.exe -m py_compile custom_components/pelican/config_flow.py
.\.venv\Scripts\python.exe -m json.tool custom_components/pelican/strings.json
```
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add custom_components/pelican/config_flow.py custom_components/pelican/strings.json
git commit -m "feat: add config flow with reauth and UI strings"
```

---

## Task 13: Entity icons

**Files:**
- Create: `custom_components/pelican/icons.json`

- [ ] **Step 1: Create `custom_components/pelican/icons.json`**

```json
{
  "entity": {
    "switch": {
      "power": { "default": "mdi:power" }
    },
    "button": {
      "start": { "default": "mdi:play" },
      "stop": { "default": "mdi:stop" },
      "restart": { "default": "mdi:restart" },
      "kill": { "default": "mdi:skull" }
    },
    "sensor": {
      "status": { "default": "mdi:server" },
      "cpu": { "default": "mdi:chip" },
      "memory": { "default": "mdi:memory" },
      "disk": { "default": "mdi:harddisk" },
      "network_rx": { "default": "mdi:download-network" },
      "network_tx": { "default": "mdi:upload-network" },
      "uptime": { "default": "mdi:clock-outline" }
    }
  }
}
```

- [ ] **Step 2: Validate JSON**

Run: `.\.venv\Scripts\python.exe -m json.tool custom_components/pelican/icons.json`
Expected: pretty-prints.

- [ ] **Step 3: Commit**

```bash
git add custom_components/pelican/icons.json
git commit -m "feat: add entity icons"
```

---

## Task 14: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create `README.md`**

````markdown
# Pelican Panel — Home Assistant integration

Monitor and control [Pelican Panel](https://pelican.dev) game servers from Home Assistant.

Adapted from Home Assistant's official `pterodactyl` integration. Pelican keeps
Pterodactyl's Client API shape, so this talks to the same endpoints
(`/api/client/...`) with a native async client.

## Features

Per server (one HA device each):

- **Running** binary sensor
- **Power** switch (on = start, off = stop)
- **Start / Stop / Restart / Kill** buttons
- **Status, CPU, Memory, Disk, Network in/out, Uptime** sensors

## Requirements

- Home Assistant 2024.12 or newer
- A Pelican Panel instance and a **client API key**

## Getting a client API key

In your Pelican panel: **profile menu (top-right) → API Keys** (not the admin
"Application API"). Give it a description; leave Allowed IPs blank or restrict it
to your Home Assistant host. Copy the `pacc_...` key — it's shown once.

The key acts as your user account, so create it under an account that owns (or is
a subuser of) the servers you want in Home Assistant.

## Installation

### HACS (custom repository)

1. HACS → ⋮ → **Custom repositories**.
2. Add `https://github.com/ZiadAbdelati/ha-pelican`, category **Integration**.
3. Install **Pelican Panel**, then restart Home Assistant.

### Manual

Copy `custom_components/pelican` into your Home Assistant `config/custom_components/`
directory and restart.

## Configuration

**Settings → Devices & Services → Add Integration → Pelican Panel.** Enter your
panel URL (e.g. `https://panel.example.com`) and the client API key.

## Disclaimer

Not affiliated with the Pelican project. Provided as-is.
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README"
```

---

## Task 15: Live end-to-end verification

No code. Verify against the real panel (`https://panel.example.com`). The
`Example` server (currently `offline`) is a safe target for the power test.

- [ ] **Step 1: Run the full unit suite and lint once more**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\ruff.exe check custom_components
```
Expected: all tests pass; lint clean.

- [ ] **Step 2: Deploy to Home Assistant**

Copy `custom_components/pelican/` into the HA `config/custom_components/` directory
(via Samba/File editor add-on, or install the pushed repo through HACS), then
restart Home Assistant.

- [ ] **Step 3: Add the integration**

Settings → Devices & Services → **Add Integration** → **Pelican Panel** → enter
`https://panel.example.com` and the client API key. Expected: entry is created
and one device per server appears.

- [ ] **Step 4: Confirm entities populate**

Open the `Example` device. Expected: Status = `offline`, Running = off, resource
sensors present, Power switch off, four buttons present.

- [ ] **Step 5: Test power control (the new switch)**

Toggle the **Power** switch on. Within ~60s (or immediately, since the coordinator
refreshes after a power signal) expect Status → `starting`/`running` and Running →
on. Toggle off and confirm it stops. Optionally confirm the same server's state in
the Pelican web UI.

- [ ] **Step 6: Check the log**

Settings → System → Logs. Expected: no errors mentioning `custom_components.pelican`.

- [ ] **Step 7: Note results**

If anything misbehaves, capture the log line and the failing entity; fix the
relevant source file and re-deploy. Common culprits: an unexpected `current_state`
value (add it to the `status` sensor `options` and `strings.json` states) or a
panel URL with a trailing path.

---

## Task 16 (optional): GitHub Actions CI for publishing

Adds Linux-based validation (hassfest + HACS + unit tests). Do this when you push
the repo to GitHub for sharing.

**Files:**
- Create: `.github/workflows/validate.yml`

- [ ] **Step 1: Create `.github/workflows/validate.yml`**

```yaml
name: Validate

on:
  push:
  pull_request:

jobs:
  hassfest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: home-assistant/actions/hassfest@master

  hacs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hacs/action@main
        with:
          category: integration

  tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements-dev.txt
      - run: ruff check custom_components
      - run: pytest
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/validate.yml
git commit -m "ci: validate with hassfest, HACS, and unit tests"
```

---

## Definition of done

- `pytest` green; `ruff check custom_components` clean.
- Integration loads in Home Assistant with no errors; one device per server.
- All entities populate; the Power switch starts and stops a server.
- (For publishing) Task 16 CI is green on GitHub.
