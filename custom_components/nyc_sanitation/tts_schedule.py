"""Repeating TTS reminders the day before DSNY collection days."""

from __future__ import annotations

import calendar
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import MATCH_ALL
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import DEFAULT_TTS_OPTIONS, DOMAIN
from .coordinator import DSNYCoordinator
from .parse import collection_types_tomorrow
from .tts_helper import async_send_tts
from .tts_messages import build_tts_message

_LOGGER = logging.getLogger(__name__)


def merge_tts_options(entry: ConfigEntry) -> dict[str, Any]:
    """Return config entry options with defaults filled in and legacy keys migrated."""
    merged: dict[str, Any] = dict(DEFAULT_TTS_OPTIONS)
    raw = entry.options or {}
    merged.update(raw)

    if raw and "tts_window_start_hour" not in raw:
        ah = int(raw.get("announce_hour", 19))
        am = int(raw.get("announce_minute", 0))
        merged["tts_window_start_hour"] = ah
        merged["tts_minute_offset"] = am
        merged["tts_interval_hours"] = 1
        if ah >= 23:
            merged["tts_window_start_hour"] = 23
            merged["tts_window_end_hour"] = 24
        else:
            merged["tts_window_end_hour"] = min(ah + 1, 24)

    return merged


def _in_active_window(hour: int, start: int, end: int) -> bool:
    """True if *hour* is in ``[start, end)`` (end may be 24)."""
    return start <= hour < end


def _hour_matches_interval(hour: int, start: int, interval: int) -> bool:
    return (hour - start) % interval == 0


def async_cancel_tts_schedule(hass: HomeAssistant) -> None:
    """Unsubscribe the time listener, if any."""
    unsub = hass.data.get(DOMAIN, {}).pop("tts_time_unsub", None)
    if unsub is not None:
        unsub()


async def async_maybe_announce(hass: HomeAssistant) -> None:
    """If enabled and schedule matches, speak when tomorrow has collections."""
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
    tts_entity = (opts.get("tts_entity_id") or "").strip()
    if not media_player or not tts_entity:
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
    h = local_now.hour
    start_h = int(opts.get("tts_window_start_hour", 12))
    end_h = int(opts.get("tts_window_end_hour", 20))
    interval = int(opts.get("tts_interval_hours", 1))
    interval = max(1, min(4, interval))

    if not _in_active_window(h, start_h, end_h):
        return
    if not _hour_matches_interval(h, start_h, interval):
        return

    types = collection_types_tomorrow(payload, local_now)
    if not types:
        return

    tomorrow_dt = local_now + timedelta(days=1)
    weekday_name = calendar.day_name[tomorrow_dt.weekday()]
    message = build_tts_message(opts, types, weekday_name)
    if not message:
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
    extra_opts = opts.get("tts_options")
    tts_options: dict[str, Any] | None
    if isinstance(extra_opts, dict):
        tts_options = extra_opts
    else:
        tts_options = None

    try:
        await async_send_tts(
            hass,
            media_player,
            message,
            language=language,
            volume=vol_f,
            tts_entity=tts_entity,
            cache=cache,
            options=tts_options,
            blocking=False,
        )
    except Exception:
        _LOGGER.exception("TTS announcement failed")


async def async_setup_tts_schedule(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Register the repeating reminder listener on the configured minute."""
    async_cancel_tts_schedule(hass)

    opts = merge_tts_options(entry)
    if not opts.get("tts_enabled"):
        return

    minute = int(opts.get("tts_minute_offset", 0))
    minute = max(0, min(59, minute))

    @callback
    def _on_time(_now: Any) -> None:
        hass.async_create_task(async_maybe_announce(hass))

    unsub = async_track_time_change(
        hass, _on_time, hour=MATCH_ALL, minute=minute, second=0
    )
    hass.data.setdefault(DOMAIN, {})["tts_time_unsub"] = unsub
    _LOGGER.debug("TTS schedule: each hour at :%02d (window + interval in callback)", minute)
