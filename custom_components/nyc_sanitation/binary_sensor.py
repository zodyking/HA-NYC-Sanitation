"""Binary sensor: trash collection due today."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_COLLECTION_TYPES_TODAY,
    ATTR_COMMUNITY_BOARD,
    ATTR_FORMATTED_ADDRESS,
    ATTR_RESIDENTIAL_ROUTING,
    DOMAIN,
)
from .coordinator import DSNYCoordinator
from .parse import collection_types_today, trash_due_today


async def async_setup_entry(
    hass: HomeAssistant,
    _entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up trash due binary sensor from config entry."""
    coordinator: DSNYCoordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities([TrashDueBinarySensor(coordinator)], True)


class TrashDueBinarySensor(CoordinatorEntity[DSNYCoordinator], BinarySensorEntity):
    """True when regular (trash) collection is scheduled for today."""

    _attr_has_entity_name = True
    _attr_name = "Trash due"
    _attr_unique_id = f"{DOMAIN}_trash_due"

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
        return trash_due_today(payload, dt_util.now())

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        if not data or not data.get("nyc_valid") or not data.get("payload"):
            return {}
        payload = data["payload"]
        assert isinstance(payload, dict)
        rt = data.get("routing") or {}
        return {
            ATTR_RESIDENTIAL_ROUTING: rt.get("residential"),
            ATTR_COLLECTION_TYPES_TODAY: collection_types_today(payload, dt_util.now()),
            ATTR_FORMATTED_ADDRESS: data.get("formatted_address"),
            ATTR_COMMUNITY_BOARD: data.get("community_board"),
        }
