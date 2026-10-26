# plan.md: CareLeap: Reachable Care, build plan for a 4-person team

> Companion to `FINAL-careleap.md` (the *what* and *why*). This file is the *who does what, when*, including what to type into Kiro.
> **Assumed length: ~30 hours.** If your hackathon is shorter, keep the order and compress the hours. Cut lines are in §9.
> **Backend first.** There's no dedicated frontend or video person yet. The UI starts at **H14** and is shared (§4, Phase B). The video starts at **H24**.

---

## 0. Team roles

| Who | Role | Owns |
|---|---|---|
| **M1** | **Kiro architect + routing engine** | `.kiro/` (steering, specs, hooks, agents, MCP config), **RAPTOR router + PBT + differential tests**, `gtfs-mcp`, CLI CI, Crew, the published power, the Kiro write-up |
| **M2** | **Data + Audit engine** | **Download scripts**, data cleaning, block-group origins, **reachability cube**, what-if, **optimizer**, `reach-mcp`, `/audit` + `/whatif` API |
| **M3** | **Research + content** | **All manual data** (clinic hours, rural table, PT-1 fields, barrier questions, visit rulebook, EN/ES templates), fact-checking stats, the text description. Later: captions + video |
| **M4** | **Visit Planner + API + integration** | **Visit Planner solver**, `access-resources-mcp`, `/plan` + `/provenance` API, end-to-end tests, the FastAPI app skeleton. Later: **leads the UI** |

**Everyone** uses Kiro for their own code. Each person commits their specs/steering/hooks into `.kiro/`, never git-ignored.

---

## 1. Ground rules (read once, at hour 0)

1. **One repo, `main` is protected.** Work on `feat/<area>` branches and merge via PR. CI (Kiro CLI + tests) must pass.
2. **Contracts first.** At hour 1 we fix the file formats and API shapes between parts (§3). After that, everyone works in parallel with fake data until the real data lands.
3. **Commit `.kiro/` constantly.** Judges grade what's in it.
4. **Never hard-code a number.** Every number comes from the engine, carries a source and date, and is labelled "illustrative" if it comes from a template.
5. **Synthetic patients only.** No real PHI anywhere.
6. **Sync points** (10 minutes, standing): **H1, H6, H12, H18, H24, H28.**

---

## 2. What to download vs. what to build by hand

### 2a. Automatic downloads: **M2 writes `scripts/get_data.py`** (M1 reviews)
| # | Dataset | Exact source | Save to |
|---|---|---|---|
| 1 | **PVTA GTFS** ⭐ | `https://www.pvta.com/g_trans/google_transit.zip` (backup: MobilityDatabase `mdb-2416`) | `data/raw/pvta_gtfs.zip` |
| 2 | **Portal healthcare kit** (EJ, hospitals, CMS ratings, county PLACES) | `https://hackachusetts2026.vercel.app/kits/tracks/healthcare.zip` | `data/raw/portal_healthcare/` |
| 3 | **ACS car-less households** | Census API, ACS 5-yr: **B25044** (tenure × vehicles), **B01003** (population), **B01001** (age), **C16002** (limited-English households). **Block group** level for **Hampden (013), Hampshire (015), Franklin (011)**, optionally Berkshire (003); state 25. Needs a free API key | `data/raw/acs_bg.csv` |
| 4 | **TIGER block-group shapes** | `https://www2.census.gov/geo/tiger/TIGER2024/BG/tl_2024_25_bg.zip` | `data/raw/tiger_bg/` |
| 5 | **CDC PLACES, tract** (colorectal screening) | `https://data.cdc.gov/resource/yjkw-uj5s.json?stateabbr=MA`, column `colon_screen_crudeprev` (verified to exist) | `data/raw/places_tract.json` |
| 6 | **CMS dialysis facilities** | data.cms.gov Provider Data Catalog → "Dialysis Facility – Listing by Facility" (look up the dataset ID in the catalog; filter `state=MA`) | `data/raw/cms_dialysis.csv` |
| 7 | **NPPES specialists** | `https://npiregistry.cms.hhs.gov/api/?version=2.1&taxonomy_description=Gastroenterology&city=SPRINGFIELD&state=MA&limit=200`. Repeat for OB/GYN, oncology and nephrology, and for Springfield, Holyoke, Northampton, Amherst and Greenfield. `state` alone is rejected; max 200 rows per call | `data/raw/nppes_*.json` |
| 8 | **OSM walk network** | `https://download.geofabrik.de/north-america/us/massachusetts-latest.osm.pbf` (~311 MB). The MVP can skip this and use straight-line × 1.3 | `data/raw/ma.osm.pbf` |

