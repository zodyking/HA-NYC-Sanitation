"""Data update coordinator for DSNY collection data."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .address import async_reverse_geocode
from .const import DOMAIN, UPDATE_INTERVAL
from .dsny_client import async_fetch_collection
from .parse import (
    WEEKDAYS_ORDER,
    build_weekly_schedule,
    community_board,
    is_nyc_response,
)

_LOGGER = logging.getLogger(__name__)


class DSNYCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch geocoded address + DSNY schedule."""

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        geocoded = await async_reverse_geocode(self.hass)
        if not geocoded:
            return {
                "nyc_valid": False,
                "error": "Could not resolve an address from home coordinates.",
                "geocoded_address": None,
                "payload": None,
                "weekly": {d: [] for d in WEEKDAYS_ORDER},
                "routing": {},
                "community_board": None,
            }

        _LOGGER.debug("DSNY query address (from Nominatim / home): %s", geocoded)

        payload = await async_fetch_collection(self.hass, geocoded)
        if not payload:
            raise UpdateFailed("DSNY API returned no data")

        nyc = is_nyc_response(payload)
        rt = payload.get("RoutingTime") or {}
        routing = {
            "residential": rt.get("ResidentialRoutingTime"),
            "commercial": rt.get("CommercialRoutingTime"),
            "mixed_use": rt.get("MixedUseRoutingTime"),
        }

        if not nyc:
            return {
                "nyc_valid": False,
                "error": "This integration only supports NYC addresses.",
                "geocoded_address": geocoded,
                "formatted_address": payload.get("FormattedAddress"),
                "payload": payload,
                "weekly": {d: [] for d in WEEKDAYS_ORDER},
                "routing": routing,
                "community_board": community_board(payload),
            }

        weekly = build_weekly_schedule(payload)

        return {
            "nyc_valid": True,
            "error": None,
            "geocoded_address": geocoded,
            "formatted_address": payload.get("FormattedAddress") or geocoded,
            "payload": payload,
            "weekly": weekly,
            "routing": routing,
            "community_board": community_board(payload),
        }
