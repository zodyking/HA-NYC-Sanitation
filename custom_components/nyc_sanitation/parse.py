"""Pure DSNY payload parsing (no Home Assistant imports; testable offline)."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
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


def collection_types_on_date(data: dict[str, Any], dt: datetime) -> list[str]:
    """Collection types for the weekday of *dt* (local), from a DSNY payload dict."""
    day = calendar.day_name[dt.weekday()]
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


def collection_types_tomorrow(data: dict[str, Any], now: datetime) -> list[str]:
    """Collection types scheduled for the calendar day after *now* (same tz semantics as *now*)."""
    return collection_types_on_date(data, now + timedelta(days=1))


def next_pickup_days(
    data: dict[str, Any],
    start_local_datetime: datetime,
    *,
    max_days: int = 21,
    limit: int = 2,
) -> list[tuple[date, list[str]]]:
    """First *limit* calendar days (from *start_local_datetime*'s date) with any collection.

    *start_local_datetime* should be start-of-day in the Home Assistant time zone.
    """
    out: list[tuple[date, list[str]]] = []
    for offset in range(max_days):
        dt = start_local_datetime + timedelta(days=offset)
        types = collection_types_on_date(data, dt)
        if types:
            out.append((dt.date(), list(types)))
            if len(out) >= limit:
                break
    return out
