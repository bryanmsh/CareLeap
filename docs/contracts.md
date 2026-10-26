# contracts.md — the fixed shapes between parts

> **This is the H1 gate.** Once these shapes are agreed, M1/M2/M3/M4 build in parallel
> against fake data until the real data lands. **Do not change a shape without telling
> the whole team** — a change here ripples into everyone's code and tests.
>
> Referenced by steering `structure.md` via `#[[file:docs/contracts.md]]`.

Conventions used below:
- **Times** are integer **seconds since local midnight of the service date**. GTFS times
  may exceed 86400 (e.g. `24:30:00` → `88200`); callers must preserve this, never wrap it.
- **GEOIDs** are Census block-group GEOIDs as strings (12-digit, e.g. `"250130001001"`).
- **Coordinates** are WGS84 decimal degrees (`lat`, `lon`), floats.
- **Booleans** are real booleans, not 0/1.
- Every response that produces an on-screen number carries a `sources` list so the
  "How we know this is right" drawer can trace it.

---

## 1. Data files (Parquet caches)

### `data/cache/origins.parquet` — M2 → M1, M2
One row per block-group origin point (population-weighted).

| column | type | notes |
|---|---|---|
| `bg_geoid` | str | 12-digit block-group GEOID (primary key) |
| `lat` | float | population-weighted centroid latitude |
| `lon` | float | population-weighted centroid longitude |
| `carless_adults` | int | adults in households with no vehicle (from ACS B25044 + B01001) |
| `pop` | int | total population (B01003) |
| `ej_flag` | bool | MassGIS Environmental Justice block group |
| `lep_pct` | float | limited-English-proficient share, 0.0–1.0 (C16002) |
| `age65_pct` | float | share aged 65+, 0.0–1.0 (B01001) |

### `data/cache/stops_walk.parquet` — M2 → M1
Walk links from each origin to nearby PVTA stops (≤ 800 m).

| column | type | notes |
|---|---|---|
| `bg_geoid` | str | origin block group |
| `stop_id` | str | PVTA GTFS `stop_id` |
| `walk_min` | float | walk minutes = straight-line_m × 1.3 / 80 m-per-min (MVP) |

A single `bg_geoid` has many rows (one per reachable stop).

### `data/cache/cube.parquet` — M2 → UI
The reachability cube. One row per (clinic, visit_type, day, hour, block group).

| column | type | notes |
|---|---|---|
| `clinic_id` | str | clinic identifier (matches `clinic_schedules.csv`) |
| `visit_type` | str | e.g. `colonoscopy`, `prenatal`, `dialysis`, `chemo` |
| `day` | str | `mon`..`sun` |
| `hour` | int | appointment start hour, 24h local (7..18) |
| `bg_geoid` | str | origin block group |
| `reachable` | bool | round trip possible given visit length |
| `reason` | str | short human-readable why (feeds the day ribbon) |

---

## 2. Engine API (Python) — M1 → M2, M4

The core function. Also exposed as the `gtfs-mcp` tool `round_trip`.

```python
def round_trip(
    origin: OriginRef,      # bg_geoid OR (lat, lon); engine resolves walk links
    clinic: ClinicRef,      # clinic_id OR (lat, lon)
    date: str,              # ISO service date "YYYY-MM-DD"
    start: int,             # appointment start, seconds since local midnight
    minutes: int,           # visit length in minutes (includes prep/recovery)
) -> RoundTripResult: ...
```

```python
@dataclass
class Leg:
    kind: str          # "walk" | "bus"
    from_stop: str     # stop_id or "origin"/"clinic"
    to_stop: str
    route_id: str | None
    dep: int           # seconds since local midnight (may exceed 86400)
    arr: int           # seconds since local midnight (may exceed 86400)

@dataclass
class RoundTripResult:
    reachable: bool
    out_legs: list[Leg]        # [] if not reachable outbound
    ret_legs: list[Leg]        # [] if not reachable return
    last_bus_home: int | None  # latest return departure that still gets home, or None
    reason: str                # e.g. "arrive 7:52 ok; last useful bus 9:41 before visit ends 10:00"
```

**Reachability definition (authoritative):** a slot is `reachable` iff there exists an
outbound journey arriving ≤ `start − 600` (10-min check-in buffer) **and** a return journey
departing ≥ `start + minutes*60`, both on the same service date, within limits:
≤ 2h each way, ≤ 2 transfers, each walk leg ≤ 800 m, earliest home departure ≥ 05:30.

---

## 3. HTTP API

Base URL in dev: `http://localhost:8000`. All responses JSON.

### `GET /audit?clinic&community&day` — M2 → UI
Reachability for one clinic × community × day.

```jsonc
{
  "cells": [
    { "day": "mon", "hour": 8, "share": 0.12, "n": 540, "reached": 65 }
    // share = reached / n (car-less adults); one cell per hour
  ],
  "equity": {
    "ej":        { "share": 0.10, "n": 320 },
    "lep":       { "share": 0.08, "n": 140 },
    "age65":     { "share": 0.15, "n": 90  },
    "zero_veh":  { "share": 0.12, "n": 540 }
  },
  "equity_ci": {                       // M3, additive; null when ACS margins are not built
    "ej":        { "share": 0.10, "lo": 0.07, "hi": 0.13, "moe": 0.03, "n": 320 },
    "lep":       { "share": 0.08, "lo": 0.03, "hi": 0.13, "moe": 0.05, "n": 140 },
    "age65":     { "share": 0.15, "lo": 0.11, "hi": 0.19, "moe": 0.04, "n": 90  },
    "zero_veh":  { "share": 0.12, "lo": 0.10, "hi": 0.14, "moe": 0.02, "n": 540 }
    // 90% confidence interval from ACS 5-yr margins of error (engine/equity.py,
    // Census ACS handbook ch. 8 formulas). share and n equal "equity" exactly;
    // always lo <= share <= hi, all in [0, 1]. Example values are illustrative.
  },
  "sources": [
    { "name": "PVTA GTFS", "vintage": "2026-09-18", "url": "https://www.pvta.com/..." },
    { "name": "ACS 5-yr B25044", "vintage": "2022", "url": "https://..." }
  ]
}
```

