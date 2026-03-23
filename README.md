# NYC Sanitation (Home Assistant)

Custom integration for **NYC Department of Sanitation (DSNY)** collection schedules: a **sidebar panel** (weekly view + routing times), reverse geocoding from your home coordinates, and a **Trash due** binary sensor.

**Current release:** `1.1.0` — setup via **Settings → Devices & services** (config flow).  
Repository: [github.com/zodyking/HA-NYC-Sanitation](https://github.com/zodyking/HA-NYC-Sanitation)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

## Requirements

- Home Assistant **2024.1** or newer
- Dependencies (declared in the manifest): `http`, `frontend`, `panel_custom`

## Installation

### HACS (recommended)

1. **HACS** → **Integrations** → **⋮** → **Custom repositories**.
2. Add `https://github.com/zodyking/HA-NYC-Sanitation`, category **Integration**.
3. Open **HACS** → **Integrations** → find **NYC Sanitation** → **Download**.
4. **Restart Home Assistant.**

### Manual

Copy [`custom_components/nyc_sanitation`](custom_components/nyc_sanitation) to:

`config/custom_components/nyc_sanitation/`

Then **restart** Home Assistant.

## Configuration (UI)

1. **Settings** → **Devices & services** → **Add integration**.
2. Search for **NYC Sanitation** or **NYC Department of Sanitation** and submit the one-step flow.
3. Under **Settings** → **System** → **General**, set **home latitude/longitude** (used with OpenStreetMap Nominatim, then the public DSNY API).

**One instance only.** To change anything, remove the integration and add it again.

### Upgrading from YAML-only (v1.0.x)

Remove `nyc_sanitation:` from `configuration.yaml`, restart if needed, then add the integration from **Devices & services** as above.

## What you get

| Piece | Description |
|--------|-------------|
| **Sidebar: Sanitation** | Weekly schedule chips + enforcement routing (NYC addresses only; otherwise a short “NYC only” message). |
| **Binary sensor: Trash due** | `on` when regular trash collection is scheduled for **today** in your HA time zone. Attributes: `collection_types_today`, `residential_routing_times`, `formatted_address`, `community_board`. |

## Troubleshooting

- Integration **not listed** after install: confirm the folder layout, restart HA, hard-refresh the browser.
- **Wrong schedule:** refine the map pin under **System → General** so Nominatim returns the correct block.

## Support

- [Issues](https://github.com/zodyking/HA-NYC-Sanitation/issues)

## Disclaimer

Not affiliated with NYC or DSNY. API data may not reflect holidays or last-minute service changes.
