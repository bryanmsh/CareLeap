---
name: gtfs-debugging
description: >-
  Diagnose why a transit round trip comes back unreachable and catch the
  classic GTFS traps (>24:00 times, service-calendar exceptions, transfer
  minimums, trip limits, missing access links), using the gtfs-mcp router.
  Logistics only; every number carries its source and vintage.
---

# Skill: gtfs-debugging

Diagnose why a transit round trip comes back unreachable, and catch the classic
GTFS feed traps before blaming the router.

## When to use

Use this skill when the user asks any of:

- "Why can't this patient get there?" / "This trip should be reachable."
- "Debug this GTFS feed" / "a reachability result looks wrong."
- A `clinic-access-audit` cell is unexpectedly unreachable and you need the cause.

## Tools (exact names and parameters)

All four live on **`gtfs-mcp`** (launched by this power's `mcp.json`; names verified
against `mcp/gtfs-mcp/server.py`). Times are **seconds since local midnight and may
exceed 86400** — a trip at 24:30:00 is `88200`, never wrapped to `1800`.

- `round_trip(origin, clinic, date, start, minutes)` →
  `{reachable, out_legs, ret_legs, last_bus_home, last_bus_home_hms, reason, sources}`.
  **Read `reason` first** — it names the failing direction. `origin`/`clinic` are a
  `stop_id` or `"lat,lon"`; `date` is ISO `YYYY-MM-DD`; `start`/`minutes` are ints.
- `plan_trip(origin, dest, date, depart_after=None, arrive_by=None)` →
  `{reachable, legs, reason, sources}`. Isolates **one leg/direction** so you can see
  which half of the round trip fails. Pass `arrive_by` for the outbound (arrive before
  the appointment) or `depart_after` for the return.
- `validate_feed()` → `{ok, service_date, n_stops, n_trips, n_stop_times,
  earliest_departure, latest_departure, crosses_midnight, sources}`. First call when a
  feed looks wrong — confirms the feed loaded and shows its service window.
- `service_changes(since)` → `{since, service_date, changes, note, sources}`. The
  in-memory feed is resolved to a single service date, so this reports no
  cross-version changes and says so honestly; use it to confirm the active date.

> Feed selection is deterministic and offline. If `GTFS_DIR` (and optionally
> `GTFS_DATE`) is set, the real PVTA feed is loaded; otherwise a small synthetic feed
> is used and every `sources` entry is labelled
> `synthetic GTFS (illustrative — not a finding)`. Never present synthetic numbers as
> findings.

## Checklist — the usual culprits

Walk these in order; most "impossible" unreachables are one of 1–5.

1. **Midnight / >24:00 times.** A trip departing `24:30:00` is `88200` seconds,
   never wrapped to `01800`. A return that "disappears" late at night is usually a
   `start`/`minutes` that pushed the return past midnight — check `last_bus_home_hms`.
2. **Service calendar.** The query `date`'s active `service_id`s come from
   `calendar.txt` **and** `calendar_dates.txt` (exception `1` adds, `2` removes). A
   holiday exception can remove all service. Confirm the date with `validate_feed()` /
   `service_changes(since)`.
3. **Transfer minimum.** A connection missed by seconds is usually `transfers.txt`
   `min_transfer_time` (or the engine default when absent). Look at the gap between
   `arr` of one leg and `dep` of the next in `out_legs` / `ret_legs`.
4. **Trip limits.** A leg is rejected for total journey > 2h, > 2 transfers, a walk leg
   > 800 m, or a return departing before 05:30. `reason` names which.
5. **Access links.** An origin/clinic with no stop within 800 m resolves to no
   boarding stop — the trip is unreachable *by construction*. `plan_trip` returns
   `"origin or dest resolves to no stop within walk limit"` for exactly this.

## Procedure

1. `validate_feed()` — confirm the feed loaded, note `service_date` and
   `crosses_midnight`, and check the date you are testing is inside the window.
2. `round_trip(...)` for the failing appointment — read `reason`. It tells you the
   failing direction (outbound vs return) and often the cause.
3. If `reason` is ambiguous, split the trip: `plan_trip(origin, clinic, date,
   arrive_by=start)` for the outbound and `plan_trip(clinic, origin, date,
   depart_after=start+minutes*60)` for the return. Whichever returns
   `reachable: false` is the broken half.
4. Match the symptom to the checklist above and fix the **data** (feed) or confirm it
   is a genuine service gap — not a router bug.

## Verifying a fix

Cross-check against the engine's oracles: it ships RAPTOR, CSA, and a brute-force
router that must agree. A divergence on a tiny feed is a **router** bug, not a data
bug. Re-run `round_trip` after any feed edit and confirm `reachable` flips with a
`reason` that matches the change you made.

## Guardrails

- **Logistics only.** Diagnosing a transit trip, never a clinical or eligibility
  statement.
- **Reachability ≠ attendance.** A reachable trip is a logistical upper bound, not a
  prediction of attendance.
- **Every number carries source + vintage.** Pass through each response's `sources`.
  Synthetic-feed numbers are labelled "illustrative" and are never findings.
- **Synthetic patients only; no live third-party routing APIs** — all routing is
  against the cached GTFS feed via the engine.

## Worked example

> User: "A patient at 42.204,-72.606 has a 45-min visit at the Holyoke clinic on Mon
> 2026-11-16 at 8am and the audit says it's unreachable. Why?"

1. Confirm the feed and date:

   ```
   validate_feed()
   → { "ok": true, "service_date": "2026-11-16", "crosses_midnight": true,
       "latest_departure": 89400, "sources": [{"name": "PVTA GTFS", "vintage": "2026-11-16"}] }
   ```

2. Reproduce the round trip (`start=28800` = 08:00, `minutes=45`):

   ```
   round_trip(origin="42.204,-72.606", clinic="holyoke",
                   date="2026-11-16", start=28800, minutes=45)
   → { "reachable": false,
       "reason": "return: no departure after visit end before last_bus_home",
       "out_legs": [ ...arrives 07:52... ],
       "ret_legs": [],
       "last_bus_home": 31500, "last_bus_home_hms": "08:45:00",
       "sources": [ {"name": "PVTA GTFS", "vintage": "2026-11-16"} ] }
   ```

   `reason` points at the **return**: the visit ends at 08:45 but the last bus home
   departs at 08:45 — the patient cannot board after the visit.

3. Isolate the return to confirm:

   ```
   plan_trip(origin="holyoke", dest="42.204,-72.606",
             date="2026-11-16", depart_after=31500)
   → { "reachable": false, "reason": "no journey found", ... }
   ```

   Confirmed: no return bus departs after 08:45. This is checklist item **#1/#4**
   (last-bus-home window), a genuine service gap — not a router bug. The fix is a
   schedule shift (hand off to `clinic-access-audit` `what_if` to find a better
   block), not a feed edit.
