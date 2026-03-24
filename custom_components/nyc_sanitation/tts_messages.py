"""Build spoken reminder text from user templates and collection types."""

from __future__ import annotations

import re
from typing import Any

from .parse import (
    CANONICAL_COLLECTION_TYPES,
    format_routing_start_display,
    format_routing_start_spoken,
    residential_routing_anchor_start,
)

_TYPE_TO_TEMPLATE_KEY: dict[str, str] = {
    "Trash": "tts_message_trash",
    "Recycling": "tts_message_recycling",
    "Compost": "tts_message_compost",
    "Large items": "tts_message_large_items",
}

_PLACEHOLDER_RE = re.compile(r"\{([a-z_]+)\}")


def _types_sentence(types: list[str]) -> str:
    if not types:
        return ""
    if len(types) == 1:
        return types[0]
    if len(types) == 2:
        return f"{types[0]} and {types[1]}"
    *rest, last = types
    return f"{', '.join(rest)}, and {last}"


def _substitute_placeholders(template: str, mapping: dict[str, str]) -> str:
    def _repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in mapping:
            return mapping[key]
        return match.group(0)

    return _PLACEHOLDER_RE.sub(_repl, template)


def _build_type_status(collection_types: list[str]) -> str:
    scheduled_set = set(collection_types)
    present = [x for x in CANONICAL_COLLECTION_TYPES if x in scheduled_set]
    absent = [x for x in CANONICAL_COLLECTION_TYPES if x not in scheduled_set]
    parts: list[str] = []
    if present:
        parts.append(f"{_types_sentence(present)} will be collected.")
    if absent:
        parts.append(f"No {_types_sentence(absent)} will be collected.")
    return " ".join(parts)


def _build_large_items_note(collection_types: list[str]) -> str:
    """Short bulk reminder when large items are scheduled; empty otherwise."""
    if "Large items" in collection_types:
        return "Follow DSNY bulk set-out rules."
    return ""


def _build_curb_reminder(
    residential_routing: str | None,
    anchor_spoken: str,
) -> str:
    if anchor_spoken:
        return (
            "Put materials at the curb this evening before tomorrow's pickup "
            f"at {anchor_spoken}."
        )
    raw = (residential_routing or "").strip()
    if raw:
        return (
            "Put materials at the curb this evening for tomorrow's pickup. "
            "Open the Sanitation panel for routing times."
        )
    return (
        "Put materials at the curb this evening for tomorrow's pickup. "
        "Check the Sanitation panel for routing times."
    )


def build_tts_message(
    opts: dict[str, Any],
    collection_types: list[str],
    tomorrow_weekday: str,
    residential_routing: str | None = None,
) -> str:
    """Return full announcement string, or empty if nothing to say."""
    if not collection_types:
        return ""

    prefix = str(opts.get("tts_message_prefix") or "").strip()
    types_csv = ", ".join(collection_types)

    anchor = residential_routing_anchor_start(residential_routing)
    routing_first_start_spoken = ""
    routing_first_start_display = ""
    if anchor:
        routing_first_start_spoken = format_routing_start_spoken(*anchor)
        routing_first_start_display = format_routing_start_display(*anchor)

    curb_reminder = _build_curb_reminder(
        residential_routing, routing_first_start_spoken
    )
    type_status = _build_type_status(collection_types)
    large_items_note = _build_large_items_note(collection_types)
    has_large = "Large items" in collection_types

    scheduled_set = set(collection_types)
    present = [x for x in CANONICAL_COLLECTION_TYPES if x in scheduled_set]
    absent = [x for x in CANONICAL_COLLECTION_TYPES if x not in scheduled_set]

    ctx: dict[str, str] = {
        "weekday": tomorrow_weekday,
        "types": types_csv,
        "types_sentence": _types_sentence(collection_types),
        "type": collection_types[0] if len(collection_types) == 1 else types_csv,
        "curb_reminder": curb_reminder,
        "type_status": type_status,
        "large_items_note": large_items_note,
        "has_large_items": "yes" if has_large else "no",
        "types_scheduled": ", ".join(present),
        "types_not_scheduled": ", ".join(absent),
        "routing_first_start": routing_first_start_spoken,
        "routing_first_start_display": routing_first_start_display,
        "residential_routing_raw": (residential_routing or "").strip(),
    }

    if len(collection_types) == 1:
        tmpl_key = _TYPE_TO_TEMPLATE_KEY.get(
            collection_types[0], "tts_message_mixed"
        )
        body_tmpl = str(opts.get(tmpl_key) or "").strip() or str(
            opts.get("tts_message_mixed") or ""
        ).strip()
    else:
        body_tmpl = str(opts.get("tts_message_mixed") or "").strip()

    if not body_tmpl:
        body_tmpl = "{curb_reminder} Tomorrow. {type_status} {large_items_note}"

    body = _substitute_placeholders(body_tmpl, ctx)
    body = re.sub(r"\s{2,}", " ", body).strip()
    if not prefix:
        return body
    return f"{prefix} {body}".strip()


# Synthetic pickup sets for per-template preview (see README).
_SCENARIO_TYPES: dict[str, list[str]] = {
    "trash": ["Trash"],
    "recycling": ["Recycling"],
    "compost": ["Compost"],
    "large_items": ["Large items"],
    "mixed": ["Trash", "Recycling", "Compost"],
}


def scenario_collection_types(scenario: str) -> list[str] | None:
    """Return fixed types for *scenario*, or ``None`` for ``tomorrow_actual`` (live data)."""
    if scenario == "tomorrow_actual":
        return None
    return list(_SCENARIO_TYPES[scenario])


