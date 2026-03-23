# NYC Sanitation (Home Assistant)

Custom integration for **NYC Department of Sanitation (DSNY)** collection schedules: a **sidebar panel** (weekly view + routing times), reverse geocoding from your home coordinates, **one binary sensor** for pickups tomorrow, and **two sensors** for the next two pickup dates (types in attributes).

**Current release:** `1.3.3` — setup via **Settings → Devices & services** (config flow).  
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
| **Sidebar: Sanitation** | Seven-day fluid row + enforcement routing (NYC addresses only; otherwise a short “NYC only” message). |
| **Binary: Pickup scheduled tomorrow** | `on` when **any** DSNY collection is scheduled for **tomorrow** (local calendar). Attribute **`collection_types`** lists them; also includes today/tomorrow summaries and address metadata. |
| **Sensor: Pickup date 1** | State **`YYYY-MM-DD`** for the **first** upcoming pickup day starting from **today** (inclusive). Attributes **`collection_types`** (list) and **`weekday`**. Shared address / routing / today+tomorrow type hints. |
| **Sensor: Pickup date 2** | State **`YYYY-MM-DD`** for the **second** upcoming pickup day, or **`none`** if none found within 21 days. Same attributes when a date exists. |

**Upgrade note (v1.3.3):** Per-stream binaries and the old “Pickups scheduled today / tomorrow” text sensors are **removed**. You get **three** entities only. Delete orphaned entities under **Settings → Devices & services → NYC Sanitation** after upgrading.

## TTS reminders (day before pickup)

Administrators can open the **Sanitation** sidebar panel and use the **settings (cog)** to configure optional **text-to-speech** reminders.

- **When it runs:** Once per day at the **local time** you choose (Home Assistant time zone). If **tomorrow** has any DSNY collection type (trash, recycling, compost, or large items), HA speaks a short announcement on the **media player** you pick.
- **Requirements:** A working **`media_player`** and a **`tts.*`** entity (you can leave the TTS field empty to auto-select the first `tts` entity). Optional **volume** (0–1) is applied before speaking.
- **Test:** Use **Test announcement** in the same dialog to verify entity IDs without waiting for the schedule.

Backend polling of the DSNY API is at most **once per hour**; the panel refreshes its view about **once per minute** so the UI stays stable while other entities update.

## Troubleshooting

- Integration **not listed** after install: confirm the folder layout, restart HA, hard-refresh the browser.
- **Wrong schedule:** refine the map pin under **System → General** so Nominatim returns the correct block.

## Support

- [Issues](https://github.com/zodyking/HA-NYC-Sanitation/issues)

## Disclaimer

Not affiliated with NYC or DSNY. API data may not reflect holidays or last-minute service changes.
