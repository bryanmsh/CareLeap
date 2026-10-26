# CareLeap: Reachable Care

> We show western Massachusetts health systems **which of their own appointments their
> patients physically can't get to**, and then plan the high-stakes visits so they
> actually happen.

Hackachusetts 2026 · Healthcare & Biotech · Challenge 3 ("A referral is not a finished visit")

## Two modes, one routing engine

- **Clinic Audit** — for every clinic hour in a weekly schedule, compute what share of
  car-less adults in each neighborhood can get there *and back* by bus. Drag a clinic
  block or add a satellite day to see the fix.
- **Visit Planner** — for high-stakes visits (colonoscopy after a positive FIT, prenatal,
  dialysis, chemo), run a barrier check and build a plan that can actually happen.

## Repo layout

```
careleap/
├── .kiro/          Kiro steering, specs, hooks, agents, skills, MCP config (COMMITTED)
├── AGENTS.md       Always-on agent rules
├── engine/         GTFS ingest, RAPTOR, CSA, brute force, reachability cube, optimizer
├── planner/        Visit rules, barrier check, constraint solver, itinerary
├── api/            FastAPI app
├── web/            React app
├── mcp/            gtfs-mcp, reach-mcp, access-resources-mcp
├── power/          Publishable Kiro power
├── data/           raw/ + cache/ (git-ignored) + fixtures/ (committed)
├── tests/          unit, property, differential, golden trips
├── docs/           kiro-journal, traceability, methods, decisions, contracts
└── .github/        CI workflows
```

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
make install        # pip install -e ".[dev,pipeline]"
cp .env.example .env    # add CENSUS_API_KEY (free: api.census.gov/data/key_signup.html)

make data           # download raw sources (~35 MB) + build every cache:
                    #   origins -> stops_walk -> bg_towns -> one cube per clinic in
                    #   data/manual/clinic_stops.csv (~5 min each, parallel) -> merge
make test           # fast suite: unit + property + golden + contract (CI runs this)
make test-full      # + slow differential (real-feed RAPTOR == CSA) + full Hypothesis

CARELEAP_DATA=real make api   # API on :8000 against data/cache
make web            # Vite dev server on :5173 (cd web && npm install first)
make dev            # both

