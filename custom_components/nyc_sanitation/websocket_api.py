"""WebSocket API for the sanitation sidebar panel."""

from __future__ import annotations

import calendar
import json
from datetime import timedelta
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
    WS_TYPE_PREVIEW_TTS_MESSAGE,
    WS_TYPE_SET_TTS_OPTIONS,
    WS_TYPE_TEST_TTS,
)
from .coordinator import DSNYCoordinator
from .parse import collection_types_tomorrow
from .tts_helper import async_send_tts
from .tts_messages import build_tts_message, scenario_collection_types
from .tts_schedule import async_setup_tts_schedule, merge_tts_options

_PREVIEW_SCENARIOS = (
    "trash",
    "recycling",
    "compost",
    "large_items",
    "mixed",
    "tomorrow_actual",
)
_DRAFT_TEMPLATE_KEYS = frozenset(
    {
        "tts_message_prefix",
        "tts_message_trash",
        "tts_message_recycling",
        "tts_message_compost",
        "tts_message_large_items",
        "tts_message_mixed",
    }
)


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Register WebSocket commands."""
    websocket_api.async_register_command(hass, websocket_get_collection_data)
    websocket_api.async_register_command(hass, websocket_get_tts_options)
    websocket_api.async_register_command(hass, websocket_set_tts_options)
    websocket_api.async_register_command(hass, websocket_test_tts)
    websocket_api.async_register_command(hass, websocket_preview_tts_message)


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


def _entity_summaries(hass: HomeAssistant, prefix: str) -> list[dict[str, str]]:
    rows: list[tuple[str, str]] = []
    for state in hass.states.async_all():
        eid = state.entity_id
        if not eid.startswith(prefix):
            continue
        name = state.attributes.get("friendly_name") or eid
        rows.append((eid, str(name)))
    rows.sort(key=lambda x: x[1].lower())
    return [{"entity_id": eid, "name": name} for eid, name in rows]


def _coerce_tts_options(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as err:
            raise vol.Invalid(f"Invalid JSON for tts_options: {err}") from err
        if not isinstance(parsed, dict):
            raise vol.Invalid("tts_options JSON must be an object")
        return parsed
    raise vol.Invalid("tts_options must be an object, JSON string, or null")


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
    """Return TTS options, entity lists, and a preview message (admin only)."""
    if not _require_admin(hass, connection, msg["id"]):
        return

    entry = _get_entry(hass)
    if entry is None:
        connection.send_error(msg["id"], "not_ready", "NYC Sanitation is not loaded")
        return

    opts = merge_tts_options(entry)
    coordinator: DSNYCoordinator | None = hass.data.get(DOMAIN, {}).get("coordinator")
    tomorrow_types: list[str] = []
    preview_message = ""
    if coordinator and coordinator.data and coordinator.data.get("nyc_valid"):
        payload = coordinator.data.get("payload")
        if isinstance(payload, dict):
            local_now = dt_util.as_local(dt_util.now())
            tomorrow_types = collection_types_tomorrow(payload, local_now)
            if tomorrow_types:
                tw = local_now + timedelta(days=1)
                wname = calendar.day_name[tw.weekday()]
                routing = coordinator.data.get("routing") or {}
                res_rt = routing.get("residential")
                residential = res_rt if isinstance(res_rt, str) else None
                preview_message = build_tts_message(
                    opts, tomorrow_types, wname, residential_routing=residential
                )

    connection.send_result(
        msg["id"],
        {
            "options": opts,
            "tomorrow_types": tomorrow_types,
            "preview_message": preview_message,
            "media_players": _entity_summaries(hass, "media_player."),
            "tts_entities": _entity_summaries(hass, "tts."),
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_PREVIEW_TTS_MESSAGE,
        vol.Required("scenario"): vol.All(str, vol.In(_PREVIEW_SCENARIOS)),
        vol.Optional("draft"): vol.Any(None, dict),
    }
)
@websocket_api.async_response
async def websocket_preview_tts_message(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return spoken text preview for a scenario using saved options + optional draft (admin only)."""
    if not _require_admin(hass, connection, msg["id"]):
        return

    entry = _get_entry(hass)
    if entry is None:
        connection.send_error(msg["id"], "not_ready", "NYC Sanitation is not loaded")
        return

    opts: dict[str, Any] = dict(merge_tts_options(entry))
    raw_draft = msg.get("draft")
    if isinstance(raw_draft, dict):
        for key, val in raw_draft.items():
            if key in _DRAFT_TEMPLATE_KEYS:
                opts[key] = str(val if val is not None else "").strip()

    coordinator: DSNYCoordinator | None = hass.data.get(DOMAIN, {}).get("coordinator")
    residential: str | None = None
    if coordinator and coordinator.data:
        rt = coordinator.data.get("routing") or {}
        res_rt = rt.get("residential")
        residential = res_rt if isinstance(res_rt, str) else None

    scenario: str = msg["scenario"]
    local_now = dt_util.as_local(dt_util.now())
    tw = local_now + timedelta(days=1)
    weekday_name = calendar.day_name[tw.weekday()]

    if scenario == "tomorrow_actual":
        if (
            coordinator is None
            or not coordinator.data
            or not coordinator.data.get("nyc_valid")
        ):
            connection.send_result(
                msg["id"],
                {
                    "preview_text": "",
                    "no_pickup_tomorrow": True,
                    "reason": "nyc_invalid",
                },
            )
            return
        payload = coordinator.data.get("payload")
        if not isinstance(payload, dict):
            connection.send_result(
                msg["id"],
                {"preview_text": "", "no_pickup_tomorrow": True, "reason": "no_payload"},
            )
            return
        types = collection_types_tomorrow(payload, local_now)
        if not types:
            connection.send_result(
                msg["id"],
                {"preview_text": "", "no_pickup_tomorrow": True},
            )
            return
    else:
        syn = scenario_collection_types(scenario)
        if syn is None:
            connection.send_error(msg["id"], "invalid_request", "Bad scenario")
            return
        types = syn

    preview_text = build_tts_message(
        opts, types, weekday_name, residential_routing=residential
    )
    connection.send_result(
        msg["id"],
        {"preview_text": preview_text, "no_pickup_tomorrow": False},
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_SET_TTS_OPTIONS,
        vol.Required("tts_enabled"): bool,
        vol.Required("tts_window_start_hour"): vol.All(int, vol.Range(min=0, max=23)),
        vol.Required("tts_window_end_hour"): vol.All(int, vol.Range(min=1, max=24)),
        vol.Required("tts_interval_hours"): vol.All(int, vol.In([1, 2, 3, 4])),
        vol.Required("tts_minute_offset"): vol.All(int, vol.Range(min=0, max=59)),
        vol.Required("media_player_entity_id"): str,
        vol.Required("tts_entity_id"): str,
        vol.Optional("volume", default=None): vol.Any(
            None, vol.All(vol.Coerce(float), vol.Range(min=0, max=1))
        ),
        vol.Required("tts_cache"): bool,
        vol.Optional("tts_language", default=""): str,
        vol.Optional("tts_options", default=None): vol.Any(None, dict, str),
        vol.Optional("tts_message_prefix", default=""): str,
        vol.Optional("tts_message_trash", default=""): str,
        vol.Optional("tts_message_recycling", default=""): str,
        vol.Optional("tts_message_compost", default=""): str,
        vol.Optional("tts_message_large_items", default=""): str,
        vol.Optional("tts_message_mixed", default=""): str,
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

    start_h = msg["tts_window_start_hour"]
    end_h = msg["tts_window_end_hour"]
    if start_h >= end_h:
        connection.send_error(
            msg["id"],
            "invalid_options",
            "Start time must be before end time (same calendar day).",
        )
        return

    try:
        coerced_opts = _coerce_tts_options(msg.get("tts_options"))
    except vol.Invalid as err:
        connection.send_error(msg["id"], "invalid_options", str(err))
        return

    media_player = msg["media_player_entity_id"].strip()
    tts_entity = msg["tts_entity_id"].strip()
    if msg["tts_enabled"]:
        if not media_player:
            connection.send_error(
                msg["id"],
                "invalid_options",
                "Media player entity is required when TTS reminders are enabled.",
            )
            return
        if not tts_entity:
            connection.send_error(
                msg["id"],
                "invalid_options",
                "TTS engine entity is required when TTS reminders are enabled.",
            )
            return

    new_opts = merge_tts_options(entry)
    new_opts.update(
        {
            "tts_enabled": msg["tts_enabled"],
            "tts_window_start_hour": start_h,
            "tts_window_end_hour": end_h,
            "tts_interval_hours": msg["tts_interval_hours"],
            "tts_minute_offset": msg["tts_minute_offset"],
            "media_player_entity_id": media_player,
            "tts_entity_id": tts_entity,
            "volume": msg.get("volume"),
            "tts_cache": msg["tts_cache"],
            "tts_language": (msg.get("tts_language") or "").strip(),
            "tts_options": coerced_opts,
            "tts_message_prefix": msg.get("tts_message_prefix") or "",
            "tts_message_trash": msg.get("tts_message_trash") or "",
            "tts_message_recycling": msg.get("tts_message_recycling") or "",
            "tts_message_compost": msg.get("tts_message_compost") or "",
            "tts_message_large_items": msg.get("tts_message_large_items") or "",
            "tts_message_mixed": msg.get("tts_message_mixed") or "",
        }
    )
    hass.config_entries.async_update_entry(entry, options=new_opts)
    await async_setup_tts_schedule(hass, entry)
    connection.send_result(
        msg["id"], {"success": True, "options": merge_tts_options(entry)}
    )


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
    tts_entity = (opts.get("tts_entity_id") or "").strip()
    if not media_player:
        connection.send_error(
            msg["id"], "invalid_options", "Set a media player entity in TTS settings."
        )
        return
    if not tts_entity:
        connection.send_error(
            msg["id"], "invalid_options", "Set a TTS engine entity in TTS settings."
        )
        return

    volume = opts.get("volume")
    vol_f: float | None
    if volume is None or volume == "":
        vol_f = None
    else:
        try:
            vol_f = float(volume)
        except (TypeError, ValueError):
            vol_f = None

    lang_raw = opts.get("tts_language")
    language = (str(lang_raw).strip() if lang_raw is not None else "") or None
    cache = bool(opts.get("tts_cache", True))
    extra = opts.get("tts_options")
    tts_options = extra if isinstance(extra, dict) else None

    try:
        await async_send_tts(
            hass,
            media_player,
            "NYC Sanitation test: text to speech is working.",
            language=language,
            volume=vol_f,
            tts_entity=tts_entity,
            cache=cache,
            options=tts_options,
            blocking=False,
        )
    except Exception as err:
        connection.send_error(msg["id"], "tts_failed", str(err))
        return

    connection.send_result(msg["id"], {"success": True})
