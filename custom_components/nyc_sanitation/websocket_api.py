"""WebSocket API for the sanitation sidebar panel."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    WS_TYPE_GET_COLLECTION,
    WS_TYPE_GET_TTS_OPTIONS,
    WS_TYPE_SET_TTS_OPTIONS,
    WS_TYPE_TEST_TTS,
)
from .coordinator import DSNYCoordinator
from .parse import collection_types_tomorrow
from .tts_helper import async_send_tts
from .tts_schedule import async_setup_tts_schedule, merge_tts_options


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Register WebSocket commands."""
    websocket_api.async_register_command(hass, websocket_get_collection_data)
    websocket_api.async_register_command(hass, websocket_get_tts_options)
    websocket_api.async_register_command(hass, websocket_set_tts_options)
    websocket_api.async_register_command(hass, websocket_test_tts)


def _require_admin(
    _hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg_id: int,
) -> bool:
    """True if the websocket connection has an admin user (HA ActiveConnection.user)."""
    user = connection.user
    if user is None:
        connection.send_error(msg_id, "unauthorized", "Not authenticated")
        return False
    if not user.is_admin:
        connection.send_error(
            msg_id, "unauthorized", "Administrator access required"
        )
        return False
    return True


def _get_entry(hass: HomeAssistant) -> ConfigEntry | None:
    entry_id = hass.data.get(DOMAIN, {}).get("config_entry_id")
    if not entry_id:
        return None
    return hass.config_entries.async_get_entry(entry_id)


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


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_GET_TTS_OPTIONS,
    }
)
@websocket_api.async_response
async def websocket_get_tts_options(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return TTS options and a preview of tomorrow's collection types (admin only)."""
    if not _require_admin(hass, connection, msg["id"]):
        return

    entry = _get_entry(hass)
    if entry is None:
        connection.send_error(msg["id"], "not_ready", "NYC Sanitation is not loaded")
        return

    opts = merge_tts_options(entry)
    coordinator: DSNYCoordinator | None = hass.data.get(DOMAIN, {}).get("coordinator")
    tomorrow_types: list[str] = []
    if coordinator and coordinator.data and coordinator.data.get("nyc_valid"):
        payload = coordinator.data.get("payload")
        if isinstance(payload, dict):
            tomorrow_types = collection_types_tomorrow(
                payload, dt_util.as_local(dt_util.now())
            )

    connection.send_result(
        msg["id"],
        {
            "options": opts,
            "tomorrow_types": tomorrow_types,
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_SET_TTS_OPTIONS,
        vol.Required("tts_enabled"): bool,
        vol.Required("announce_hour"): vol.All(int, vol.Range(min=0, max=23)),
        vol.Required("announce_minute"): vol.All(int, vol.Range(min=0, max=59)),
        vol.Required("media_player_entity_id"): str,
        vol.Optional("tts_entity_id", default=""): str,
        vol.Optional("volume", default=None): vol.Any(
            None, vol.All(vol.Coerce(float), vol.Range(min=0, max=1))
        ),
    }
)
@websocket_api.async_response
async def websocket_set_tts_options(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Persist TTS options on the config entry (admin only)."""
    if not _require_admin(hass, connection, msg["id"]):
        return

    entry = _get_entry(hass)
    if entry is None:
        connection.send_error(msg["id"], "not_ready", "NYC Sanitation is not loaded")
        return

    media_player = msg["media_player_entity_id"].strip()
    if msg["tts_enabled"] and not media_player:
        connection.send_error(
            msg["id"],
            "invalid_options",
            "Media player entity is required when TTS reminders are enabled.",
        )
        return

    new_opts = merge_tts_options(entry)
    new_opts.update(
        {
            "tts_enabled": msg["tts_enabled"],
            "announce_hour": msg["announce_hour"],
            "announce_minute": msg["announce_minute"],
            "media_player_entity_id": media_player,
            "tts_entity_id": (msg.get("tts_entity_id") or "").strip(),
            "volume": msg.get("volume"),
        }
    )
    hass.config_entries.async_update_entry(entry, options=new_opts)
    await async_setup_tts_schedule(hass, entry)
    connection.send_result(msg["id"], {"success": True, "options": merge_tts_options(entry)})


@websocket_api.websocket_command(
    {vol.Required("type"): WS_TYPE_TEST_TTS},
)
@websocket_api.async_response
async def websocket_test_tts(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Speak a short test phrase using current TTS options (admin only)."""
    if not _require_admin(hass, connection, msg["id"]):
        return

    entry = _get_entry(hass)
    if entry is None:
        connection.send_error(msg["id"], "not_ready", "NYC Sanitation is not loaded")
        return

    opts = merge_tts_options(entry)
    media_player = (opts.get("media_player_entity_id") or "").strip()
    if not media_player:
        connection.send_error(
            msg["id"], "invalid_options", "Set a media player entity in TTS settings."
        )
        return

    tts_entity = (opts.get("tts_entity_id") or "").strip() or None
    volume = opts.get("volume")
    vol_f: float | None
    if volume is None or volume == "":
        vol_f = None
    else:
        try:
            vol_f = float(volume)
        except (TypeError, ValueError):
            vol_f = None

    try:
        await async_send_tts(
            hass,
            media_player,
            "NYC Sanitation test: text to speech is working.",
            volume=vol_f,
            tts_entity=tts_entity,
            blocking=False,
        )
    except Exception as err:
        connection.send_error(msg["id"], "tts_failed", str(err))
        return

    connection.send_result(msg["id"], {"success": True})
