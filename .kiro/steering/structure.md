---
inclusion: always
---

# Structure — repo layout and module boundaries

```
careleap/
├── .kiro/          steering, specs, hooks, agents, skills, settings/mcp.json (COMMITTED)
├── AGENTS.md       always-on agent rules
├── engine/         GTFS ingest, RAPTOR/rRAPTOR, CSA, brute force, reachability cube, optimizer
├── planner/        visit_rules.yaml, barrier check, constraint solver, itinerary, templates/
├── api/            FastAPI (routers: audit, whatif, plan, provenance)
├── web/            React app (routes /audit, /planner, /about)
├── mcp/            gtfs-mcp, reach-mcp, access-resources-mcp
├── power/careleap/   publishable Kiro power
├── pipeline/       build_origins.py, stops_walk.py
├── scripts/        get_data.py
├── data/           raw/ + cache/ (git-ignored) + fixtures/ + manual/ (committed)
├── tests/          unit, property, differential, golden
├── docs/           contracts.md, kiro-journal.md, traceability.md, methods.md, decisions/
└── .github/workflows/   kiro-ci.yml, pbt.yml, data-refresh.yml
```

## Module boundaries
- `engine/` exposes `round_trip(...)` and the cube builder. It does **not** import from
  `api/` or `web/`.
- `pipeline/` writes the Parquet caches consumed by `engine/` and the API.
- `api/` depends on `engine/` and `planner/`, never the reverse.
- `mcp/` servers wrap engine/planner functions; they are thin adapters.

## The contracts
The fixed file and API shapes between the four workstreams are defined here:

#[[file:docs/contracts.md]]

Respect those shapes. A change to a shape must update the contract tests in the same PR
and be announced to the whole team.
