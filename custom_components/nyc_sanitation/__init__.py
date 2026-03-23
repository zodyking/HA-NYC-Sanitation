"""NYC Department of Sanitation — collection schedule and sidebar panel."""

from __future__ import annotations

import json
import logging
import os
import time

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_CORE_CONFIG_UPDATE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PANEL_ICON, PANEL_TITLE, PANEL_URL_PATH
from .coordinator import DSNYCoordinator
from .tts_schedule import async_cancel_tts_schedule, async_setup_tts_schedule

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """YAML stub — add the integration via the UI (Settings → Devices & services)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NYC Sanitation from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = DSNYCoordinator(hass)
    hass.data[DOMAIN]["coordinator"] = coordinator
    hass.data[DOMAIN]["config_entry_id"] = entry.entry_id

    await coordinator.async_config_entry_first_refresh()

    if not hass.data[DOMAIN].get("ws_registered"):
        from .websocket_api import async_setup as async_setup_websocket

        async_setup_websocket(hass)
        hass.data[DOMAIN]["ws_registered"] = True

    await _async_ensure_static_assets(hass)
    await _async_register_panel(hass)

    @callback
    def _core_config_changed(_event) -> None:
        hass.async_create_task(coordinator.async_request_refresh())

    entry.async_on_unload(
        hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, _core_config_changed)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_setup_tts_schedule(hass, entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    async_cancel_tts_schedule(hass)
    hass.data[DOMAIN].pop("config_entry_id", None)
    hass.data[DOMAIN].pop("tts_last_announce_date", None)

    try:
        frontend.async_remove_panel(hass, PANEL_URL_PATH)
    except KeyError:
        pass

    hass.data[DOMAIN].pop("coordinator", None)
    hass.data[DOMAIN]["panel_registered"] = False

    return True


async def _async_ensure_static_assets(hass: HomeAssistant) -> None:
    """Register panel JS path once per HA process (survives unload/re-add)."""
    if hass.data[DOMAIN].get("static_assets_registered"):
        return

    frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
    panel_url = f"/{DOMAIN}_panel"

    await hass.http.async_register_static_paths(
        [StaticPathConfig(panel_url, frontend_path, cache_headers=False)]
    )
    hass.data[DOMAIN]["static_assets_registered"] = True


async def _async_register_panel(hass: HomeAssistant) -> None:
    """Register sidebar panel (idempotent per loaded entry)."""
    if hass.data[DOMAIN].get("panel_registered"):
        return

    await _async_ensure_static_assets(hass)

    panel_url = f"/{DOMAIN}_panel"

    def _read_manifest_version() -> str:
        manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
        try:
            with open(manifest_path, encoding="utf-8") as f:
                return json.load(f).get("version", "1.0.0")
        except (OSError, json.JSONDecodeError, TypeError):
            return "1.0.0"

    version = await hass.async_add_executor_job(_read_manifest_version)
    load_id = str(int(time.time() * 1000))

    await panel_custom.async_register_panel(
        hass,
        webcomponent_name="nyc-sanitation-panel",
        frontend_url_path=PANEL_URL_PATH,
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        module_url=f"{panel_url}/sanitation-panel.js?v={version}&_={load_id}",
        embed_iframe=False,
        require_admin=False,
    )
    hass.data[DOMAIN]["panel_registered"] = True
    _LOGGER.debug("Registered NYC Sanitation sidebar panel")
