"""Build spoken reminder text from user templates and collection types."""

from __future__ import annotations

import re
from typing import Any

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


def build_tts_message(
    opts: dict[str, Any],
    collection_types: list[str],
    tomorrow_weekday: str,
) -> str:
    """Return full announcement string, or empty if nothing to say."""
    if not collection_types:
        return ""

    prefix = str(opts.get("tts_message_prefix") or "").strip()
    types_csv = ", ".join(collection_types)
    ctx = {
        "weekday": tomorrow_weekday,
        "types": types_csv,
        "types_sentence": _types_sentence(collection_types),
        "type": collection_types[0] if len(collection_types) == 1 else types_csv,
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
        body_tmpl = "Tomorrow, {weekday}, sanitation collections include {types_sentence}."

    body = _substitute_placeholders(body_tmpl, ctx)
    if not prefix:
        return body
    return f"{prefix} {body}".strip()
