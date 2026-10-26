# Kiro Journal — Sumedh (M1)

Per-person Kiro-usage log for Slot-to-Stop. Append only, newest at the bottom.
Write entries with: `python scripts/log_kiro.py --member sumedh --tool <IDE|CLI|Web|Crew> --topic <t> --what "..." [--kiro "..."] [--outcome "..."]`
Assemble the whole team's log with: `python scripts/log_kiro.py --assemble`

<!-- LOG ENTRIES BELOW — newest at the bottom -->

## 2026-10-24 15:33 · sumedh · Crew · topic: hooks
what: built the Kiro journal: 2 IDE hooks + scripts/log_kiro.py, logging to docs/kiro-journal.md
kiro: Crew authored the hook docs against the on-disk hook schema and a stdlib helper so Web/Crew work is logged too
outcome: helper verified; hooks travel via .kiro/ for teammates in the IDE

## 2026-10-24 15:33 · sumedh · Crew · topic: mcp
what: wired gtfs-mcp round_trip/plan_trip/validate_feed to the engine
kiro: one shared deterministic router every agent calls, on cached GTFS not a live API
outcome: imports clean, routes correctly

## 2026-10-24 15:33 · sumedh · Crew · topic: pbt
what: differential PBT: RAPTOR == CSA == brute-force oracle over 400 random feeds
kiro: the oracle caught two real router bugs (origin foot-transfers, CSA transfer-unlock) during bring-up
outcome: 3,200 agreeing queries; 250 tests green in 0.6s

## 2026-10-24 15:39 · sumedh · Crew · topic: other
what: added engine.latest_departure: reverse one-to-many profile search (backward RAPTOR) for M2's reachability cube
kiro: Crew built the symmetric backward search and a Hypothesis property proving it agrees with the forward earliest_arrival
outcome: 252 tests green; 626 reverse results verified vs forward oracle, 0 violations

## 2026-10-24 15:43 · sumedh · Crew · topic: hooks
what: made journaling work in Crew: always-on steering/journaling.md tells every agent to self-log via scripts/log_kiro.py
kiro: Crew has no file-save hook, so the steering rule (injected every session) makes the agent log its own work into per-person files
outcome: helper runs from any CWD; steering + per-person journal verified

## 2026-10-24 16:15 · sumedh · Crew · topic: pbt
what: golden PVTA trip on real feed exposed + fixed a transfer-limit bug (RAPTOR boarded from same-round stops, allowing >2 transfers)
kiro: ran round_trip on the live PVTA GTFS; the real network produced 4-6 bus journeys the synthetic feeds never did, revealing the bound was not per-round; fixed to read a frozen previous-round snapshot
outcome: 318 tests green; RAPTOR==CSA 0 disagreements on 120 real-feed queries; golden tests guard the regression

## 2026-10-24 16:27 · sumedh · Crew · topic: other
what: built M2's reachability cube (pipeline/build_cube.py) on real PVTA+ACS data; ran M2's build_origins/stops_walk to produce the caches
kiro: cube calls the engine's verified round_trip per cell (matches the oracle, 20/20); caught and discarded a profile-search shortcut that under-reported reachability 1.2% vs the true 31%
outcome: origins 506 bgs / 55,901 carless adults; 193 transit-desert bgs; cube 42,504 cells/clinic, 31% reachable to Baystate; cube==round_trip 20/20

## 2026-10-24 16:34 · sumedh · Crew · topic: other
what: Fixed reachability cube under-reporting (1.2% flat -> 31% varying by hour)
kiro: rebuilt pipeline/build_cube.py to call engine.round_trip per cell using block-group lat/lon instead of stop-membership join
outcome: Baystate GI cube: 7am 19% to noon 45% to 6pm 14%; cube==round_trip 60/60; 318 tests green