The script must:
- be **idempotent** (skip files it already has)
- write `data/raw/manifest.json` (URL, date, sha256)
- **validate** each file (row counts, required columns)

### 2b. Manual work: **M3 owns all of it** (cite every row)
| # | Item | How | Output |
|---|---|---|---|
| 9 | **Clinic schedules** | Copy posted hours from 10–20 clinic web pages (Baystate GI/endoscopy, Baystate OB, Holyoke Medical Center, Cooley Dickinson, Mercy Medical Center, dialysis centers, infusion centers). If hours aren't posted, write a **labelled template** | `data/manual/clinic_schedules.csv`: `clinic_id, name, lat, lon, visit_type, day, start, end, visit_minutes, source_url, is_template` |
| 10 | **Rural options table** | For each Franklin and Hampshire town: dial-a-ride (FRTA demand response), Council on Aging volunteer drivers, PT-1, or none. Check websites or phone | `data/manual/rural_options.csv`: `town, dial_a_ride, coa_driver, pt1, hours, source_url, verified_by, date` |
| 11 | **PT-1 form fields** | Read the MassHealth PT-1 form on mass.gov and list every field | `data/manual/pt1_fields.json` |
| 12 | **Barrier questions** | 6 questions based on the **CMS AHC HRSN** tool and **PRAPARE** (transport, work shift, childcare, escort, cost, language/worry) | `data/manual/barrier_questions.yaml` (EN + ES) |
| 13 | **Visit rulebook** | Colonoscopy (sedated, escort, prep), prenatal, dialysis (3×/week, ~4h), chemo/infusion: duration, escort?, telehealth-OK?, prep sheet | `planner/visit_rules.yaml` |
| 14 | **Patient templates EN/ES** | Itinerary + prep sheet at a grade-6 reading level, signed off by a human reviewer | `planner/templates/{en,es}/*.md` + `signoff.json` |
| 15 | **Fact-check list** | Verify the "(verify)" stats in `FINAL-careleap.md`: FIT follow-up rate, escort rule, Baystate CHNA transport mention, dialysis shift fields | `docs/sources.md` |
| 16 | *(Stretch)* **FRTA mini-GTFS** | Hand-encode 1–2 FRTA routes from their PDF timetables | `data/manual/frta_minigtfs/` |

---

## 3. The contracts (fixed at H1)

M1 writes these in `docs/contracts.md`. Kiro steering `structure.md` references it with `#[[file:docs/contracts.md]]`.

| File / API | Producer → Consumer | Shape |
|---|---|---|
| `data/cache/origins.parquet` | M2 → M1, M2 | `bg_geoid, lat, lon, carless_adults, pop, ej_flag, lep_pct, age65_pct` |
| `data/cache/stops_walk.parquet` | M2 → M1 | `bg_geoid, stop_id, walk_min` |
| `engine.round_trip(origin, clinic, date, start, minutes) → {reachable, out_legs[], ret_legs[], last_bus_home, reason}` | M1 → M2, M4 | Python function + `gtfs-mcp` tool |
| `data/cache/cube.parquet` | M2 → UI | `clinic_id, visit_type, day, hour, bg_geoid, reachable(bool), reason` |
| `GET /audit?clinic&community&day` | M2 → UI | `{cells:[{day,hour,share,n,reached}], equity:{...}, sources:[...]}` |
| `POST /whatif {clinic, shift:{block, to}}` | M2 → UI | Same shape as `/audit` |
| `POST /plan {patient, visit_type, barriers}` | M4 → UI | `{options:[{kind:slot|ride|tele|prep|none, details, why}], itinerary, pt1_prefill}` |
| `GET /provenance?id` | M4 (with M1) → UI | `{source, vintage, requirement_id, properties:[{name,status}], spec_link}` |

