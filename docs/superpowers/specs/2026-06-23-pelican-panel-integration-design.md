# Pelican Panel — Home Assistant Integration (Design)

**Date:** 2026-06-23
**Status:** Approved, ready for implementation planning

## Goal

A Home Assistant integration that monitors and controls game servers managed by
[Pelican Panel](https://pelican.dev), adapted from the official Home Assistant
`pterodactyl` integration. Personal use first (installed as a custom component),
written cleanly enough to publish via HACS later with only README/polish work.

## Background

Pelican Panel is a successor to Pterodactyl Panel and deliberately preserves the
Pterodactyl **Client API** surface. Verified against Pelican's
`routes/api-client.php`, all four endpoints the original integration uses exist
at identical paths:

| Purpose | Endpoint |
|---|---|
| List servers | `GET /api/client` |
| Server details | `GET /api/client/servers/{server:uuid}` |
| Resource utilization | `GET /api/client/servers/{server:uuid}/resources` |
| Power signal | `POST /api/client/servers/{server:uuid}/power` |

Auth is a client API key sent as `Authorization: Bearer <key>`. Responses use the
same Fractal envelope as Pterodactyl (`object` + `attributes`, with a `resources`
block for utilization), so field-level parsing carries over.

**Routing (confirmed against a live panel 2026-06-23):** although the route is
declared `{server:uuid}`, Pelican resolves *both* the full `uuid` and the short
8-char `identifier` (both return `200`). We route by `identifier` — matching the
original integration and using it as the entity unique_id — with `uuid` kept for
device metadata.

## Scope

**In scope — parity with the original, plus a power switch.** One HA *device* per
server, exposing:

| Platform | Entity | Source / behavior |
|---|---|---|
| binary_sensor | Running | `current_state == "running"` |
| switch | Power *(new)* | `on` → `start` signal, `off` → `stop` signal; reported on when running/starting |
| button | Start / Stop / Restart / Kill | corresponding power signals |
| sensor | Status | `current_state` |
| sensor | CPU | `cpu_absolute` (%) |
| sensor | Memory | `memory_bytes` (limit as attribute) |
| sensor | Disk | `disk_bytes` (limit as attribute) |
| sensor | Network in | `network_rx_bytes` |
| sensor | Network out | `network_tx_bytes` |
| sensor | Uptime | `uptime` |

**Out of scope (YAGNI for now):** console command service, file/backup/database
management, schedules, websocket console streaming, player-count queries. These
can be added later; the design leaves room but does not build them.

## Architecture

### Project layout

A standalone git repo, HACS-ready from day one:

```
ha-pelican/
├── custom_components/pelican/
│   ├── __init__.py          # setup/unload, platform forwarding
│   ├── api.py               # native async Pelican client + exceptions + PelicanData
│   ├── coordinator.py       # DataUpdateCoordinator (60s)
│   ├── entity.py            # base entity + device_info
│   ├── binary_sensor.py
│   ├── sensor.py
│   ├── button.py
│   ├── switch.py            # new vs. original
│   ├── config_flow.py       # user + reauth steps
│   ├── const.py
│   ├── manifest.json        # domain=pelican, version, iot_class=local_polling
│   ├── strings.json
│   └── icons.json
├── tests/                   # mocked unit tests using captured fixtures
├── hacs.json
├── README.md
└── docs/superpowers/specs/
```

Deployment: copy or symlink `custom_components/pelican` into the HA config
directory; later install via HACS as a custom repository.

### API client (`api.py`)

Native async client built on Home Assistant's shared aiohttp session
(`homeassistant.helpers.aiohttp_client.async_get_clientsession`). Chosen over
reusing `pydactyl` because pydactyl is synchronous (needs executor wrapping) and
Pterodactyl-branded; a ~100-line native client is fully async, dependency-free,
and the right base for a Pelican-branded integration to share.

Methods (server addressed by `identifier`):

- `async_get_servers()` → list of server attribute dicts (from `GET /api/client`);
  already carries each server's static `attributes` (name, uuid, identifier, limits)
- `async_get_utilization(identifier)` → `current_state` + `resources` block
- `async_send_power(identifier, signal)` → `POST .../power` with `{"signal": ...}`

Headers on every request: `Authorization: Bearer <key>`, `Accept: application/json`,
`Content-Type: application/json`.

Exceptions:

- `PelicanAuthError` — HTTP 401 (→ reauth)
- `PelicanConnectionError` — network/timeout/non-401 HTTP failures (→ retry)

### Data model

`PelicanData` dataclass per server, populated by combining the server-details and
utilization responses:

```
name, uuid, identifier, state,
cpu, cpu_limit,
memory, memory_limit,
disk, disk_limit,
network_rx, network_tx,
uptime
```

### Coordinator

A single `DataUpdateCoordinator[dict[str, PelicanData]]` keyed by server
`identifier`, polling every **60 seconds** (matches the original). Each cycle
fetches the server list once (which already carries every server's static
attributes and limits), then fetches `/resources` per server for live state and
usage — no separate per-server detail call needed. `401` → `ConfigEntryAuthFailed`
(triggers HA's reauth flow); other failures → `UpdateFailed`.

### Config flow & auth

- **User step:** collect base URL + client API key; validate by listing servers.
  Map `PelicanAuthError` → `invalid_auth`, `PelicanConnectionError` →
  `cannot_connect`, anything else → `unknown`.
- **Reauth step:** re-prompt for the API key only; URL is retained.
- **Uniqueness:** use the normalized panel URL as the entry `unique_id`
  (`async_set_unique_id` + `_abort_if_unique_id_configured`) — one entry per
  panel. (An account-derived id was considered but dropped as unnecessary.)

### Manifest / distribution

- `domain: pelican`, `name: Pelican Panel`
- `version` present (required for custom components), start at `0.1.0`
- `iot_class: local_polling`, `config_flow: true`
- `requirements: []` (aiohttp is provided by HA)
- `codeowners`, `documentation`, `issue_tracker` set for the public repo
- `hacs.json` so it is installable as a HACS custom repository
- Entity icons via `icons.json` (mirrors the original)

## Verification plan

Leverages the live Pelican instance the user can provide an API key for:

1. **Capture real responses** ✅ *done 2026-06-23* — probed the live panel
   read-only and confirmed auth (`200`), the exact field names, and that both
   `identifier` and `uuid` resolve. Raw capture retained to seed test fixtures.
2. **Mocked unit tests** (polish, included now) using those fixtures: API client
   parsing, coordinator update, config-flow happy path + `invalid_auth` /
   `cannot_connect`.
3. **End-to-end** in the user's HA: install the component, confirm entities
   populate, and confirm the power switch starts/stops a throwaway/test server.

## Verification against live panel (2026-06-23)

Probed a live Pelican instance (`panel.example.com`, read-only) and confirmed
the design end-to-end:

- **Auth works** — `Authorization: Bearer <client key>` → `HTTP 200`.
- **Routing resolved** — both the full `uuid` *and* the short `identifier` return
  `200` for `/servers/{id}` and `/servers/{id}/resources`. We route by
  `identifier` (also the entity unique_id), as the original does.
- **JSON envelope identical to Pterodactyl** — `object` / `data` / `attributes`
  with a `resources` block.
- **Data model confirmed** — `attributes.limits` = `memory, swap, disk, io, cpu,
  ...`; resources = `attributes.{current_state, is_suspended, resources}` where
  `resources` = `{memory_bytes, cpu_absolute, disk_bytes, network_rx_bytes,
  network_tx_bytes, uptime}` — exactly what `PelicanData` expects.

## Remaining risks

- **Power signal** not exercised yet (would actually start/stop a server). Standard
  `POST /servers/{id}/power` with `{"signal": ...}`; verify on the offline
  `Example` server during end-to-end testing.
- **Pelican API versioning** — current client API is stable; Pelican versions
  future changes separately. No action needed now.

## Decisions log

- **API client:** native async (approach A), not pydactyl reuse.
- **Scope:** parity + power switch; no console/files/backups for now.
- **Distribution:** custom component first; HACS-ready repo; publish later.
- **Polish included now:** mocked unit-test fixtures. URL-based `unique_id`
  (account-derived id dropped as YAGNI).
- **Project location:** `~/projects/ha-pelican`.