make snapshot       # freeze data/cache -> data/snapshots/demo-v1/
make demo           # serve the API (real mode) on that frozen snapshot
```

Without `make data` the API runs in **mock** mode (labelled mocks in `api/mocks/`);
`/suggest` and `/rural` then answer "needs real data" instead of inventing numbers.

## Guardrails

- **Logistics only.** No clinical or eligibility decisions.
- **Synthetic patients only.** No real PHI.
- **Every number carries a source and vintage.** Template values are labelled "illustrative".
- **`.kiro/` is committed, never git-ignored.**

## Kiro Scorecard

What each Kiro feature is, where it lives, and the concrete thing it caught or saved.
Test counts are current as of 2026-10-24 (evening) — `make test` → **490 passed** (fast
suite), `make test-full` adds 2 slow real-feed differential tests (**492**); `cd web && npx
vitest run` → **20 passed** (5 files), Playwright e2e 2 + axe 2. A fresh copy of the tree
ran `make install && make data && make test` clean (`make data` = 5 min, 4 clinics). Every
number below is one we can reproduce in this repo.

| Kiro feature | Where in repo | What it caught or saved (concrete) |
|---|---|---|
| **Steering** | `.kiro/steering/*.md`, `AGENTS.md` | 11 always-on/scoped rules. `gtfs-domain.md` pins the midnight no-wrap rule (`24:30:00`→`88200`); `accessibility.md` drives the "no colour-only cells" web test; `tech.md` the provenance rule. Steering on/off writeup: [ADR 003](docs/decisions/003-experiment-3-steering-on-off.md). |
| **Specs — `raptor-router`** | `.kiro/specs/raptor-router/` | Authoritative router spec; RAPTOR shipped as the production path. |
| **Specs — `connection-scan`** | `.kiro/specs/connection-scan/` | Second-implementation (CSA) spec; the structural "second opinion" in the differential tests. |
| **Specs — `reachability-cube`** (Design-First) | `.kiro/specs/reachability-cube/` | 24 `RC-` reqs, 12/12 tasks (multi-clinic, parallel build, FRTA closed 2026-10-24). Documented + guarded the discarded profile-search shortcut (**1.2% flat vs true 31%** reachability). Cube now covers 4 clinics incl. CHCFC Greenfield over the merged PVTA+FRTA feed (11.3% reachable — the rural gap, measured). |
| **Specs — `schedule-optimizer`** (Requirements-First) | `.kiro/specs/schedule-optimizer/` | 16 `SO-` reqs, 9/9 tasks done; CELF greedy + CP-SAT oracle. 9 of 16 `SO-` ids cited directly in test code. |
| **Specs — `visit-planner`** | `.kiro/specs/visit-planner/` | Barrier-check + constraint-solver spec for high-stakes visits. |
| **Specs — `manual-data`** | `.kiro/specs/manual-data/` | Manual/synthetic data sourcing spec (provenance + vintage per number). |
| **Specs — `ui-week-grid`** | `.kiro/specs/ui-week-grid/` | Audit week-grid UI spec (drives the `web/` Audit screen). |
| **Specs — `bug-transfer-limit`** (Bugfix) | `.kiro/specs/bug-transfer-limit/` | Retroactive bugfix spec from the real PVTA counterexample (trip `4107`→`1053`: 4 out / 6 return buses, limit 3). |
| **Specs — `bug-csa-transfer-cap`** (Bugfix) | `.kiro/specs/bug-csa-transfer-cap/` | **Both test oracles were wrong.** Running the differential over the *real* feed (connection-scan task 6) showed CSA losing **21 stops** RAPTOR reached. Root cause: CSA *and* brute force kept one label per stop — invalid once transfers are capped (time × buses is bi-criteria). RAPTOR was right. Fixed CSA with per-level labels and brute force to settle per (stop, buses) state; minimal 5-stop trap feed pinned in `tests/property/test_csa_transfer_cap.py`, shown failing on pre-fix code and passing on the fix. |
| **Specs — `multi-feed`** | `.kiro/specs/multi-feed/` | PVTA + FRTA in one `Timetable` (agency-prefixed ids, per-feed calendars, ≤400 m cross-agency walks); 9/9 tasks incl. M1 review; golden FRTA Route 32 trip. |
| **Property-based tests** | `tests/property/` (36 tests) | `test_midnight.py` defends the ≥86400 no-wrap invariant; `test_transfer_limit.py` pins the shrunk `n=4` counterexample as `@example`; optimizer props assert never-worse + greedy ≥ (1−1/e)·CP-SAT. |
| **Differential tests** | `tests/differential/` (242 cases: 240 synthetic + 2 real-feed) | RAPTOR == CSA == brute-force oracle over **120 random feeds × 2** (reachability + earliest-arrival), **0 disagreements**. Caught 2 router bugs during bring-up (origin foot-transfers; CSA transfer-unlock). Then the **real-feed** run (`test_real_feed_agree.py`: 40 random PVTA round trips + 3 full earliest-arrival maps) caught the **oracle bug** above — two agreeing oracles were both wrong, and only the real network had the trap shape (long-first, short-later arrival at a hub). Lesson for the write-up: a differential test is only as strong as its inputs. Now **0 disagreements** on the real feed too. |
| **Golden trips** | `tests/golden/` (4 tests: 3 PVTA + 1 FRTA) | Real PVTA feed caught the **transfer-limit bug** the synthetic feeds never produced (RAPTOR boarded from same-round stops → >2 transfers). FRTA Route 32 golden trip pins the multi-feed loader. |
| **Contract tests** | `tests/contract/` (19 tests) + `tests/unit/test_rural_api.py` (7) | API shape + real-cube contract (hourly share not flat: 7am 19% → noon 45% → 6pm 14%). `/rural` contract pinned before the UI: verdict rule as a Hypothesis property; real data = 320 block groups transit-reachable, **86 assisted-only (3,270 car-less adults)**, 0 with nothing, 100 outside the rural table. |
| **Custom agents** | `.kiro/agents/*.json` | `router-dev`, `careleap-dev`, `audit-runner`, `content-reviewer`, `release-checker` — scoped tool/permission profiles + agent hooks. |
| **MCP servers** | `mcp/`, `.kiro/settings/mcp.json` | `gtfs-mcp` — **wired to real engine** (`round_trip`, `Timetable`). `reach-mcp` — **wired to real engine** (`engine.audit` + `engine.optimizer`, `suggest_schedule`). `access-resources-mcp` — **wired to the manual data** (`rural_options`, `pt1_prefill`, `visit_rules` + the rural table as a resource; M3). No stubs remain. |
| **Hooks** | `.kiro/hooks/` (IDE) + `.kiro/agents/careleap-dev.json` (CLI) — see [`.kiro/hooks/README.md`](.kiro/hooks/README.md) | **11 of 11 planned.** CLI (agent `careleap-dev`): #1 feed-freshness on `agentSpawn`, #2 template reminder, #3 block template writes without sign-off, #4 block live routing APIs (exit 2 → "use gtfs-mcp"), #5 provenance log. IDE (8 `.kiro.hook` files): #1 session-start feed expiry, #6 fast router suite on `engine/**` save, #7 axe on `web/**` save, #8 GTFS validate, #9 data freshness, #10 traceability, #11 two journal hooks. 35 script tests. File hooks fire only on agent edits, so CI repeats the checks. |
| **CI** | `.github/workflows/kiro-ci.yml` ([docs/ci.md](docs/ci.md)) | Jobs `test` (pytest + `kiro-cli agent validate`), `web` (tsc, vitest, Playwright e2e, axe), `release-gate` (headless `kiro-cli chat --no-interactive --agent release-checker`). The gate self-skips: kiro-cli 2.34.0 has no non-interactive login yet. Squash-merge kept a 6.5 MB data zip out of `main` (PR #7). |
| **Power** | `power/careleap/` | `plugin.json`, `mcp.json` (gtfs-mcp + reach-mcp via `CARELEAP_HOME`), 2 skills. Installed into a fresh empty workspace and driven over MCP stdio: `tools/list` + a real `round_trip` call passed. Found a real bug: the tool was exposed as `round_trip_tool`, not the contract name `round_trip` — fixed. Not yet published. |
| **Crew** | `ops/crew/`, `docs/kiro-journal/` | Ran Phase A and Phase B as parallel agents on disjoint files (every claimed file/test re-checked). Two no-LLM script crons live: PVTA feed heartbeat every 6 h (ETag/Last-Modified diff → Slack) and a 14-day feed-expiry alarm. Slack alert pending Slack hookup. |
| **Kiro Web** | GitHub issues [#8](https://github.com/SSJ-07/hackachusetts/issues/8), [#9](https://github.com/SSJ-07/hackachusetts/issues/9), [#10](https://github.com/SSJ-07/hackachusetts/issues/10) | Issues opened for Kiro Web Autonomous (i18n, phone itinerary, QR card). PRs not yet opened — experiment ⑤. |

### Experiments ①–⑤

| # | Experiment | Status | Writeup |
|---|---|---|---|
| ① | Differential oracle (RAPTOR vs CSA vs brute force) | **done** — 240 synthetic cases + real-feed run; caught 2 router bugs, then **a bug in both oracles** (`bug-csa-transfer-cap`) | [ADR 001](docs/decisions/001-raptor-vs-csa.md) |
| ② | Spec-driven vs vibe coding (UI legend vs grid) | **pending** — protocol + exact metrics fixed | [ADR 004](docs/decisions/004-experiment-2-spec-vs-vibe.md) |
| ③ | Steering ON vs OFF (`gtfs-domain.md`) | **done (single-sample, 1 confound)** — ON wrote & passed 12/12; OFF write-denied, its *proposed* code also passed 12/12 | [ADR 003](docs/decisions/003-experiment-3-steering-on-off.md) |
| ④ | Requirements-First vs Design-First specs | **done (single-sample)** — req-first stronger on req→test traceability (9/16 vs 0/24 cited in tests) | [ADR 002](docs/decisions/002-experiment-4-req-first-vs-design-first.md) |
| ⑤ | Kiro IDE vs Kiro Web Autonomous | **pending** — protocol + exact metrics fixed | [ADR 005](docs/decisions/005-experiment-5-ide-vs-web-autonomous.md) |
