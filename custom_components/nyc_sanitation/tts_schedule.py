"""Daily TTS reminder the day before DSNY collection days."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import DEFAULT_TTS_OPTIONS, DOMAIN
from .coordinator import DSNYCoordinator
from .parse import collection_types_tomorrow
from .tts_helper import async_send_tts

_LOGGER = logging.getLogger(__name__)


def merge_tts_options(entry: ConfigEntry) -> dict[str, Any]:
    """Return config entry options with defaults filled in."""
    merged = dict(DEFAULT_TTS_OPTIONS)
    merged.update(entry.options or {})
    return merged


def _format_announcement(types: list[str]) -> str:
    if not types:
        return ""
    if len(types) == 1:
        return f"Tomorrow is sanitation day: {types[0]}."
    if len(types) == 2:
        return f"Tomorrow is sanitation day: {types[0]} and {types[1]}."
    *rest, last = types
    return f"Tomorrow is sanitation day: {', '.join(rest)}, and {last}."


def async_cancel_tts_schedule(hass: HomeAssistant) -> None:
    """Unsubscribe the daily time listener, if any."""
    unsub = hass.data.get(DOMAIN, {}).pop("tts_time_unsub", None)
    if unsub is not None:
        unsub()


async def async_maybe_announce(hass: HomeAssistant) -> None:
    """If enabled and tomorrow has collections, speak once per local calendar day."""
    entry_id = hass.data.get(DOMAIN, {}).get("config_entry_id")
    if not entry_id:
        return
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None:
        return

    opts = merge_tts_options(entry)
    if not opts.get("tts_enabled"):
        return

    media_player = (opts.get("media_player_entity_id") or "").strip()
    if not media_player:
        return

    coordinator: DSNYCoordinator | None = hass.data.get(DOMAIN, {}).get("coordinator")
    if coordinator is None or not coordinator.data or not coordinator.data.get(
        "nyc_valid"
    ):
        return

    payload = coordinator.data.get("payload")
    if not isinstance(payload, dict):
        return

    now = dt_util.now()
    local_now = dt_util.as_local(now)
    today = local_now.date()

    last = hass.data.get(DOMAIN, {}).get("tts_last_announce_date")
    if last == today:
        return

    types = collection_types_tomorrow(payload, local_now)
    if not types:
        return

    message = _format_announcement(types)
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
            message,
            volume=vol_f,
            tts_entity=tts_entity,
            blocking=False,
        )
    except Exception:
        return

    hass.data.setdefault(DOMAIN, {})["tts_last_announce_date"] = today


async def async_setup_tts_schedule(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Register or refresh the daily announcement time listener."""
    async_cancel_tts_schedule(hass)

    opts = merge_tts_options(entry)
    if not opts.get("tts_enabled"):
        return

    hour = int(opts.get("announce_hour", 19))
    minute = int(opts.get("announce_minute", 0))

    @callback
    def _on_time(_now: Any) -> None:
        hass.async_create_task(async_maybe_announce(hass))

    unsub = async_track_time_change(hass, _on_time, hour=hour, minute=minute, second=0)
    hass.data.setdefault(DOMAIN, {})["tts_time_unsub"] = unsub
    _LOGGER.debug("TTS schedule: daily at %02d:%02d", hour, minute)
