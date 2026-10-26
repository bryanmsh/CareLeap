#!/usr/bin/env python3
"""Hook #4 — preToolUse (shell + web) live-routing blocker.

Blocks a shell command or web fetch that reaches a live third-party routing /
directions API. CareLeap must use deterministic cached GTFS via `gtfs-mcp`
(AGENTS.md "Prefer deterministic, cached data over live third-party routing
APIs"). Exit 2 so the CLI blocks the call and the stderr message reaches the
model.

Matched hosts / services (substring, case-insensitive):
  - maps.googleapis.com            (Google Directions / Distance Matrix)
  - router.project-osrm.org, osrm  (OSRM routing)
  - api.mapbox.com with a directions/routing path (Mapbox Directions)

Input: preToolUse JSON on stdin. We scan every string in `tool_input` (command,
url, args, ...) so it works for both the shell tool and a web-fetch tool.
"""
from __future__ import annotations

import json
import re
import sys

MESSAGE = "use gtfs-mcp"

# (label, regex) — regex is matched against the lower-cased blob of tool_input.
_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("maps.googleapis.com", re.compile(r"maps\.googleapis\.com")),
    ("router.project-osrm.org / osrm", re.compile(r"router\.project-osrm\.org|\bosrm\b")),
    # Mapbox: only the directions/routing products, not every mapbox URL.
    ("api.mapbox.com (directions/routing)",
     re.compile(r"api\.mapbox\.com/(?:directions|directions-matrix|matrix|optimized-trips|isochrone)")),
]


def _blob(tool_input: object) -> str:
    """Flatten every string in tool_input into one searchable string."""
    parts: list[str] = []

    def walk(v: object) -> None:
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, dict):
            for item in v.values():
                walk(item)
        elif isinstance(v, (list, tuple)):
            for item in v:
                walk(item)

    walk(tool_input)
    return "\n".join(parts).lower()


def main(argv: list[str] | None = None) -> int:
    raw = ""
    try:
        if not sys.stdin.isatty():
            raw = sys.stdin.read()
    except Exception:
        raw = ""

    event: dict = {}
    if raw.strip():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            print("block_live_routing: could not parse hook JSON; allowing call", file=sys.stderr)
            return 0

    blob = _blob(event.get("tool_input"))
    if not blob:
        return 0

    hits = [label for label, pat in _RULES if pat.search(blob)]
    if hits:
        print(
            "BLOCKED: live third-party routing API detected ("
            + ", ".join(hits)
            + "). " + MESSAGE + ": CareLeap routes on cached GTFS through "
            "gtfs-mcp, never a live directions API (AGENTS.md).",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
