"""Pure DSNY payload parsing (no Home Assistant imports; testable offline)."""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime, timedelta
from typing import Any

# Order used for TTS “scheduled vs not scheduled” summaries.
CANONICAL_COLLECTION_TYPES: tuple[str, ...] = (
    "Trash",
    "Recycling",
    "Compost",
    "Large items",
)

_ROUTING_TIME_TOKEN_RE = re.compile(
    r"(\d{1,2}):(\d{2})\s*(AM|PM)", re.IGNORECASE
)

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


def residential_routing_window_starts(
    residential_routing: str | None,
) -> list[tuple[int, int, str]]:
    """Parse DSNY ``ResidentialRoutingTime`` text into window start times.

    Each window is assumed to appear as ``start - end``; we take every other
    time token starting at the first as a *start* (e.g. ``8:00 AM - 9:00 AM``).

    Returns list of ``(hour12, minute, "AM"|"PM")`` in order of appearance.
    """
    if not residential_routing or not str(residential_routing).strip():
        return []
    matches = list(_ROUTING_TIME_TOKEN_RE.finditer(str(residential_routing)))
    if not matches:
        return []
    starts: list[tuple[int, int, str]] = []
    for i in range(0, len(matches), 2):
        m = matches[i]
        h12 = int(m.group(1))
        minute = int(m.group(2))
        if not 1 <= h12 <= 12 or not 0 <= minute <= 59:
            continue
        ap = m.group(3).upper()
        if ap not in ("AM", "PM"):
            continue
        starts.append((h12, minute, ap))
    return starts


def _start_to_minutes_from_midnight(h12: int, minute: int, ap: str) -> int:
    """Convert 12h clock to minutes from midnight for comparison."""
    apu = ap.upper()
    if apu == "AM":
        h24 = 0 if h12 == 12 else h12
    else:
        h24 = 12 if h12 == 12 else h12 + 12
    return h24 * 60 + minute


def residential_routing_anchor_start(
    residential_routing: str | None,
) -> tuple[int, int, str] | None:
    """Pick one start time for set-out messaging.

    Prefer the **earliest AM** window start; if none, use the first start in the
    string. Returns ``(hour12, minute, AM|PM)`` or ``None`` if unparseable.
    """
    starts = residential_routing_window_starts(residential_routing)
    if not starts:
        return None
    am_starts = [s for s in starts if s[2].upper() == "AM"]
    pool = am_starts if am_starts else starts
    best = min(
        pool,
        key=lambda s: _start_to_minutes_from_midnight(s[0], s[1], s[2]),
    )
    return best


def format_routing_start_spoken(h12: int, minute: int, ap: str) -> str:
    """Spoken-friendly time for TTS (e.g. ``8 A M``, ``6 30 P M``)."""
    apu = ap.upper()
    period = " ".join(list(apu))
    if minute == 0:
        return f"{h12} {period}"
    return f"{h12} {minute} {period}"


def format_routing_start_display(h12: int, minute: int, ap: str) -> str:
    """Human display like ``8:00 AM``."""
    return f"{h12}:{minute:02d} {ap.upper()}"
