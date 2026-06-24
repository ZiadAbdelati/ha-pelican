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

### HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ZiadAbdelati&repository=ha-pelican&category=integration)

Click the button above — it opens HACS on your Home Assistant with this
repository pre-filled. Then **Download**, and **restart Home Assistant**.

<details>
<summary>Manual HACS steps (if the button doesn't work)</summary>

1. HACS → ⋮ → **Custom repositories**.
2. Add `https://github.com/ZiadAbdelati/ha-pelican`, category **Integration**.
3. Download **Pelican Panel**, then restart Home Assistant.
</details>

### Manual

Copy `custom_components/pelican` into your Home Assistant `config/custom_components/`
directory and restart.

## Configuration

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=pelican)

Click the button above, or go to **Settings → Devices & Services → Add
Integration → Pelican Panel**. Enter your panel URL (e.g.
`https://panel.example.com`) and the client API key.

> The "set up an integration" button works once the integration is installed and
> Home Assistant has restarted.

## Disclaimer

Not affiliated with the Pelican project. Provided as-is.
