"""Reverse geocode Home Assistant home coordinates via Nominatim."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, NOMINATIM_REVERSE_URL

_LOGGER = logging.getLogger(__name__)

NOMINATIM_HEADERS = {
    "User-Agent": f"{DOMAIN}/1.0 (Home Assistant integration; https://www.home-assistant.io/)",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}


def _display_name_from_address(addr: dict[str, Any]) -> str | None:
    """Build a single-line US-style address when structured fields exist."""
    if not addr:
        return None
    house = addr.get("house_number")
    road = addr.get("road")
    city = addr.get("city") or addr.get("town") or addr.get("village")
    state = addr.get("state")
    postcode = addr.get("postcode")
    country = addr.get("country")
    parts: list[str] = []
    line1 = " ".join(p for p in (house, road) if p)
    if line1:
        parts.append(line1)
    if city:
        parts.append(city)
    region = ", ".join(p for p in (state, postcode) if p)
    if region:
        parts.append(region)
    if country:
        parts.append(country)
    return ", ".join(parts) if len(parts) >= 2 else None


async def async_reverse_geocode(hass: HomeAssistant) -> str | None:
    """Return a display address for the configured home latitude/longitude."""
    lat = hass.config.latitude
    lon = hass.config.longitude
    if lat is None or lon is None:
        _LOGGER.warning("Home latitude/longitude not configured")
        return None

    session = async_get_clientsession(hass)
    params = {
        "lat": str(lat),
        "lon": str(lon),
        "format": "json",
        "addressdetails": "1",
    }
    try:
        async with session.get(
            NOMINATIM_REVERSE_URL,
            params=params,
            headers=NOMINATIM_HEADERS,
            timeout=30,
        ) as resp:
            if resp.status != 200:
                _LOGGER.error("Nominatim HTTP %s", resp.status)
                return None
            data = await resp.json()
    except TimeoutError:
        _LOGGER.exception("Nominatim request timed out")
        return None
    except Exception:
        _LOGGER.exception("Nominatim request failed")
        return None

    addr = data.get("address") or {}
    structured = _display_name_from_address(addr)
    if structured:
        return structured
    display = data.get("display_name")
    if isinstance(display, str) and display.strip():
        return display.strip()
    return None
