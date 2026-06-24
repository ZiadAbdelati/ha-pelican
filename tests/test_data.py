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