Until the UI exists, **every API is tested with Playwright/pytest against these shapes**. M4 owns the contract tests.

---

## 4. Hour-by-hour plan

Legend: **K:** = what to do *in Kiro*.

## Phase A: Backend (H0 → H14)

### H0–0.5 · Kickoff (everyone together)
| Who | Tasks |
|---|---|
| **All** | Read `FINAL-careleap.md` §0 and §15. Agree on the demo path: **Baystate GI × Holyoke × Maria**. Confirm the roles. |
| **M1** | Create the GitHub repo + folder skeleton (final doc §7.1). Protect `main`. Invite everyone. |
| **M2** | Get a Census API key. Start the big downloads first: PVTA zip, TIGER, Geofabrik. |
| **M3** | Open a shared sheet for clinic hours and the rural table. Start Baystate GI + OB hours. |
| **M4** | Read the PT-1 form and the AHC/PRAPARE tools to understand the planner inputs. Sketch the Visit Planner decision flow on paper. |

### H0.5–1 · Kiro foundations (M1 leads)
| Who | Tasks |
|---|---|
| **M1** | **K:** Open the repo in the Kiro IDE.<br>**Steering:** generate the foundation docs (product / tech / structure) and add the guardrails ("logistics only", "every number has a source", "synthetic patients only"). Add `AGENTS.md`. Add the fileMatch steering `gtfs-domain.md` (`engine/**`) and `equity-and-language.md` (templates), the auto steering `visit-rules.md` and `optimizer-notes.md`, and the manual steering `demo-script.md`.<br>**MCP:** create `.kiro/settings/mcp.json` with GitHub + Playwright + AWS Docs, plus stubs for `gtfs-mcp`, `reach-mcp` and `access-resources-mcp`. |
| **M2** | **K** (vibe mode is fine for scripts): *"Write `scripts/get_data.py` that downloads the datasets in plan.md §2a, is idempotent, writes `data/raw/manifest.json` with URL, date and sha256, and validates row counts and columns."* Run it. |
| **M3** | Keep collecting clinic hours. Draft `barrier_questions.yaml`. |
| **M4** | **K:** *"Scaffold a FastAPI app in `api/` with routers audit, whatif, plan, provenance returning mock data that matches docs/contracts.md; add pytest contract tests."* |

### H1 · ✅ Sync #1 (10 min)
M1 presents `docs/contracts.md` (§3). Everyone confirms their inputs and outputs.

