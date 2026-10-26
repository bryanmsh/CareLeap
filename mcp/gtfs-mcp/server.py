"""gtfs-mcp — stdio MCP server wrapping the CareLeap routing engine.

Owner: M1. Exposes the engine's authoritative round-trip router so agents route
against a cached GTFS feed instead of live third-party routing APIs (see
AGENTS.md: "prefer deterministic, cached data"). Shapes are fixed by
docs/contracts.md §2.

Feed selection (deterministic, no network):
    - If env GTFS_DIR is set, load that GTFS directory resolved to GTFS_DATE
      (ISO "YYYY-MM-DD"); that is the real PVTA feed.
    - Otherwise fall back to a small SYNTHETIC feed so callers get real routing
      answers now. Synthetic results are labelled as such in `sources` and are
      never to be presented as findings (guardrail: template/illustrative numbers).

Run: GTFS_DIR=data/cache/pvta GTFS_DATE=2026-11-12 .venv/bin/python mcp/gtfs-mcp/server.py
     (or with neither env var, on the synthetic fallback feed).
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from typing import Any

# Make the repo root importable so `import engine` works when run as a script.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from mcp.server.mcpserver import MCPServer  # noqa: E402

from engine import one_way, round_trip  # noqa: E402
from engine.gtfs import Timetable, fmt_gtfs_time  # noqa: E402
from engine.synth import access_links, build_grid_feed  # noqa: E402
from engine.types import DEFAULT_LIMITS, Leg  # noqa: E402

SERVER = "gtfs-mcp"
server = MCPServer(name=SERVER, version="0.1.0")

# --------------------------------------------------------------------------
# Feed loading (cached once per process).
# --------------------------------------------------------------------------
_SYNTHETIC_DATE = "2026-11-12"


@lru_cache(maxsize=1)
def _feed() -> Timetable:
    gtfs_dir = os.environ.get("GTFS_DIR")
    gtfs_date = os.environ.get("GTFS_DATE", _SYNTHETIC_DATE)
    if gtfs_dir and os.path.isdir(gtfs_dir):
        return Timetable.from_gtfs_dir(gtfs_dir, gtfs_date)
    # synthetic fallback: a single bidirectional line, so the tools return real
    # routing answers for wiring/tests even before the PVTA cache lands.
    return build_grid_feed(n_stops=4, date=gtfs_date)


def _feed_source() -> dict[str, Any]:
    """Provenance for every numeric answer (guardrail: every number carries a source)."""
    if os.environ.get("GTFS_DIR"):
        return {
            "name": "PVTA GTFS",
            "vintage": _feed().service_date,
            "synthetic": False,
            "url": "https://www.pvta.com/",
        }
    return {
        "name": "synthetic GTFS (illustrative — not a finding)",
        "vintage": _feed().service_date,
        "synthetic": True,
        "url": None,
    }


def _leg_dict(leg: Leg) -> dict[str, Any]:
    return {
        "kind": leg.kind,
        "from_stop": leg.from_stop,
        "to_stop": leg.to_stop,
        "route_id": leg.route_id,
        "dep": leg.dep,
        "arr": leg.arr,
        "dep_hms": fmt_gtfs_time(leg.dep),
        "arr_hms": fmt_gtfs_time(leg.arr),
    }


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------
@server.tool(name="round_trip")  # contracts.md §2 tool name
def round_trip_tool(origin: str, clinic: str, date: str, start: int, minutes: int) -> dict[str, Any]:
    """Round trip for an appointment. Returns RoundTripResult (contracts.md §2).

    `origin`/`clinic` are stop_ids or "lat,lon"; times are seconds since local
    midnight (may exceed 86400 — never wrapped).
    """
    r = round_trip(_feed(), _resolve(origin), _resolve(clinic), date, int(start), int(minutes))
    return {
        "server": SERVER,
        "reachable": r.reachable,
        "out_legs": [_leg_dict(l) for l in r.out_legs],
        "ret_legs": [_leg_dict(l) for l in r.ret_legs],
        "last_bus_home": r.last_bus_home,
        "last_bus_home_hms": fmt_gtfs_time(r.last_bus_home) if r.last_bus_home is not None else None,
        "reason": r.reason,
        "sources": [_feed_source()],
    }



@server.tool()
def plan_trip(origin: str, dest: str, date: str, depart_after: int | None = None,
              arrive_by: int | None = None) -> dict[str, Any]:
    """One-way transit trip. Times are seconds since local midnight (may exceed 86400)."""
    tt = _feed()
    o_stops = access_links(tt, _resolve(origin), DEFAULT_LIMITS)
    d_stops = access_links(tt, _resolve(dest), DEFAULT_LIMITS)
    if not o_stops or not d_stops:
        return {
            "server": SERVER, "reachable": False, "legs": [],
            "reason": "origin or dest resolves to no stop within walk limit",
            "sources": [_feed_source()],
        }
    res = one_way(
        tt, o_stops, d_stops, date,
        depart_after=int(depart_after) if depart_after is not None else None,
        arrive_by=int(arrive_by) if arrive_by is not None else None,
        origin_label="origin", dest_label="dest",
    )
    legs = res[1] if res else []
    arr = res[0] if res else None
    ok = bool(legs) and (arrive_by is None or (arr is not None and arr <= int(arrive_by)))
    reason = (f"arrive {fmt_gtfs_time(arr)}" if arr is not None else "no journey found")
    return {
        "server": SERVER,
        "reachable": ok,
        "legs": [_leg_dict(l) for l in legs],
        "reason": reason,
        "sources": [_feed_source()],
    }


@server.tool()
def service_changes(since: str) -> dict[str, Any]:
    """Service changes in the feed since an ISO date.

    The in-memory feed is resolved to a single service date, so change tracking
    across feed versions is not available here; reported honestly rather than faked.
    """
    return {
        "server": SERVER,
        "since": since,
        "service_date": _feed().service_date,
        "changes": [],
        "note": "single-date feed; cross-version change tracking not available",
        "sources": [_feed_source()],
    }


@server.tool()
def validate_feed() -> dict[str, Any]:
    """Validate the loaded feed and report its size and service window."""
    tt = _feed()
    deps = [st.dep for st in tt.stop_times]
    return {
        "server": SERVER,
        "ok": bool(tt.stops and tt.trips and tt.stop_times),
        "service_date": tt.service_date,
        "n_stops": len(tt.stops),
        "n_trips": len(tt.trips),
        "n_stop_times": len(tt.stop_times),
        "earliest_departure": min(deps) if deps else None,
        "latest_departure": max(deps) if deps else None,
        "crosses_midnight": any(d >= 86400 for d in deps),
        "sources": [_feed_source()],
    }


def _resolve(ref: str):
    """Parse a tool arg into an OriginRef/ClinicRef: 'lat,lon' -> tuple, else stop_id."""
    if isinstance(ref, str) and "," in ref:
        parts = ref.split(",")
        if len(parts) == 2:
            try:
                return (float(parts[0]), float(parts[1]))
            except ValueError:
                pass
    return ref


# --------------------------------------------------------------------------
# Resources
# --------------------------------------------------------------------------
@server.resource("gtfs://feed/metadata", name="feed-metadata", mime_type="application/json")
def feed_metadata() -> str:
    import json
    tt = _feed()
    return json.dumps({
        "feed": _feed_source()["name"],
        "vintage": tt.service_date,
        "service_date": tt.service_date,
        "n_stops": len(tt.stops),
        "n_trips": len(tt.trips),
        "source": _feed_source(),
    })


@server.resource("gtfs://stops", name="stop-list", mime_type="application/json")
def stop_list() -> str:
    import json
    tt = _feed()
    return json.dumps({
        "stops": [
            {"stop_id": s.stop_id, "lat": s.lat, "lon": s.lon, "name": s.name,
             "wheelchair_boarding": s.wheelchair_boarding}
            for s in tt.stops.values()
        ],
        "source": _feed_source(),
    })


@server.prompt()
def explain_trip(trip_json: str) -> str:
    """Plain-language day-ribbon explanation of a round_trip result."""
    return (
        "Explain this round trip in plain language at a grade-6 reading level: when to leave, "
        "which bus, where to transfer, and the last bus home. Logistics only; no clinical advice.\n\n"
        + trip_json
    )


if __name__ == "__main__":
    server.run()
