"""HTTP client for DSNY public collection API."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urlencode

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DSNY_BASE_URL, ID_FOR_SERVICE

_LOGGER = logging.getLogger(__name__)

DSNY_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.nyc.gov",
    "Referer": "https://www.nyc.gov/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
    ),
}


async def async_fetch_collection(
    hass,
    address: str,
) -> dict[str, Any] | None:
    """GET DSNY collection JSON for the given free-text address."""
    if not address or not address.strip():
        return None

    query = urlencode(
        {
            "address": address.strip(),
            "idForService": ID_FOR_SERVICE,
        }
    )
    url = f"{DSNY_BASE_URL}?{query}"
    session = async_get_clientsession(hass)

    try:
        async with session.get(url, headers=DSNY_HEADERS, timeout=60) as resp:
            text = await resp.text()
            if resp.status != 200:
                _LOGGER.error("DSNY HTTP %s: %s", resp.status, text[:500])
                return None
    except TimeoutError:
        _LOGGER.exception("DSNY request timed out")
        return None
    except aiohttp.ClientError:
        _LOGGER.exception("DSNY request failed")
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        _LOGGER.error("DSNY response was not JSON")
        return None
