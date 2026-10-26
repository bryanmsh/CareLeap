# Reachability cube — requirements (EARS)

Derived from `design.md`. Each requirement has a stable id `RC-n`.

## Cube construction

- **RC-1** — The system SHALL represent reachability as a cube with one row per
  `(clinic_id, visit_type, day, hour, bg_geoid)` carrying a boolean `reachable` and a
  `reason` string.
- **RC-2** — The system SHALL derive `reachable` ONLY from `engine.round_trip`; it SHALL
  NOT re-derive reachability by any other method.
- **RC-3** — When building a cell, the system SHALL represent a block group by its
  population-weighted centroid `(lat, lon)` from `origins.parquet`.
- **RC-4** — The system SHALL resolve each clinic to a PVTA stop via
  `data/manual/clinic_stops.csv` (`clinic_id → stop_id`) and use that stop's coordinates
  as the clinic reference.
- **RC-5** — When a clinic's anchor stop is not present in the feed for a given date,
  the system SHALL skip that clinic for that date with a warning and SHALL NOT guess a
  coordinate.
- **RC-6** — The system SHALL cover hours 7–18 local for days `mon`..`sun`, with each
  weekday mapped to a concrete date inside the feed's service window.
- **RC-7** — The system SHALL cache one `Timetable` per concrete date and reuse it
  across hours and block groups in a build.
- **RC-8** — The system SHALL NOT reintroduce the discarded profile-search shortcut
  unless a test proves it equals per-cell `round_trip` reachability cell for cell.

## Aggregation (engine/audit.py)

- **RC-9** — The system SHALL expose a single aggregation path (`engine/audit.py`) used
  by `/audit`, `/whatif` and any other consumer; endpoints SHALL NOT compute shares
  independently.
- **RC-10** — The system SHALL weight every share by car-less adults (people), where a
  cell's `n` is the car-less adults in the community and `reached` is the car-less
  adults in block groups reachable at that hour.
- **RC-11** — The system SHALL guarantee every `share` lies in `[0, 1]`, and SHALL
  return `share = 0` when `n == 0`.
- **RC-12** — The system SHALL return equity groups `ej`, `lep`, `age65`, `zero_veh`,
  each weighted as defined in `design.md §3.3`, averaged across the clinic's hours, each
  reporting `{share, n}`.
- **RC-13** — While filtering by community, the system SHALL accept `all`, a county name
  (hampden/hampshire/franklin), or a GEOID-prefix digit string, and SHALL raise
  `AuditDataError` for any other value.
- **RC-14** — When a requested clinic/day/community has no cube rows, the system SHALL
  raise `AuditDataError`.
- **RC-15** — The system SHALL return a non-empty `sources` list, each entry carrying a
  `name` and a `vintage`, for every audit payload.
- **RC-16** — For a what-if move, the system SHALL remove the block's original hour and
  add the target hour, recompute from the cube, and return the same payload shape as
  `/audit`; when the block or target hour is outside the clinic's schedule it SHALL
  raise `AuditDataError`.

## API behaviour

- **RC-17** — While `CARELEAP_DATA=mock`, the system SHALL serve the labelled mock
  payload for `/audit` and `/whatif` (day stamped), unchanged from the H1 scaffold.
- **RC-18** — While `CARELEAP_DATA=real`, the system SHALL aggregate the real cube
  through `engine.audit`, loading and caching cube + origins once per process.
- **RC-19** — While in real mode, when `cube.parquet` or `origins.parquet` is missing,
  the system SHALL respond `503` and SHALL NOT fall back to mock data.
- **RC-20** — When `GET /audit` receives an unknown clinic, day or community in real
  mode, the system SHALL respond `404`.
- **RC-21** — When `POST /whatif` receives an unknown clinic in real mode, the system
  SHALL respond `404`; when the clinic exists but the block/hour is outside its
  schedule, the system SHALL respond `422`.
- **RC-22** — The system SHALL keep `get_audit_data` overridable via FastAPI
  `dependency_overrides` so tests can inject synthetic cube/origins frames.

## Provenance & safety

- **RC-23** — The system SHALL attach a source and vintage to every number it reports
  (logistics only, synthetic patients only, no secrets).
- **RC-24** — The system SHALL treat times as seconds since local midnight and SHALL NOT
  wrap a value ≥ 86400.
