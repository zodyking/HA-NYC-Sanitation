"""Sensors: next two pickup dates (ISO) with collection types in attributes."""

from __future__ import annotations

import calendar
from datetime import date

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_COLLECTION_TYPES,
    ATTR_COLLECTION_TYPES_TODAY,
    ATTR_COLLECTION_TYPES_TOMORROW,
    ATTR_COMMUNITY_BOARD,
    ATTR_FORMATTED_ADDRESS,
    ATTR_PICKUP_WEEKDAY,
    ATTR_RESIDENTIAL_ROUTING,
    DOMAIN,
)
from .coordinator import DSNYCoordinator
from .parse import (
    collection_types_today,
    collection_types_tomorrow,
    next_pickup_days,
)

STATE_NO_SECOND = "none"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up pickup date 1 and pickup date 2 sensors."""
    coordinator: DSNYCoordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities(
        [
            PickupDateSensor(coordinator, entry, slot=1),
            PickupDateSensor(coordinator, entry, slot=2),
        ],
        True,
    )


class PickupDateSensor(CoordinatorEntity[DSNYCoordinator], SensorEntity):
    """State = YYYY-MM-DD for the Nth upcoming pickup day, or *none* for slot 2 if missing."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:calendar"

    def __init__(
        self, coordinator: DSNYCoordinator, entry: ConfigEntry, *, slot: int
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._slot = slot
        self._attr_translation_key = f"pickup_date_{slot}"
        self._attr_unique_id = f"{DOMAIN}_pickup_date_{slot}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="NYC Sanitation",
            manufacturer="NYC Department of Sanitation",
            model="Collection schedule",
        )

    @property
    def available(self) -> bool:
        data = self.coordinator.data
        if not data:
            return False
        return bool(data.get("nyc_valid") and data.get("payload"))

    def _pickup_pair(self) -> list[tuple[date, list[str]]]:
        payload = self.coordinator.data["payload"]
        assert isinstance(payload, dict)
        start = dt_util.start_of_local_day(dt_util.now())
        return next_pickup_days(payload, start, max_days=21, limit=2)

    @property
    def native_value(self) -> str | None:
        if not self.available:
            return None
        pairs = self._pickup_pair()
        idx = self._slot - 1
        if idx >= len(pairs):
            return STATE_NO_SECOND if self._slot == 2 else None
        return pairs[idx][0].isoformat()

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        if not data or not data.get("nyc_valid") or not data.get("payload"):
            return {}
        payload = data["payload"]
        assert isinstance(payload, dict)
        now = dt_util.now()
        rt = data.get("routing") or {}
        base = {
            ATTR_RESIDENTIAL_ROUTING: rt.get("residential"),
            ATTR_COLLECTION_TYPES_TODAY: collection_types_today(payload, now),
            ATTR_COLLECTION_TYPES_TOMORROW: collection_types_tomorrow(payload, now),
            ATTR_FORMATTED_ADDRESS: data.get("formatted_address"),
            ATTR_COMMUNITY_BOARD: data.get("community_board"),
        }
        pairs = self._pickup_pair()
        idx = self._slot - 1
        if idx >= len(pairs):
            if self._slot == 2:
                return {**base, ATTR_COLLECTION_TYPES: [], ATTR_PICKUP_WEEKDAY: None}
            return base
        day_date, types = pairs[idx]
        weekday_name = calendar.day_name[day_date.weekday()]
        return {
            **base,
            ATTR_COLLECTION_TYPES: types,
            ATTR_PICKUP_WEEKDAY: weekday_name,
        }
