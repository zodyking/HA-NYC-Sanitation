"""TTS helpers (tts.speak + media player), aligned with common HA patterns."""

from __future__ import annotations

import logging
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .const import DEFAULT_TTS_LANGUAGE

_LOGGER = logging.getLogger(__name__)


async def async_send_tts(
    hass: HomeAssistant,
    media_player: str,
    message: str,
    language: str | None = None,
    volume: float | None = None,
    tts_entity: str | None = None,
    blocking: bool = False,
) -> None:
    """Send TTS to a media player via the ``tts.speak`` service."""
    if not message or not message.strip():
        _LOGGER.warning("Empty TTS message, skipping")
        return

    if not media_player:
        _LOGGER.warning("No media player specified for TTS")
        return

    if hass.states.get(media_player) is None:
        _LOGGER.error("Media player %s not found", media_player)
        return

    if volume is not None:
        await async_set_volume(hass, media_player, volume)

    if not tts_entity:
        tts_entity = await _async_find_tts_entity(hass, language)

    if not tts_entity:
        _LOGGER.error("No TTS entity found")
        return

    try:
        await hass.services.async_call(
            "tts",
            "speak",
            {
                "media_player_entity_id": media_player,
                "message": message.strip(),
            },
            target={"entity_id": tts_entity},
            blocking=blocking,
        )
        _LOGGER.debug("TTS sent to %s via %s", media_player, tts_entity)
    except Exception as err:
        _LOGGER.error("Failed to send TTS: %s", err)
        raise


async def _async_find_tts_entity(
    hass: HomeAssistant, language: str | None = None
) -> str | None:
    """Pick a ``tts.*`` entity, preferring one whose id mentions *language*."""
    lang = (language or DEFAULT_TTS_LANGUAGE).lower()
    tts_entities: list[str] = []
    for state in hass.states.async_all():
        eid = state.entity_id
        if eid.startswith("tts."):
            tts_entities.append(eid)
    if not tts_entities:
        _LOGGER.warning("No TTS entities found in Home Assistant")
        return None
    for entity_id in tts_entities:
        if lang in entity_id.lower():
            return entity_id
    return tts_entities[0]


async def async_set_volume(hass: HomeAssistant, media_player: str, volume: float) -> None:
    """Clamp and set media player volume level (0..1)."""
    if not media_player:
        return
    volume = max(0.0, min(1.0, float(volume)))
    try:
        await hass.services.async_call(
            "media_player",
            "volume_set",
            {ATTR_ENTITY_ID: media_player, "volume_level": volume},
            blocking=False,
        )
    except Exception as err:
        _LOGGER.error("Failed to set volume on %s: %s", media_player, err)
        raise
