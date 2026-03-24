# NYC Sanitation (Home Assistant)

Custom integration for **NYC Department of Sanitation (DSNY)** collection schedules: a **sidebar panel** (weekly view + routing times), reverse geocoding from your home coordinates, **one binary sensor** for pickups tomorrow, and **two sensors** for the next two pickup dates (types in attributes).

**Current release:** `1.4.1` — setup via **Settings → Devices & services** (config flow).  
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

Administrators open the **Sanitation** sidebar panel and use the **settings (cog)** to open the full-page **TTS settings** view.

### When it runs

- Uses your Home Assistant **time zone**.
- On each **minute offset** you choose (e.g. `:32` every hour), the integration checks whether the current **local hour** is inside the **active window**.
- **Window:** **Start** and **End** use 12-hour times. **End** is the first clock time when reminders **stop** (half-open interval): active hours satisfy `start_hour ≤ H < end_hour`. Example: **12 PM → 8 PM** means hours **12–19** only (nothing in the 8:00–9:00 PM hour). If **End** is **12:00 AM**, it is stored as “through end of day” (all hours `0–23` for that calendar day).
- **Repeat every:** eligible hours are **start**, **start + N hours**, **start + 2N…** while still inside the window (N = 1, 2, 3, or 4).
- If **tomorrow** has any DSNY collection type, HA builds the spoken message from your **prefix** and templates, then:
  1. Waits until the **media player** state is **`idle`** (with a timeout),
  2. Optionally calls **`media_player.volume_set`** (if “Apply volume” is enabled),
  3. Waits for **`idle`** again,
  4. Calls **`tts.speak`** with your **TTS engine** as **target**, **`media_player_entity_id`**, **`message`**, **`cache`**, and optional **language** / **options** (same shape as the Developer Tools **Speak** action).

Each matching tick can announce again (no “once per calendar day” cap), so choose a window and interval that match how often you want reminders.

### Message templates and placeholders

- **Prefix** (default: `Message from New York City Sanitation,`) is prepended to the **body** template.
- **Body** is chosen from the **single-type** template matching tomorrow’s only type, or from **Multiple types** when there is more than one.
- **Schedule / pickup:** **`{weekday}`**, **`{types}`**, **`{types_sentence}`**, **`{type}`** (single-type shortcut; when multiple, same as `{types}`).
- **Curb + routing:** **`{curb_reminder}`** — set-out guidance using **residential** enforcement times from DSNY. **`{routing_first_start}`** is a TTS-friendly time (e.g. `8 A M`). **`{routing_first_start_display}`** is a short display form (e.g. `8:00 AM`). **`{residential_routing_raw}`** is the full API string for advanced templates.
  - **Heuristic:** the integration parses `ResidentialRoutingTime` (e.g. `Daily: 8:00 AM - 9:00 AM and 6:00 PM - 7:00 PM`) and uses the **earliest morning (AM) window start** as “first route tomorrow.” If there is no AM window, it uses the **first** start time in the string. If no times parse, the reminder avoids inventing a time and points you to the panel.
- **What is / isn’t tomorrow:** **`{type_status}`** — e.g. “Scheduled for pickup: Trash and Recycling. Not scheduled: Compost and Large items.” (covers all four streams: Trash, Recycling, Compost, Large items). **`{types_scheduled}`** / **`{types_not_scheduled}`** — comma lists in that canonical order. **`{has_large_items}`** — `yes` or `no`. **`{large_items_note}`** — extra sentence when **large items are** scheduled (bulk rules); when bulk is **not** scheduled, absences are already in **`{type_status}`**.

### Text preview (WebSocket, admin)

The TTS settings panel can show **spoken text** without saving or calling **`tts.speak`**. It uses the WebSocket command **`nyc_sanitation/preview_tts_message`** (same admin gate as other panel commands).

- **`scenario`** (required): **`trash`**, **`recycling`**, **`compost`**, **`large_items`**, **`mixed`**, or **`tomorrow_actual`**. The first five use **fixed** tomorrow-type lists so placeholders like **`{type_status}`** look realistic (e.g. **`mixed`** → Trash, Recycling, Compost). **`tomorrow_actual`** uses **live** tomorrow types from the DSNY payload (same idea as the global “tomorrow” preview). If there is no pickup tomorrow, the result has empty **`preview_text`** and **`no_pickup_tomorrow`: true** (and sometimes a **`reason`** when the address is not NYC-valid).
- **`draft`** (optional object): any of **`tts_message_prefix`**, **`tts_message_trash`**, **`tts_message_recycling`**, **`tts_message_compost`**, **`tts_message_large_items`**, **`tts_message_mixed`** — values are merged over **saved** options for the preview only.

The response includes **`preview_text`** and **`no_pickup_tomorrow`**.

### Default spoken examples (if you keep default templates)

Exact lines depend on routing text, weekday, and tomorrow’s types. Illustrative shape:

| Situation | Example shape |
|-----------|----------------|
| Trash only tomorrow (no bulk) | Prefix + curb reminder referencing first **A M** route time + “Tomorrow, Wednesday, is Trash collection day.” + **type_status** listing Recycling, Compost, Large items as not scheduled. |
| Trash + Recycling, no bulk | Same curb line + “Tomorrow, Wednesday.” + **type_status** (scheduled: Trash and Recycling; not scheduled: Compost and Large items). |
| Includes **Large items** | **type_status** includes Large items in “Scheduled”; **`{large_items_note}`** adds bulk set-out wording in single-type templates. |

(Word order and times come from your DSNY response and templates.)

### Requirements

- **Media player** and **TTS engine** (`tts.*`) are **required** when reminders are enabled (pick from the dropdowns populated from your HA state).
- **Test announcement** uses the same idle → optional volume → idle → **`tts.speak`** path with a fixed test phrase.

Backend polling of the DSNY API is at most **once per hour**; the panel refreshes its main view about **once per minute**.

## Troubleshooting

- Integration **not listed** after install: confirm the folder layout, restart HA, hard-refresh the browser.
- **Wrong schedule:** refine the map pin under **System → General** so Nominatim returns the correct block.

## Support

- [Issues](https://github.com/zodyking/HA-NYC-Sanitation/issues)

## Disclaimer

Not affiliated with NYC or DSNY. API data may not reflect holidays or last-minute service changes.