### `POST /whatif  { clinic, shift: { block, to } }` — M2 → UI
Recompute after moving a clinic block. **Returns the same shape as `/audit`** so the UI
reuses one renderer.

```jsonc
// request
{ "clinic": "baystate-gi", "shift": { "block": "mon-08", "to": 10 } }
// response: identical shape to GET /audit
```

### `POST /plan  { patient, visit_type, barriers }` — M4 → UI
Build a Visit Planner plan. `patient` is synthetic only.

```jsonc
// request
{
  "patient": { "id": "maria", "origin_bg": "250130...", "lang": "es" },
  "visit_type": "colonoscopy",
  "barriers": {
    "has_transport": false, "work_shift": [7, 15], "childcare": false,
    "has_escort": true, "cost_worry": true, "language": "es",
    // OPTIONAL childcare window (M4, VP-20). When the patient must be home to
    // care for someone, the plan SHALL NOT recommend a slot/ride whose
    // door-to-door window (travel included) overlaps this window.
    // Hours are 24h local; a window may cross midnight (e.g. {start:22,end:6}).
    // Omit the key when there is no window; `childcare: true` without a window
    // still flags the need but applies no time constraint.
    "childcare_window": { "start": 15, "end": 18 }
  }
}
// response
{
  "options": [
    {
      "kind": "ride",           // "slot" | "ride" | "tele" | "prep" | "none"
      "details": { "slot": "2026-11-12T15:30:00", "window": "COA volunteer 15:00-17:00" },
      "why": "Sedation requires an escort; transit-only is not allowed."
    }
  ],
  "itinerary": {
    "out_legs": [ /* Leg shape from §2 */ ],
    "ret_legs": [ /* Leg shape */ ],
    "last_bus_home": 68460,
    "plan_b": "If you miss the 18:01 bus, the 18:46 still gets you home by 19:20."
  },
  "pt1_prefill": { /* fields from data/manual/pt1_fields.json, values filled */ }
}
```

### `GET /provenance?id` — M4 (with M1) → UI
Powers the "How we know this is right" drawer. `id` identifies an on-screen number.

```jsonc
{
  "source":   { "name": "PVTA GTFS", "vintage": "2026-09-18" },
  "requirement_id": "RT-8",                 // from the raptor-router spec (EARS id)
  "properties": [
    { "name": "round-trip soundness", "status": "pass" },
    { "name": "midnight safety",      "status": "pass" }
  ],
  "spec_link": ".kiro/specs/raptor-router/requirements.md#RT-8"
}
```

### `GET /rural?town` — M1 → UI (rural lens; additive, 2026-10-24)
The "no option at all" verdict per block group. Reachability comes only from the cube;
the per-town options come from the hand-collected tables `data/manual/rural_options.csv`
+ `rural_coverage.csv` (M3), joined through `data/cache/bg_towns.parquet`
(`pipeline/build_towns.py`, TIGER county subdivisions). `town` is optional and
case-insensitive; unknown town → 404. Mock mode returns an empty, labelled answer.

```jsonc
{
  "town": "Rowe",                       // echo of the filter, or null
  "features": [
    { "bg_geoid": "250110401001", "town": "Rowe", "county": "Franklin",
      "lat": 42.69, "lon": -72.92, "carless_adults": 20,
      "transit_share": 0.0,             // share of ALL cube cells (every clinic × day × hour) reachable
      "desert": true,                   // no PVTA/FRTA stop within the walk limit
      "verdict": "none",                // transit | assisted_only | none | not_assessed
      "coverage_tier": "none" }
  ],
  "summary": { "n_bg": 1, "carless_adults": 20,
               "by_verdict": { "transit": {"n_bg": 0, "carless_adults": 0}, "none": {"n_bg": 1, "carless_adults": 20}, /* ... */ } },
  "options": [                          // the town's row(s) from the rural tables, cited
    { "town": "Rowe", "county": "Franklin", "coverage_tier": "none", "has_any_option": false,
      "dial_a_ride": null, "coa_driver": null, "pt1": null,
      "source_url": "https://...", "verified_by": "phone", "date": "2026-10-24" }
  ],
  "towns_available": ["Agawam", "Amherst", "..."],
  "sources": [ /* SourceRef[]: cube, ACS, rural tables (vintage = newest row date), TIGER COUSUB 2024 */ ]
}
```

Verdict rule: `transit` if any cube cell for the block group is reachable; otherwise
`not_assessed` if the town is not in the rural table (Hampden towns today); otherwise
`assisted_only` if `has_any_option` is TRUE, else `none`.

### Serving a frozen snapshot
`CARELEAP_CACHE_DIR=<dir>` redirects every cache path (`cube.parquet`,
`origins.parquet`, `bg_towns.parquet`, `pvta/`, `manifest.json`). `make snapshot` freezes
`data/cache/` into `data/snapshots/demo-v1/`; `make demo` serves it in real mode.

---

## 4. Testing note

Until the UI exists, **every API is tested with pytest/Playwright against the shapes
above**. M4 owns the contract tests. A shape change must update the contract tests in the
same PR.
