"""Binary sensor: any DSNY pickup scheduled tomorrow (local calendar)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
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
    ATTR_RESIDENTIAL_ROUTING,
    DOMAIN,
)
from .coordinator import DSNYCoordinator
from .parse import collection_types_today, collection_types_tomorrow


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up pickup-tomorrow binary sensor."""
    coordinator: DSNYCoordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities([PickupScheduledTomorrowBinarySensor(coordinator, entry)], True)


class PickupScheduledTomorrowBinarySensor(
    CoordinatorEntity[DSNYCoordinator], BinarySensorEntity
):
    """True when at least one collection type is scheduled for tomorrow."""

    _attr_has_entity_name = True
    _attr_translation_key = "pickup_scheduled_tomorrow"
    _attr_unique_id = f"{DOMAIN}_pickup_scheduled_tomorrow"
    _attr_icon = "mdi:calendar-arrow-right"

    def __init__(self, coordinator: DSNYCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry

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

    @property
    def is_on(self) -> bool | None:
        if not self.available:
            return None
        payload = self.coordinator.data["payload"]
        assert isinstance(payload, dict)
        types = collection_types_tomorrow(payload, dt_util.now())
        return bool(types)

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        if not data or not data.get("nyc_valid") or not data.get("payload"):
            return {}
        payload = data["payload"]
        assert isinstance(payload, dict)
        now = dt_util.now()
        rt = data.get("routing") or {}
        tomorrow_types = collection_types_tomorrow(payload, now)
        return {
            ATTR_COLLECTION_TYPES: tomorrow_types,
            ATTR_RESIDENTIAL_ROUTING: rt.get("residential"),
            ATTR_COLLECTION_TYPES_TODAY: collection_types_today(payload, now),
            ATTR_COLLECTION_TYPES_TOMORROW: tomorrow_types,
            ATTR_FORMATTED_ADDRESS: data.get("formatted_address"),
            ATTR_COMMUNITY_BOARD: data.get("community_board"),
        }
