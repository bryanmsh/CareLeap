---
name: clinic-access-audit
description: >-
  Audit which hours of a clinic's weekly schedule car-less adults in each
  community can actually reach AND return from by transit, using the
  reach-mcp reachability cube and the gtfs-mcp round-trip router. Produces a
  CHNA-ready, source-cited access report. Logistics only — never a clinical
  or eligibility statement.
---

# Skill: clinic-access-audit

Audit which hours of a clinic's weekly schedule car-less adults in each community
can actually reach **and return from** by transit, and quantify the equity gap.

## When to use

Use this skill when the user asks any of:

- "Who can reach this clinic by bus?"
- "Audit our schedule for access" / "which appointment hours strand car-less patients?"
- "Build a CHNA-ready access report for clinic X."
- "If we moved the Monday 8am block to 10am, who gains access?"

Do **not** use it to make clinical, eligibility, or attendance claims — see Guardrails.

## Tools (exact names and parameters)

Both servers are launched by this power's `mcp.json`. Tool names are exactly as the
servers register them (verified against `mcp/reach-mcp/server.py` and
`mcp/gtfs-mcp/server.py`).

**`reach-mcp`** — the authoritative aggregation path (reads the cached cube, never recomputes):

- `reachability(clinic, community, day)` → `{cells, equity, sources, server}`.
  One clinic × community × day slice of the reachability cube. Same shape as the
  API's `GET /audit`. `community="all"` aggregates every community.
- `what_if(clinic, block, to, community="all")` → same shape as `reachability`.
  Recomputes after moving a schedule block, e.g. `block="mon-08", to=10` moves the
  Monday 08:00 block to 10:00.
- `suggest_schedule(clinic, k=3, day="mon")` → up to `k` ranked changes, each
  `{change, gain_visit_hours, gain_people, sources}`, maximizing reachable EJ
  car-less visit-hours.

**`gtfs-mcp`** — the per-trip router, for drill-down and verification only:

- `round_trip_tool(origin, clinic, date, start, minutes)` → `{reachable, out_legs,
  ret_legs, last_bus_home, reason, sources}`. `origin`/`clinic` are a `stop_id` or
  `"lat,lon"`; `date` is ISO `YYYY-MM-DD`; `start`/`minutes` are integers (`start`
  in **seconds since local midnight**, may exceed 86400). This is the authoritative
  round-trip check the cube is built from — use it to spot-check a single cell, not
  to re-derive the audit. (The server's docstring calls this `round_trip`, but the
  live `tools/list` wire name is `round_trip_tool` — call it by the latter.)

> If `reachability` / `what_if` return `{"error": "...cube cache not found..."}`,
> the cube has not been built. Report that honestly and stop — do **not** fabricate
> numbers. Building it (`pipeline/build_cube.py`) is ~9 min/clinic and is out of
> scope for an audit run.

## Procedure

1. **Identify the clinic and its weekly blocks.** Get the `clinic_id` (or lat/lon)
   and the list of scheduled `(day, hour)` blocks you are auditing.
2. **Read reachability per community/day — never by hand.** For each day the clinic
   is open, call `reachability(clinic, community, day)`. Start with
   `community="all"` for the headline, then per community for the equity breakdown.
   The engine's `round_trip` is already baked into the cube; do not re-route it.
3. **Report the reachable share of car-less adults** per `(day, hour)`, plus the
   equity breakdown returned in `equity` (e.g. EJ, limited-English, 65+,
   zero-vehicle). Attach every `sources` entry — each number carries its source
   and vintage.
4. **Flag the strand hours** — blocks whose reachable share falls below your
   threshold, especially for EJ / zero-vehicle communities.
5. **Test a fix.** Call `what_if(clinic, block, to)` for a candidate shift (e.g.
   `block="mon-08", to=10`) and compare the reachable share before/after. Report the
   **realised** gain from the payload, never a hard-coded number. Or call
   `suggest_schedule(clinic, k, day)` to let the optimizer rank changes.
6. **(Optional) Drill into one cell.** To explain *why* a specific slot is
   unreachable for a specific origin, call `gtfs-mcp round_trip_tool(origin, clinic,
   date, start, minutes)` and read `reason` / `last_bus_home`.

## Guardrails

- **Logistics only.** This is a transit-reachability audit, never a clinical,
  eligibility, or medical statement, and never advice about who *should* attend.
- **Reachability ≠ attendance.** "Can reach by bus" is an upper bound on logistical
  access, not a prediction that anyone will attend. Say so in the report.
- **Every number carries source + vintage.** Pass through the `sources` array from
  every tool response. If a response's source is labelled
  `synthetic GTFS (illustrative — not a finding)` (the fallback feed when `GTFS_DIR`
  is unset), you MUST label those numbers "illustrative" and must not present them
  as findings.
- **Synthetic patients only.** Origins are block-group aggregates / synthetic
  cohorts — never real patient records.
- **No live third-party routing APIs.** All routing is against the cached GTFS feed
  via the engine. Do not substitute a web maps API.

## Worked example

> User: "Audit the Holyoke clinic's Monday schedule for car-less access, and tell me
> if moving the 8am block to 10am helps."

1. Headline, Monday, all communities:

   ```
   reachability(clinic="holyoke", community="all", day="mon")
   → { "cells": [ {"hour": 8,  "reachable_share": 0.31, ...},
                  {"hour": 10, "reachable_share": 0.58, ...},
                  {"hour": 14, "reachable_share": 0.62, ...} ],
       "equity": { "ej": {"hour8": 0.19, ...}, "zero_vehicle": {...} },
       "sources": [ {"name": "PVTA GTFS", "vintage": "2026-11-12", ...},
                    {"name": "ACS 2022 5-yr", ...} ],
       "server": "reach-mcp" }
   ```

   Read-out: at 08:00 only **31%** of car-less adults can reach-and-return; the EJ
   community is worst at **19%**. 10:00 and 14:00 are far better.

2. Test the proposed fix:

   ```
   what_if(clinic="holyoke", block="mon-08", to=10)
   → cells show the 08:00 demand re-slotted to 10:00 at reachable_share ≈ 0.58
   ```

   Report the **realised** gain from this payload (e.g. "+27 pts reachable share
   for that block, ~N car-less adults gained"), citing its `sources`.

3. Spot-check one hard cell with the router:

   ```
   round_trip_tool(origin="42.204,-72.606", clinic="holyoke",
                   date="2026-11-16", start=28800, minutes=45)
   → { "reachable": false, "reason": "no return before last_bus_home", ... }
   ```

   Explains *why* 08:00 strands this origin: the visit ends after the last bus home.

4. Deliver the report: table of `(day, hour) → reachable share` with the equity
   breakdown, the strand hours flagged, the `what_if` gain, and a sources/vintage
   footnote. Numbers from a synthetic feed are labelled "illustrative".
