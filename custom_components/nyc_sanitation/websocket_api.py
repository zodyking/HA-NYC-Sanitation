"""WebSocket API for the sanitation sidebar panel."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, WS_TYPE_GET_COLLECTION
from .coordinator import DSNYCoordinator


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Register WebSocket commands."""
    websocket_api.async_register_command(hass, websocket_get_collection_data)


@websocket_api.websocket_command({vol.Required("type"): WS_TYPE_GET_COLLECTION})
@websocket_api.async_response
async def websocket_get_collection_data(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return collection schedule snapshot for the panel."""
    coordinator: DSNYCoordinator | None = hass.data.get(DOMAIN, {}).get("coordinator")
    if coordinator is None:
        connection.send_error(msg["id"], "not_ready", "NYC Sanitation is not loaded")
        return

    data = coordinator.data
    if not data:
        connection.send_result(
            msg["id"],
            {
                "nyc_valid": False,
                "error": "No data yet",
                "formatted_address": None,
                "geocoded_address": None,
                "weekly": {},
                "routing": {},
                "community_board": None,
                "last_update_success": coordinator.last_update_success,
            },
        )
        return

    weekly = data.get("weekly") or {}
    serializable_weekly = {
        day: list(types) if isinstance(types, list) else []
        for day, types in weekly.items()
    }

    connection.send_result(
        msg["id"],
        {
            "nyc_valid": data.get("nyc_valid", False),
            "error": data.get("error"),
            "formatted_address": data.get("formatted_address"),
            "geocoded_address": data.get("geocoded_address"),
            "weekly": serializable_weekly,
            "routing": data.get("routing") or {},
            "community_board": data.get("community_board"),
            "last_update_success": coordinator.last_update_success,
        },
    )
