# Reachability cube — design

> Design-first. This documents `pipeline/build_cube.py`, `engine/audit.py`, and the
> `/audit` + `/whatif` endpoints **as they exist today**. Requirements (`requirements.md`)
> and tasks (`tasks.md`) are derived from this document.

## 1. Purpose

The reachability cube answers one question for every community and every appointment
hour: **can a car-less adult who lives here make the round trip to this clinic for an
appointment starting at hour H, and get home afterward?** It is the single source of
truth behind the `/audit` view (reachability by hour + equity split) and `/whatif`
(what moving a clinic block would do to reachability).

Logistics only. Synthetic patients only. Every number carries a source and a vintage.

## 2. The cube — `pipeline/build_cube.py`

### 2.1 Shape

`data/cache/cube.parquet` is one row per cell:

| column      | type | meaning                                                  |
|-------------|------|----------------------------------------------------------|
| `clinic_id` | str  | clinic key (e.g. `BAY_GI_SPRINGFIELD`)                   |
| `visit_type`| str  | appointment type (default `primary_care`)                |
| `day`       | str  | `mon`..`sun`                                             |
| `hour`      | int  | appointment start hour, local, `7`..`18`                 |
| `bg_geoid`  | str  | 12-digit Census block-group GEOID                        |
| `reachable` | bool | round trip possible at this cell                         |
| `reason`    | str  | engine reason string when not reachable                  |

The current cache holds **one clinic** (`BAY_GI_SPRINGFIELD`), all seven days, hours
7–18 → 506 block groups × 7 × 12 = the full grid for that clinic.

### 2.2 Method — one `round_trip` per cell

For each `(clinic, day, hour, block_group)` the builder calls the engine's
authoritative `engine.round_trip(tt, origin, clinic_ref, date, start, visit_min)` and
stores `r.reachable` / `r.reason`. This is deliberately the **same** call the
differential tests validate, so the cube can never drift from the router.

- **Centroid resolution.** A block group is represented by its population-weighted
  centroid `(lat, lon)` from `origins.parquet`. `round_trip` resolves that coordinate
  to nearby stops using the engine's walk model; the cube stores only the boolean
  outcome.
- **Clinic anchors — `data/manual/clinic_stops.csv`.** Clinic records carry *addresses,
  not coordinates*, so the builder maps `clinic_id → stop_id` via this manual file and
  uses that PVTA stop's `(lat, lon)` as the clinic reference. A clinic whose anchor stop
  is **not in the feed on a given date is skipped with a warning** — never guessed —
  because every number must have a real source.
- **Timetable caching.** One `Timetable.from_gtfs_dir(PVTA_DIR, date)` is built per
  concrete date (the service calendar differs by weekday) and reused across hours and
  block groups.
- **Day → date mapping.** `_day_to_date` maps a weekday name to a concrete date inside
  the feed's service window, anchored on `--date` (default `2026-11-12`).

### 2.3 The discarded profile-search shortcut

A faster two-profile-search variant (`latest_departure` + `earliest_arrival`, comparing
stop membership) was **tried and discarded**. Comparing reachable stop *sets* ignored
walk time and precise timing, and it **under-reported** reachability — a near-flat
~1.2% versus the true ~31% that per-cell `round_trip` produces. The shortcut is only
allowed back behind a test proving it equals `round_trip` **cell for cell**.

### 2.4 Cost

~**9 minutes per clinic** (one `round_trip` × 506 block groups × 7 days × 12 hours).
The cube is therefore built offline and cached; the API never rebuilds it on a request.
`build_cube.py` is not run in tests.

## 3. Aggregation — `engine/audit.py` (the ONE path)

`engine/audit.py` is the single place that turns the cube into the `/audit` shape, so
`/audit`, `/whatif`, the MCP tool and the schedule optimizer can never disagree about a
number. Pure functions over pandas DataFrames.

### 3.1 Loaders & community filter
- `load_cube()` / `load_origins()` read the parquet files and normalise dtypes.
- `filter_community(origins, community)` restricts origins to `all`, a county name
  (`hampden` / `hampshire` / `franklin` → FIPS prefix) or a raw GEOID-prefix digit
  string. Anything else raises `AuditDataError`.

### 3.2 Car-less-adult weighting
Every share is weighted by **car-less adults — people, not block groups**:

- cell `n` = car-less adults in the community (`origins.carless_adults.sum()`).
- cell `reached` = car-less adults in the block groups where the slot is reachable at
  that hour.
- cell `share` = `reached / n` (0 when `n == 0`).

### 3.3 Equity groups
Over the whole day, averaged across the clinic's hours, each weighted by car-less
adults and the group's share of the population:

| group      | weight per block group                    |
|------------|-------------------------------------------|
| `ej`       | `carless_adults × ej_flag` (EJ block groups) |
| `lep`      | `carless_adults × lep_pct` (expected limited-English adults) |
| `age65`    | `carless_adults × age65_pct` (expected 65+ adults) |
| `zero_veh` | `carless_adults` (all car-less adults)    |

Each group returns `{share ∈ [0,1], n}`.

### 3.4 `audit(...)` and `whatif(...)`
- `audit(cube, origins, clinic, community, day, hours=None)` → `{cells, equity, sources}`.
- `whatif(cube, origins, clinic, block, to, community='all')` models the clinic's day as
  one block per cube hour. Moving `thu-08 → 10` removes the 08:00 block and offers it at
  10:00, recomputing that cell from the cube's 10:00 reachability. Same shape as
  `/audit`, so the UI reuses one renderer. A block or target hour outside the clinic's
  schedule raises `AuditDataError`.

### 3.5 Provenance — `sources()`
Returns source + vintage for every number: PVTA GTFS (vintage from
`data/cache/pvta/feed_info.txt` when present, else the manifest), ACS 5-year
(B25044/B01001/C16002), MassGIS EJ 2020, and the reachability cube itself.

## 4. API surface

### 4.1 Data mode — `api/deps.py`
`CARELEAP_DATA` selects `mock` (default) or `real`. `get_audit_data()` returns an
`AuditSource`:
- **mock**: carries the labelled mock payload (`api/mocks/audit.json`); routers return
  it verbatim, day stamped. Keeps the existing contract tests green.
- **real**: carries the cube + origins DataFrames, loaded once and cached with
  `functools.lru_cache`. If `cube.parquet` or `origins.parquet` is missing, the shared
  `_unavailable(...)` helper raises **HTTP 503** (never a silent fall back to mock).

Tests override `get_audit_data` via FastAPI `dependency_overrides` to inject tiny
synthetic frames, so the real-mode logic runs in CI with no cache.

### 4.2 `GET /audit?clinic&community&day`
- mock → the mock payload, day stamped.
- real → `engine.audit.audit(cube, origins, clinic, community, day)`.
- `AuditDataError` (unknown clinic / day / community) → **HTTP 404**.

### 4.3 `POST /whatif {clinic, shift:{block, to}}`
- Same `AuditResponse` shape as `/audit`.
- real → unknown clinic → **404**; a well-formed request whose block/hour is outside the
  clinic's schedule → **422**.

## 5. Constraints & invariants
- Reachability comes **only** from `engine.round_trip`; the cube never re-derives it.
- Times are seconds since local midnight; never wrapped ≥ 86400.
- `engine/audit.py` is the only aggregation path; `/audit` and `/whatif` must not
  compute shares themselves.
- The cube is built offline and cached; requests never trigger a rebuild.
