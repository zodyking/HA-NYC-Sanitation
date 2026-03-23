"""Pure DSNY payload parsing (no Home Assistant imports; testable offline)."""

from __future__ import annotations

import calendar
from datetime import datetime
from typing import Any

from .const import NYC_BOROUGH_CODES, NYC_BOROUGH_NAMES

WEEKDAYS_ORDER = list(calendar.day_name)  # Monday .. Sunday


def _parse_day_set(value: str | None) -> set[str]:
    if not value or not str(value).strip():
        return set()
    return {d.strip() for d in str(value).split(",") if d.strip()}


def is_nyc_response(payload: dict[str, Any]) -> bool:
    pluto = payload.get("Pluto")
    if isinstance(pluto, dict):
        boro = pluto.get("Borough")
        if boro is not None and str(boro).strip().upper() in NYC_BOROUGH_CODES:
            return True
        name = pluto.get("BoroughName")
        if isinstance(name, str) and name.upper() in NYC_BOROUGH_NAMES:
            return True
    goat = payload.get("Goat")
    if isinstance(goat, dict):
        first = goat.get("firstBoroughName")
        if isinstance(first, str) and first.strip().upper() in NYC_BOROUGH_NAMES:
            return True
    return False


def community_board(payload: dict[str, Any]) -> str | None:
    goat = payload.get("Goat")
    if not isinstance(goat, dict):
        return None
    boro = goat.get("firstBoroughName")
    dist = goat.get("communityDistrictNumber")
    if isinstance(boro, str) and isinstance(dist, str):
        return f"{boro.strip()} District {dist.strip()}"
    if isinstance(boro, str):
        return boro.strip()
    return None


def build_weekly_schedule(data: dict[str, Any]) -> dict[str, list[str]]:
    """Map weekday name -> list of collection type labels for the panel."""
    regular = _parse_day_set(data.get("RegularCollectionSchedule"))
    recycling = _parse_day_set(data.get("RecyclingCollectionSchedule"))
    organics = _parse_day_set(data.get("OrganicsCollectionSchedule"))
    bulk = _parse_day_set(data.get("BulkPickupCollectionSchedule"))

    weekly: dict[str, list[str]] = {d: [] for d in WEEKDAYS_ORDER}
    for day in WEEKDAYS_ORDER:
        types: list[str] = []
        if day in regular:
            types.append("Trash")
        if day in recycling:
            types.append("Recycling")
        if day in organics:
            types.append("Compost")
        if day in bulk:
            types.append("Large items")
        weekly[day] = types
    return weekly


def collection_types_today(data: dict[str, Any], now: datetime) -> list[str]:
    """Human-readable collection types due on the given local datetime's weekday."""
    day = calendar.day_name[now.weekday()]
    types: list[str] = []
    if day in _parse_day_set(data.get("RegularCollectionSchedule")):
        types.append("Trash")
    if day in _parse_day_set(data.get("RecyclingCollectionSchedule")):
        types.append("Recycling")
    if day in _parse_day_set(data.get("OrganicsCollectionSchedule")):
        types.append("Compost")
    if day in _parse_day_set(data.get("BulkPickupCollectionSchedule")):
        types.append("Large items")
    return types


def trash_due_today(data: dict[str, Any], now: datetime) -> bool:
    day = calendar.day_name[now.weekday()]
    return day in _parse_day_set(data.get("RegularCollectionSchedule"))
