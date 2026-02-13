"""Debug helpers for conditional verbose diagnostics."""

from __future__ import annotations

import os
from typing import Any


def resolve_debug(debug: bool = False) -> bool:
    if debug:
        return True
    raw = os.getenv("SHORT_DECISION_DEBUG", "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def with_debug(payload: dict[str, Any], debug: bool, debug_info: dict[str, Any]) -> dict[str, Any]:
    if not debug:
        return payload
    enriched = dict(payload)
    enriched["debug_info"] = debug_info
    return enriched
