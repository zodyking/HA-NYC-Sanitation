"""Sensors with human-readable schedule text and shared diagnostics."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_COLLECTION_TYPES_TODAY,
    ATTR_COLLECTION_TYPES_TOMORROW,
    ATTR_COMMUNITY_BOARD,
    ATTR_FORMATTED_ADDRESS,
    ATTR_RESIDENTIAL_ROUTING,
    DOMAIN,
)
from .coordinator import DSNYCoordinator
from .parse import collection_types_today, collection_types_tomorrow


def _join_types(types: list[str]) -> str:
    return ", ".join(types) if types else "None"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up text sensors for today's and tomorrow's collections."""
    coordinator: DSNYCoordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities(
        [
            CollectionsSummarySensor(
                coordinator,
                entry,
                translation_key="collections_today",
                unique_id_suffix="collections_today",
                tomorrow=False,
            ),
            CollectionsSummarySensor(
                coordinator,
                entry,
                translation_key="collections_tomorrow",
                unique_id_suffix="collections_tomorrow",
                tomorrow=True,
            ),
        ],
        True,
    )


class CollectionsSummarySensor(CoordinatorEntity[DSNYCoordinator], SensorEntity):
    """Comma-separated list of collection types for today or tomorrow."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:calendar-text"

    def __init__(
        self,
        coordinator: DSNYCoordinator,
        entry: ConfigEntry,
        *,
        translation_key: str,
        unique_id_suffix: str,
        tomorrow: bool,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._tomorrow = tomorrow
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{DOMAIN}_{unique_id_suffix}"

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
    def native_value(self) -> str | None:
        if not self.available:
            return None
        payload = self.coordinator.data["payload"]
        assert isinstance(payload, dict)
        now = dt_util.now()
        if self._tomorrow:
            return _join_types(collection_types_tomorrow(payload, now))
        return _join_types(collection_types_today(payload, now))

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        if not data or not data.get("nyc_valid") or not data.get("payload"):
            return {}
        payload = data["payload"]
        assert isinstance(payload, dict)
        now = dt_util.now()
        rt = data.get("routing") or {}
        return {
            ATTR_RESIDENTIAL_ROUTING: rt.get("residential"),
            ATTR_COLLECTION_TYPES_TODAY: collection_types_today(payload, now),
            ATTR_COLLECTION_TYPES_TOMORROW: collection_types_tomorrow(payload, now),
            ATTR_FORMATTED_ADDRESS: data.get("formatted_address"),
            ATTR_COMMUNITY_BOARD: data.get("community_board"),
        }