### H1–3 · Specs + data landing
| Who | Tasks |
|---|---|
| **M1** | **K: Spec 1 `raptor-router`** (Feature spec, **Requirements-First**). Prompt: *"Round-trip transit router over GTFS. Given origin stop set with walk minutes, clinic stop set, service date, appointment start and duration: return whether an outbound arrives ≤ start−10min and a same-day return departs ≥ start+duration; return legs and last bus home. Handle GTFS times >24:00, calendar_dates exceptions, min transfer time, ≤2 transfers, ≤2h each way."* Review the EARS requirements. Run **Analyze Requirements** and fix any gaps. Approve design → tasks. |
| **M2** | Finish the downloads. **K:** *"Write `pipeline/build_origins.py`: join ACS B25044 + B01003 + B01001 + C16002 to TIGER block groups for Hampden/Hampshire/Franklin; compute car-less adults; add MassGIS EJ flags and limited-English %; output `data/cache/origins.parquet` per contracts.md."* |
| **M3** | Finish 10+ clinic rows with source URLs. Start `rural_options.csv` (Franklin County towns first). Draft `visit_rules.yaml`. |
| **M4** | **K: Spec `visit-planner`** (Requirements-First): escort rule, shift rule, telehealth rule, the option ranking, the "no viable option" path. Use `visit_rules.yaml` (M3's draft) as the input format. |

### H3–6 · Engine v1 + planner v1
| Who | Tasks |
|---|---|
| **M1** | **K: Run all tasks** for `raptor-router`. Watch the waves; step in on GTFS edge cases. **Turn on PBT**: approve the properties Kiro proposes. Make sure you get **causality, FIFO, transfer-min, Pareto, round-trip soundness, midnight safety**. Write the **brute-force router** (tiny networks) as an oracle. **K: hook #6** (File Save `engine/**` → fast Hypothesis suite + golden trips). |
| **M2** | **K:** *"Write `pipeline/stops_walk.py`: for each block-group origin, nearest PVTA stops within 800 m; walk minutes = straight-line × 1.3 / 80 m per min."* Run the MobilityData GTFS validator and save the report. |
| **M3** | Finish `visit_rules.yaml` v1 and `pt1_fields.json`. Draft the EN templates (itinerary, colonoscopy prep sheet). |
| **M4** | **K: Run all tasks** for `visit-planner`. Approve the planner properties: **escort ⇒ never transit-only**, **no slot overlaps the shift (incl. travel)**, **telehealth only if allowed**, **no clinical/eligibility text**. Build `access-resources-mcp` (tools `rural_options`, `pt1_prefill`, `visit_rules`). |

### H6 · ✅ Sync #2
Checkpoint: the **router answers one real Holyoke → Baystate round trip**. M1 hand-checks it against the PVTA timetable, and it becomes **golden trip #1**. M4 shows Maria's plan, using a stubbed router.

### H6–9 · Differential testing + cube
| Who | Tasks |
|---|---|
| **M1** | **K: Spec 2 `connection-scan`** (second router, Quick Spec). Add the **differential properties**: RAPTOR == CSA on random queries over real PVTA, and RAPTOR == brute force on random tiny GTFS networks. Use **checkpoints** to compare the approaches. Write `docs/decisions/001-raptor-vs-csa.md`. Build `gtfs-mcp` (tools `plan_trip`, `round_trip`, `service_changes`, `validate_feed`; **resource:** feed metadata; **prompt:** `explain_trip`). |
| **M2** | **K: Spec `reachability-cube`** (**Design-First**). Implement it with **rRAPTOR** (range queries) through M1's engine API. Output `cube.parquet` for Baystate GI first. Target: under 5 s per clinic once cached. |
| **M3** | More clinic rows (dialysis, infusion). Continue the rural table. Start fact-checking (`docs/sources.md`). |
| **M4** | Swap the planner's stubbed router for M1's real `round_trip`. Wire the `/plan` endpoint. **Maria end-to-end**: colonoscopy → escort needed → slot after her shift → PT-1 pre-fill → prep sheet. |

### H9–12 · API + what-if + optimizer
| Who | Tasks |
|---|---|
| **M1** | Find the **midnight bug** on purpose. Seed PBT with `24:30:00` return trips. When a property fails and shrinks, **K: create a Bugfix spec from the counterexample**, and **screen-record it for the video**. Fix → green. **K: hook #5** (Post Tool Use `@gtfs-mcp` → append to `docs/provenance.jsonl`). **K: hook #11** (Agent Stop → append to `docs/kiro-journal.md`). |
| **M2** | `/audit` + `/whatif` on real data. **K: Spec `schedule-optimizer`** (Requirements-First): greedy with lazy evaluation + **OR-Tools CP-SAT** check on tiny cases. Properties: never worse than baseline, respects clinic hours, monotone in access. |
| **M3** | ES templates + get a human reviewer to sign `signoff.json`. **K:** run the `content-reviewer` agent on the templates once M1 creates it (H12+). |
| **M4** | `/provenance` endpoint. It reads `docs/traceability.md` + `docs/provenance.jsonl` and returns source → requirement → properties → status. Contract tests for all 4 endpoints. |

### H12 · ✅ Sync #3: "backend loop works"
Through the API only: Baystate GI × Holyoke grid → drag 8am → 10am via `/whatif` → the numbers change. Maria's `/plan` returns the escort plan. **Freeze the demo data snapshot** (`data/snapshots/demo-v1/`).

### H12–14 · Kiro Web + CLI
| Who | Tasks |
|---|---|
| **M1** | **Kiro Web:** connect the repo at app.kiro.dev and enable **Config Sync**. Set a **Schedule** job: a weekly GTFS refresh PR. **Kiro CLI:** create custom agents in `.kiro/agents/`: `router-dev` (writes `engine/**` only, no network), `content-reviewer` (read-only), `audit-runner`, `release-checker`. Add `.github/workflows/kiro-ci.yml`: headless Kiro CLI runs `release-checker` + PBT/golden suites on every PR. Check the exact CLI flags with `kiro-cli --help` first. |
| **M2** | `reach-mcp` (tools `reachability`, `what_if`, `suggest_schedule`; **resource:** cached cubes; **elicitation:** asks for visit duration if missing). **K (CLI):** parallel sub-agents with `audit-runner` precompute one cube per demo clinic. |
| **M3** | Finish `rural_options.csv` (every Franklin town verified) and build the "**no option at all**" layer data. |
| **M4** | Prepare the UI kickoff: **K:** *"Scaffold `web/` with React + Vite + TypeScript, Tailwind, shadcn/ui, MapLibre GL, deck.gl, D3, react-i18next; routes /audit, /planner, /about; typed API client generated from contracts.md."* |

---

## Phase B: UI + Kiro depth (H14 → H24)

From here **M4 leads the UI**, with **M3** helping. **Kiro Web Autonomous** builds independent UI modules from GitHub issues.

### H14–18 · UI v1 + hooks + power + Crew
| Who | Tasks |
|---|---|
| **M1** | Finish the **remaining hooks** (final doc §8.5): **#1** Session Start (feed freshness), **#2** Prompt Submit (template rule), **#3** Pre Tool Use (block unsigned template writes), **#4** Pre Tool Use (block live routing APIs), **#7** File Save `web/**` → axe-core a11y check, **#8** File Create (validate new GTFS zips), **#9** Pre Task (`make data`), **#10** Post Task (update `docs/traceability.md`).<br>**K: build the `careleap` power**: `plugin.json`, `mcp.json` (`gtfs-mcp` + `reach-mcp`), skills `clinic-access-audit` + `gtfs-debugging`. Test-install it in a fresh workspace.<br>**Crew:** `kirocrew setup` → configure MCP + steering explicitly → a heartbeat every 6h (PVTA ETag → validate → re-audit → Slack diff via the Gateway), plus a service-end alarm 14 days before feed expiry → `kirocrew doctor`. |
| **M2** | `suggest_schedule` returns the top 3 changes with impact. A `/report` endpoint for the CHNA PDF numbers. |
| **M3** | Open GitHub issues for **Kiro Web Autonomous**: ① CHNA PDF report module, ② i18n wiring EN/ES, ③ phone-mock itinerary component. Review the PRs it opens (never auto-merge). Write the printable **QR itinerary card** content. |
| **M4** | **K: Quick Spec `ui-week-grid`** → the **Audit screen**: block-group map + week grid (7 days × 12 hours) coloured by reachable share, plus the **day ribbon** on hover (D3: outbound → appointment → return → last bus home). |

### H18 · ✅ Sync #4: feature freeze for the MVP
The whole demo path is clickable in the browser. From here: **polish, tests, Kiro evidence.** Do a cut-line check (§9).

### H18–22 · Experiments + UI polish (this is what wins Best Use of Kiro)
| Who | Tasks |
|---|---|
| **M1** | Run and log the **5 experiments** in `docs/kiro-journal.md` + `docs/decisions/`:<br>① RAPTOR vs CSA (done).<br>② **Spec vs vibe:** M4 rebuilds one small UI piece by vibe coding; compare time and bugs.<br>③ **Steering on/off:** rerun a router task without `gtfs-domain.md`; count the bugs.<br>④ Requirements-First vs Design-First (router vs cube).<br>⑤ IDE vs Web Autonomous (PDF module).<br>Add the R5/r5py reference check if time allows. Write the **README "Kiro Scorecard"**. |
| **M2** | **Drag-to-shift** interaction wired to `/whatif`. "Suggest best schedule" panel. Performance + a stable `make demo`. |
| **M3** | **Rural lens** layer + **equity panel** (EJ / limited-English / 65+ / zero-vehicle). Accessibility copy review (grade 6). |
| **M4** | **Planner flow:** visit type → 6-tap barrier check → options → itinerary → phone mock (merge the Web PR). The **"How we know this is right" drawer** (calls `/provenance`). The vibe-coded rebuild for experiment ②. |

### H22–24 · Hardening
| Who | Tasks |
|---|---|
| **M1** | CI fully green. Traceability complete (every on-screen number has requirement → property → test). Deploy (AWS via the CDK/SAM power, or Netlify + Render). |
| **M2** | End-to-end tests of the demo path with **Playwright MCP**. |
| **M3** | Final fact-check. Write the **text description** (draft in final doc §14). |
| **M4** | **Accessibility pass** (keyboard, contrast, screen-reader labels, large-type mode). Animation polish (grid recolour, drag). |

### H24 · ✅ Sync #5: video lock
Agree on the shot list (final doc §15) and confirm every number on screen is computed.

---

## Phase C: Video + submission (H24 → H30)

### H24–28 · Video + write-up
| Who | Tasks |
|---|---|
| **M1** | Write the **Kiro write-up** (final doc §11). Record the **Kiro segments**: PBT shrink → bugfix spec, the provenance drawer, a Web PR, the CLI gate, the Crew Slack alert, the power page. |
| **M2** | Fresh clone → `make data && make demo` works. Write the README run steps. |
| **M3** | **Owns the video:** record app segments with M4 driving the app, write captions + voice-over, edit to **< 3:00** (and keep a 2:45 cut). Royalty-free or no music. Upload public to YouTube. |
| **M4** | Drive the app for recordings. Fix anything that breaks on camera. |

### H28 · ✅ Sync #6: final review
Everyone watches the final video. One person clones fresh and runs the app. Go through the checklist (§8).

### H28–30 · Submit
| Who | Tasks |
|---|---|
| **M1** | Submit the form: name, tagline, track, description, video link, repo link, Kiro write-up, power link. |
| **All** | Buffer for surprises. No new features. |

---

## 5. Kiro cheat-sheet (what to do where)

| Need | Where in Kiro | How |
|---|---|---|
| Steering docs | IDE → Kiro panel → Steering | Generate the foundation docs, then add files with inclusion `always` / `fileMatch` / `auto` / `manual`. Use `#[[file:...]]` to reference contracts and rule files |
| A new spec | IDE → Kiro panel → Specs → **+** | **Feature** (Requirements-First or Design-First) or **Bugfix**. **Quick Spec** for low-risk UI. Review requirements → design → tasks, then **Run all tasks** |
| Property-based tests | IDE (spec Correctness) | **IDE-only.** Approve the proposed properties. On a failure: fix code / test / requirement. A failure can become a **Bugfix spec** |
| Hooks | IDE → Agent Hooks (or `.kiro/hooks/`) | Trigger (Session Start, Prompt Submit, Pre/Post Tool Use, File Save/Create/Delete, Pre/Post Task, Agent Stop) + action (shell `command` or `agent` prompt). **Not on Web**, and file hooks fire only on *agent* edits, so CI repeats them |
| MCP servers | `.kiro/settings/mcp.json` | stdio servers `gtfs-mcp`, `reach-mcp`, `access-resources-mcp`. Use resources, prompts and elicitation, not just tools |
| Custom agents | `.kiro/agents/` | Least-privilege: `router-dev`, `content-reviewer`, `audit-runner`, `release-checker` |
| Powers | IDE → Powers → **Build a Power** | `plugin.json` + `skills/` + `mcp.json`; publish on GitHub. Catalog: Amazon Location, CDK/SAM, Figma, Snyk |
| Checkpoints | IDE / CLI | Rewind to compare RAPTOR vs CSA; log it in the journal |
| CLI (headless) | Terminal / GitHub Actions | API-key auth; `release-checker` + test suites in CI; parallel sub-agents for per-clinic cubes |
| Web | app.kiro.dev | Connect GitHub, **Config Sync**, **Autonomous** from an issue → PR, **Schedule** cron → PR. Never auto-merges |
| Crew | Your own machine | `kirocrew setup` → explicit MCP/steering → heartbeat + recurring jobs → Gateway to Slack → `kirocrew doctor`. Crew **can't SMS** patients |
| Mobile (preview) | Phone | Review Web PRs and Crew alerts (log it as an experiment) |

**Golden habit:** the Agent Stop hook writes to `docs/kiro-journal.md` after every Kiro session. At each sync, skim it and add one line of human comment. The journal *becomes* the write-up.

---

## 6. Who owns which `.kiro/` files

| File / folder | Owner |
|---|---|
| `steering/product.md, tech.md, structure.md, AGENTS.md, gtfs-domain.md, demo-script.md` | M1 |
| `steering/optimizer-notes.md` | M2 |
| `steering/equity-and-language.md` | M3 |
| `steering/visit-rules.md`, `steering/accessibility.md` | M4 |
| `specs/raptor-router, connection-scan, bug-*` | M1 |
| `specs/reachability-cube, schedule-optimizer` | M2 |
| `specs/visit-planner, ui-week-grid, ui-planner` | M4 |
| `specs/audit-report-pdf` (via Kiro Web) | M3 |
| `hooks/*`, `agents/*`, `settings/mcp.json`, `power/careleap/` | M1 |

---

## 7. Daily-driver commands (set these up early)

| Command | What it does | Owner |
|---|---|---|
| `make data` | `scripts/get_data.py` + pipeline → `data/cache/` | M2 |
| `make test` | Unit + property (fast profile) + golden trips + contract tests | M1 / M4 |
| `make test-full` | Full Hypothesis profile + differential (CSA, brute force, R5) | M1 |
| `make api` / `make web` / `make dev` | Run the API / frontend / both | M4 |
| `make demo` | Load the frozen snapshot `data/snapshots/demo-v1/` | M2 |
| `make a11y` | axe-core + Playwright accessibility run | M4 |

---

## 8. Final checklist (H28)
- [ ] Fresh clone → `make data && make demo` works
- [ ] `/.kiro` committed, not git-ignored; specs, steering, hooks, agents, MCP all present
- [ ] CI green (Kiro CLI gate + PBT + golden + contract + a11y)
- [ ] Video < 3:00, public, captioned, no copyrighted music, shows the real app
- [ ] Description, track (Healthcare · Challenge 3), Kiro write-up, power link
- [ ] Every on-screen number is computed and traceable; templates labelled; synthetic patients only
- [ ] `docs/kiro-journal.md`, `docs/traceability.md`, `docs/decisions/`, README Kiro Scorecard

---

## 9. If we fall behind (cut in this order)
1. Drop the **R5 reference check** (keep brute force + CSA).
2. Drop **dialysis + chemo** (keep colonoscopy + prenatal).
3. Drop the **OSM walk network** (use straight-line × 1.3).
4. Drop the **optimizer** (keep the manual drag what-if).
5. Drop the **FRTA mini-GTFS** stretch (keep the rural table).
6. **Never cut:** the round-trip router + PBT, the week grid + drag, Maria's escort plan, `.kiro/` depth, the video.