## 2026-10-24 17:20 · sumedh · Crew · topic: spec
what: M1 Phase A via 4 parallel Crew agents: real /audit+/whatif, schedule-optimizer + real reach-mcp, midnight PBT, web Audit screen (PR #7)
kiro: Crew split the work across 4 agents with separate files, using one shared engine/audit.py; every claimed file and test was re-checked by the parent before merging
outcome: pytest green, web build passes, CI green; squash-merged so a 6.5 MB data zip never entered main

## 2026-10-24 17:27 · sumedh · Crew · topic: spec
what: retroactive Bugfix spec bug-transfer-limit from the real PVTA counterexample (4107->1053: 4 out / 6 return buses, limit 3)
kiro: re-ran the pre-fix RAPTOR: a chain-feed Hypothesis property failed and shrank to n=4; pinned it as @example in tests/property/test_transfer_limit.py
outcome: property fails on pre-fix code, passes on fix; spec in .kiro/specs/bug-transfer-limit/

## 2026-10-24 18:02 · sumedh · Crew · topic: hooks
what: Phase B M1: UI properties + Playwright/axe, Suggest panel on GET /suggest, 8 new hooks, 3-job CI, power fresh-workspace test, experiments 3/4, Scorecard, Crew feed crons, Kiro Web issues #8-10
kiro: Crew ran 5 parallel worker agents on disjoint files; parent verified every file and re-ran all suites; axe hook found 2 serious a11y bugs, power test found the round_trip tool-name bug
outcome: 396 pytest + 20 vitest + 2 e2e + 2 axe green; uncommitted on sumedh

## 2026-10-24 19:04 · sumedh · Crew · topic: other
what: M2 handover: Makefile (data/test/test-full/snapshot/demo), 4-clinic cube merge incl. CHCFC Greenfield via FRTA (11.3% reachable), make data builds a cube per clinic_stops.csv row
kiro: reassigned from M2 (laptop crash); Makefile wires get_data -> pvta extract -> origins -> stops_walk -> bg_towns -> per-clinic cubes -> merge
outcome: cube.parquet 170,016 cells: Baystate 31.0%, Holyoke 33.4%, Mercy 41.5%, Greenfield 11.3%; snapshot data/snapshots/demo-v1 (45 MB) served by make demo via SLOT_TO_STOP_CACHE_DIR

## 2026-10-24 19:04 · sumedh · Crew · topic: hooks
what: hooks #1 (feed-expiry-on-session-start, IDE sessionStart UNVERIFIED + CLI agentSpawn verified) and #6 (engine-fast-tests-on-save, fileEdited engine/**) added; README hook table updated
kiro: CLI agentSpawn hook on slot-to-stop-dev runs check_data_fresh.py; IDE hook reuses the same script
outcome: 8 IDE .kiro.hook files + 5 CLI agent hooks; scripts unit-tested

## 2026-10-24 19:04 · sumedh · Crew · topic: spec
what: Rural lens end to end: pipeline/build_towns.py (TIGER COUSUB point-in-polygon, 506 bgs -> 65 towns, 2/279 mismatches vs MassGIS), engine/rural.py, GET /rural, map lens toggle + town filter + text summary, contracts.md section
kiro: spec-less but contract-first: shapes added to docs/contracts.md and pinned by tests/unit/test_rural_api.py before the UI
outcome: real data: 320 bgs transit, 86 assisted-only (3,270 car-less adults), 0 none, 100 not_assessed; 7 unit + 1 Hypothesis property; tsc + 20 vitest green

## 2026-10-24 19:04 · sumedh · Crew · topic: pbt
what: Differential test over the REAL PVTA feed (connection-scan task 6) found a bug in BOTH oracles: CSA and brute force kept one label per stop, which is wrong under a transfer cap (bi-criteria time x buses); RAPTOR was right. Fixed CSA with per-level labels, brute force to settle per (stop, buses, rode_bus)
kiro: Bugfix spec .kiro/specs/bug-csa-transfer-cap/ with minimal hand-built trap feed; regression test fails on pre-fix code (git stash check) and passes on the fix
outcome: RAPTOR == CSA on 40 real round trips + 3 full earliest-arrival maps (was 21 lost stops); synthetic differential, golden, transfer-limit, midnight suites green

## 2026-10-24 19:04 · sumedh · Crew · topic: spec
what: Reviewed M3 multi-feed engine/gtfs.py addition (task 8) and ticked raptor-router 10/11, connection-scan 6, reachability-cube multi-clinic/speedup/FRTA, multi-feed 7b
kiro: review notes recorded in the multi-feed tasks.md
outcome: multi-feed unit + property + golden green

## 2026-10-24 19:08 · sumedh · Crew · topic: power
what: Re-tested slot-to-stop power in a fresh workspace and published it as a public repo + v0.1.0 release
kiro: Crew ran stdio MCP initialize/tools/list/tools/call against the power's mcp.json, kiro-cli mcp list, then gh repo create + release
outcome: both servers list tools; validate_feed ok on PVTA; reachability returns cells; github.com/SSJ-07/slot-to-stop-power public

## 2026-10-24 19:10 · sumedh · Crew · topic: other
what: README Kiro Scorecard refreshed: oracle bug (bug-csa-transfer-cap) under differential testing, 11/11 hooks, 4-clinic cube, /rural contract, current counts (490 fast + 2 slow pytest, 20 vitest, 2 e2e, 2 axe, fresh-clone make data 5 min); mcp/README stale placeholder note fixed
outcome: write-up text only; no code changed

## 2026-10-24 19:43 · sumedh · Crew · topic: pbt
what: Demo bring-up found the planner always answered 'none' for Maria on real data: (1) colonoscopy slots only existed for BAY_GI_GREENFIELD, which has no stop anchor; (2) the UI's synthetic origin was not a real block group; (3) engine.round_trip returned the EARLIEST outbound (06:xx for a 16:30 visit), so the door-to-door window overlapped every shift
kiro: fixed in order: 66 labelled template slots for BAY_GI_SPRINGFIELD (demo anchor), Maria -> Holyoke bg 250138121032 (real + mocks), round_trip now returns the latest-departing outbound via the reverse profile; new property test_latest_outbound.py
outcome: Maria: escort-aware ride at 16:30 + ES prep sheet + PT-1 prefill on real PVTA data; fast suite + 11 e2e + axe green

## 2026-10-24 19:43 · sumedh · Crew · topic: other
what: Demo plumbing: CORS middleware (origins from SLOT_TO_STOP_WEB_ORIGINS), planner slot window [today, +14d] frozen by SLOT_TO_STOP_TODAY in make demo, PlanView shows top 3 options + show-more; merged #14 after fixing a count() race in Kevin's planner e2e
outcome: localhost demo: API :8000 real mode on the frozen snapshot, web :5173 via /api proxy

## 2026-10-24 20:30 · sumedh · Crew · topic: other
what: Demo polish: map was blank (glyphs: undefined rejected by MapLibre; worker URL under Vite; container unmounted on lens switch) - fixed all three; RT-8 provenance record added; planner options now carry per-option transit details (leave/arrive, routes, return, last bus, buses, door-to-door) and Holyoke OB/GYN template slots so prenatal shows 'Take the bus' options
outcome: headless screenshots: both map lenses draw; prenatal 12 distinct slot options with bus lines; Maria 12 rides with bus estimate; tsc, 20 vitest, 9 e2e, 2 axe green

## 2026-10-24 20:43 · sumedh · Crew · topic: other
what: Planner output fixes from demo review: identical weekday options collapsed into one choice with also_on dates (12 -> distinct trips); prep option now attaches the signed-off EN/ES prep sheet (signoff.json) with known tokens filled and the rest left blank; ride itinerary/phone view show appointment, check-in, visit end, escort rule; PT-1 shows field labels and the clinic name+address
outcome: Maria: 12 options -> 7 distinct, prep sheet attached (ES, reviewed); fast pytest, 20 vitest, 10 e2e+axe green

## 2026-10-24 20:50 · sumedh · Crew · topic: other
what: Renamed the product Slot-to-Stop -> CareLeap everywhere: UI title/strings, API title, docs, steering, specs, power (power/careleap), agent careleap-dev, env vars SLOT_TO_STOP_* -> CARELEAP_*, Python package careleap, crew script careleap_feed.py, FINAL-careleap.md
kiro: past journal entries left untouched (append-only rule); external power repo URL kept (GitHub rename is a manual step)
outcome: 534 pytest, 20 vitest, 10 e2e+axe green; API + web restarted under CARELEAP_* env
