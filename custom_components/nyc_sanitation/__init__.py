"""NYC Department of Sanitation — collection schedule and sidebar panel."""

from __future__ import annotations

import json
import logging
import os
import time

from homeassistant.components import panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import EVENT_CORE_CONFIG_UPDATE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PANEL_ICON, PANEL_TITLE, PANEL_URL_PATH
from .coordinator import DSNYCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up NYC Sanitation from YAML."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = DSNYCoordinator(hass)
    hass.data[DOMAIN]["coordinator"] = coordinator

    from .websocket_api import async_setup as async_setup_websocket

    async_setup_websocket(hass)

    await coordinator.async_refresh()

    await async_load_platform(hass, "binary_sensor", DOMAIN, {}, config)

    await _async_register_panel(hass)

    @callback
    def _core_config_changed(_event) -> None:
        hass.async_create_task(coordinator.async_request_refresh())

    hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, _core_config_changed)

    return True


async def _async_register_panel(hass: HomeAssistant) -> None:
    """Register static assets and sidebar panel (once)."""
    if hass.data[DOMAIN].get("panel_registered"):
        return

    frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
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

    await hass.http.async_register_static_paths(
        [StaticPathConfig(panel_url, frontend_path, cache_headers=False)]
    )

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
