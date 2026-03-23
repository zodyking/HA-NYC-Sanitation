# NYC Sanitation (Home Assistant)

Custom integration for NYC Department of Sanitation (DSNY) collection schedules: sidebar panel, reverse-geocoded home address, and a **Trash due** binary sensor.

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

## Requirements

- Home Assistant **2024.1** or newer
- Dependencies: `http`, `frontend`, `panel_custom` (declared in the integration manifest)

## Installation

### HACS

1. Open **HACS** → **Integrations** → menu **⋮** → **Custom repositories**.
2. Add this repository URL, category **Integration**.
3. Install **NYC Sanitation** and restart Home Assistant.

### Manual

Copy the `custom_components/nyc_sanitation` folder into your configuration directory:

`config/custom_components/nyc_sanitation/`

Restart Home Assistant.

## Configuration

Add an empty mapping for the domain in `configuration.yaml`:

```yaml
nyc_sanitation:
```

Set your **home location** (latitude / longitude) under **Settings → System → General**. The integration uses OpenStreetMap Nominatim to build an address string, then queries the public DSNY API.

## What you get

- Sidebar panel **Sanitation** — weekly schedule and enforcement routing times (NYC addresses only).
- `binary_sensor` **Trash due** — `on` when regular trash collection is scheduled for the current day in your HA time zone; attributes include collection types due that day, residential routing times, and formatted address.

## Disclaimer

This project is not affiliated with NYC or DSNY. Collection rules from the public API may not reflect holidays or last-minute changes.
