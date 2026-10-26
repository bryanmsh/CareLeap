# CareLeap: Reachable Care
### Final build plan · Hackachusetts 2026 · Healthcare & Biotech · Challenge 3

> **One line:** We show western Massachusetts health systems **which of their own appointments their patients physically can't get to**, and then plan the high-stakes visits so they actually happen.

**Date:** Oct 24, 2026 · **Track:** Healthcare & Biotech · **Challenge 3:** "Improving healthcare access and coordination" ("A referral is not a finished visit")

## Contents
- [0. The idea in 60 seconds](#0-the-idea-in-60-seconds)
- [1. Why: the problem](#1-why-the-problem)
- [2. Who uses it](#2-who-uses-it)
- [3. What it does (the product)](#3-what-it-does-the-product)
- [4. How it works (under the hood)](#4-how-it-works-under-the-hood)
- [5. Data we need](#5-data-we-need)
- [6. Tech stack](#6-tech-stack)
- [7. How to build it: step by step](#7-how-to-build-it-step-by-step)
- [8. Kiro plan: built to win "Best Use of Kiro"](#8-kiro-plan-built-to-win-best-use-of-kiro)
- [9. Scoring map: every judging line, answered](#9-scoring-map-every-judging-line-answered)
- [10. Demo video script (under 3:00)](#10-demo-video-script-under-300)
- [11. Kiro write-up outline](#11-kiro-write-up-outline-required-for-submission)
- [12. Risks and how we handle them](#12-risks-and-how-we-handle-them)
- [13. Submission checklist](#13-submission-checklist)

---

## 0. The idea in 60 seconds

**The old CareLeap:** a coordinator pasted a few appointment times for *one* patient and saw which ones the bus could reach.

Judges raised three weaknesses:
1. "Transport alone doesn't fix no-shows."
2. "A coordinator could check Google Maps."
3. "It ignores rural towns."

**CareLeap: Reachable Care** answers all three with two modes on one routing engine.

| Mode | Who | What it does |
|---|---|---|
| **① Clinic Audit** *(the headline)* | Hospital ops managers, ACO/MassHealth planners, community-benefit teams | For every specialty clinic and every hour of the week, it computes **what share of car-less adults in each neighborhood can get there *and back* by bus**. It shows where the schedule fails whole communities, and **which change fixes it**: move a block, or add a satellite day. |
| **② Visit Planner** *(the follow-through)* | Referral coordinators and patient navigators | For a **high-stakes visit** (colonoscopy after a positive test, prenatal, dialysis, chemo), it runs a 30-second barrier check and outputs a plan to make the visit happen. That can be a reachable slot that fits the patient's work shift, an escort-aware ride request, a telehealth swap, or an in-language prep sheet. It sends the itinerary, including the last bus home, the day before. |

**Why it's new:** no tool today computes *round-trip* transit reachability for a clinic's whole weekly schedule against the neighborhoods it serves. Google Maps plans one trip. We audit **thousands of visit-hours at once**, and we show what a schedule change would do.

**Demo moment:** click **Holyoke** and a grid of Baystate's clinic hours turns red. Drag the GI block from **8am → 10am** and the reachable share jumps. Then open one positive-screening patient: *"Needs an escort — transit won't work."* The app pre-fills the ride request and picks a slot inside a volunteer-driver window.

---

## 1. Why: the problem

### 1.1 Missed specialty visits have a real cost
- **About 3.6 million Americans** miss or delay care each year because of transportation (Wallace et al.).
- The visits that matter most are the ones that get missed:
  - **Colonoscopy after a positive stool test (FIT).** Many patients never complete the follow-up colonoscopy *(verify rate; published estimates are often around half within 6 months)*. An unfinished follow-up is how a screen-detected cancer becomes a late-stage cancer.
  - **Prenatal visits.** Late or missed prenatal care is linked to worse maternal and infant outcomes.
  - **Dialysis.** A missed session is dangerous, and patients go three times a week.
  - **Chemotherapy and infusion.** These run on fixed cycles.

### 1.2 Clinic schedules are set without checking the bus
- Clinic hours are set around staff and rooms, not around **whether patients without a car can arrive and get home**.
- An 8:00am slot can be "on a bus route" and still be impossible:
  - the first bus arrives at 8:20, or
  - the visit ends at 4:30 and the last bus home left at 4:41, ten minutes before the patient could reach the stop.
- **Nobody measures this at the schedule level.** Health systems see a "no-show rate", not a cause.

### 1.3 The bus is only one barrier
- A JAMA Internal Medicine trial (Chaiyachati 2018) gave **free rides** to 786 Medicaid patients. Missed visits barely moved: **36.5% vs 36.7%**.
- That doesn't mean transport is irrelevant. It means **transport has to be solved together with the other barriers**: work shifts, childcare, needing an escort, cost, language, and fear.
- **We use this study directly:** we don't bet everything on the bus.

### 1.4 Some visits can't use the bus at all
- **Sedated procedures**, colonoscopy above all, need an adult escort home. Most endoscopy units won't discharge a sedated patient to a bus, or even a taxi, alone *(verify per clinic)*.
- This is a known reason colonoscopies get cancelled on the day. **The app catches it automatically.**

### 1.5 Rural western Massachusetts is worse, and invisible in the data
- **Franklin County's transit agency (FRTA) publishes no GTFS feed** (none listed on MobilityDatabase as of our check), so no trip planner can route there.
- Rural residents rely on demand-response "dial-a-ride", Council on Aging volunteer drivers, and **MassHealth PT-1 rides**. PT-1 must be requested by the provider.
- **We map what exists, and we show who has *no option at all*.** That map is a finding in its own right.

### 1.6 Health systems are already required to look at this
- **Every nonprofit hospital must publish a Community Health Needs Assessment (CHNA)** and an implementation strategy (IRS 501(r)). **Access to care and transportation** show up again and again in western MA CHNAs *(verify the Baystate CHNA text)*.
- **MassHealth ACOs** are paid on quality and total cost of care and run health-related social needs programs *(verify the current flexible-services scope)*.
- So **the buyers have a reason, and often a budget line, today.**

### 1.7 Why existing tools don't solve it
| Existing option | What it does | Why it falls short |
|---|---|---|
| Google Maps / transit apps | Plans **one** trip | Can't audit a schedule, doesn't check the round trip against the visit length, no equity view |
| Scheduling systems (Epic Cadence, Zocdoc) | Book appointments | Optimize the provider's calendar, not whether the patient can reach it |
| NEMT / ride brokers, Uber Health, Lyft Healthcare | Book rides | Rides alone didn't change no-shows, and they ignore sedation escorts and work shifts |
| Closed-loop referral tools (Unite Us, etc.) | Track referrals | Don't plan transit or test schedules |
| Transit-equity research (academic) | One-off studies | Not operational, not tied to a clinic's real schedule |

**Our niche is open:** an operations-research engine that audits **a clinic's schedule against the community it serves**, plus a visit planner for **the visits where a no-show really hurts**.

---

## 2. Who uses it

| User | Their job | What they get | Why they'd adopt it now |
|---|---|---|---|
| **Clinic operations manager** (e.g., Baystate GI, Holyoke Medical Center OB) | Sets clinic templates and hours | A heatmap of reachable share by hour × neighborhood, plus "what-if" fixes | No-shows waste capacity; a cheap fix (shift a block) recovers visits |
| **Community-benefit / CHNA team** | Writes the CHNA and implementation strategy | A **CHNA-ready Access Audit report**: findings, maps, recommended actions | IRS 501(r) requires the CHNA, and they need measurable access actions |
| **MassHealth ACO / population-health planner** | Owns quality metrics and HRSN programs | Which members' high-stakes visits are at risk, and which program fixes them | Quality measures (e.g., colorectal screening follow-up), total-cost-of-care |
| **Referral coordinator / patient navigator** (FQHC: Holyoke Health Center, Caring Health Center) | Gets the patient to the visit | The Visit Planner: barrier check → a plan that can actually happen | Already on the phone with specialist offices daily |
| **Regional transit authority** (PVTA) and **regional planners** (Pioneer Valley Planning Commission) | Plan routes and service hours | Health-trip demand that their service misses | Evidence for route changes and grants |
| **Patient** (car-less, Holyoke/Springfield/Amherst/Northampton; rural Franklin County) | Gets to the visit | An itinerary with the last bus home, the day before, in their language, plus a printed card | Nothing to install |

**Two named people for the pitch** (fictional composites, labelled as such):
- **Maria, Holyoke.** Spanish-speaking, no car, works 7am–3pm at a warehouse. Her FIT test was positive. Baystate offers an 8:00am colonoscopy. She can't get there by bus, she can't miss work, and she can't ride home sedated. → **The Visit Planner** finds a slot after her shift is possible, inside a volunteer-driver window, files a PT-1 ride for the escort trip, and gives her a Spanish prep sheet.
- **Baystate GI operations manager.** → **The Clinic Audit** shows the 8am block is unreachable from most of Holyoke's EJ block groups *(number computed)*. Moving it to 10am, or adding a Holyoke satellite morning, fixes it for N residents.

---

## 3. What it does (the product)

### 3.1 Mode ① Clinic Audit
**Screen layout:** a map on the left, a "week grid" on the right, and an action panel below.

1. **Pick a clinic and specialty.** Example: Baystate Medical Center, GI / endoscopy (Springfield).
2. **Pick a community.** Click a town (Holyoke) or select EJ block groups on the map.
3. **The Reachability Grid appears:**
   - Rows are days of the week and columns are clinic hours (7am–6pm).
   - Each cell shows the **% of car-less adults in that community who can arrive on time and get home the same day by transit**, given the visit length (GI ≈ 2h including prep and recovery).
   - Colours run red → amber → green. A cell turns grey if service doesn't run (e.g., Sunday).
4. **Hover a cell** and a "day ribbon" explains *why*:
   - *"Arrive 7:52 ✔ · visit ends 10:00 · last useful bus 9:41 ✘ · next 11:15 → wait 75 min."*
   - The ribbon draws the outbound legs → appointment block → return legs.
5. **What-if panel:**
   - **Drag a clinic block** (8am → 10am) and the grid and map recompute live.
   - **"Add satellite day"** at a chosen site (e.g., Holyoke Medical Center) shows how the reachable share changes.
   - **"Suggest best schedule"** runs an optimizer and proposes up to K schedule changes that maximize reachable visit-hours for EJ neighborhoods, given the clinic's opening hours.
6. **Equity panel:** results broken out by EJ status, limited-English %, age 65+, and zero-vehicle households.
7. **Rural lens:** for towns with no fixed-route data (Franklin County), the map shows which options exist: **dial-a-ride**, **Council on Aging volunteer driver**, **PT-1**, or **none**. A "**no option at all**" layer highlights those towns.
8. **Export a CHNA Access Audit (PDF):** findings, the grid, maps, the recommended changes with their impact, a methods appendix, and data vintages.

**What's new here:** a computed **round-trip, visit-length-aware reachability score** for a real clinic schedule, broken out by equity group, plus **counterfactual fixes**. Nobody publishes this.

### 3.2 Mode ② Visit Planner (high-stakes visits)
1. **Pick the visit type.** Colonoscopy after a positive FIT · Prenatal · Dialysis · Chemo/infusion · Other specialty.
   - Each type carries **rules** in a "visit-type rulebook":
     - duration
     - **escort required?** (sedation)
     - **telehealth-eligible?** (e.g., some follow-ups yes, procedures no)
     - **prep needed?** (bowel prep sheet)
     - **recurrence** (dialysis is 3×/week)
2. **30-second barrier check** (6 tap-questions, based on the public **CMS Accountable Health Communities (AHC) HRSN screening tool** and **PRAPARE** themes; uses those public instruments):
   - Car or transport? · Work shift hours? · Childcare? · Someone who can escort you? · Out-of-pocket cost worry? · Preferred language / any worries about the visit?
3. **The engine builds a "Can this visit happen?" plan.** It ranks options:
   - ✅ **A reachable slot** that fits the bus *and* the work shift *and* the childcare window.
   - 🚗 **Escort-aware ride:** if sedation means transit won't work, it pre-fills a **PT-1 request** and suggests slots that match **volunteer-driver windows**.
   - 💻 **Telehealth swap**, if the visit type allows it.
   - 📄 **An in-language prep sheet** (from reviewed templates only).
   - ⚠️ **No viable option**, flagged for a navigator to call, with the reason.
4. **Day-before itinerary:** the exact trip, transfers, walking, wheelchair-boarding flags, **the last bus home**, and a "plan B" if you miss it. It's shown on an **in-app phone mock** plus a **printable card with a QR code**. (Live SMS isn't feasible in a hackathon because of toll-free verification. It's a post-hackathon integration.)

**What's new:** escort-aware, shift-aware, round-trip scheduling for the visits where missing one causes countable harm, with every barrier checked, not just transport.

### 3.3 Guardrails (shown on screen, enforced in code)
- **Logistics only.** We never make a clinical decision or decide eligibility. *"Your care team decides your care."*
- **Synthetic patients only** in the demo, with no PHI.
- **Patient text comes only from human-reviewed templates** (EN + ES in the MVP), per **45 CFR 92.201(c)(3)**. No live machine translation goes to patients.
- **Every number shows its source and data date.** Illustrative numbers are never stated as findings.

---

## 4. How it works (under the hood)

### 4.1 Architecture
```
              ┌──────────────── DATA PREP (offline, cached) ─────────────────┐
 PVTA GTFS ──►│ gtfs-ingest → validate → timetable arrays (stops/routes/trips)│
 ACS + EJ  ──►│ block groups → car-less adults → population-weighted origin   │
 OSM walk  ──►│ points → walk links to nearest stops (≤ 800 m)                │
 Clinics   ──►│ clinic sites (MassGIS/CMS/NPPES) + schedule templates (CSV)   │
 Rural     ──►│ demand-response / COA / PT-1 coverage table by town           │
              └───────────────────────────────┬──────────────────────────────┘
                                              ▼
                         ┌──────────── ROUTING ENGINE ────────────┐
                         │ Round-trip RAPTOR (profile / rRAPTOR)   │
                         │  • outbound: latest departure that      │
                         │    arrives ≤ slot_start − buffer        │
                         │  • return: earliest arrival home after  │
                         │    slot_end, before service ends        │
                         │ Oracles: brute-force router (tiny nets) │
                         │          + Connection Scan (CSA) diff   │
                         │          + R5/r5py (reference engine)   │
                         └───────┬──────────────────────┬──────────┘
                                 ▼                      ▼
              ┌──────── CLINIC AUDIT ────────┐  ┌────── VISIT PLANNER ───────┐
              │ reachability cube:           │  │ visit-type rulebook         │
              │ block group × clinic ×       │  │ barrier check (AHC/PRAPARE) │
              │ day × hour → reachable?      │  │ constraint solver → ranked  │
              │ → % car-less adults reached  │  │ plan (slot/ride/tele/prep)  │
              │ what-if + greedy optimizer   │  │ itinerary + last bus home   │
              └──────────────┬───────────────┘  └──────────────┬─────────────┘
                             ▼                                 ▼
                   React UI: map · week grid · day ribbon · phone mock · PDF
```

### 4.2 The core calculation, in plain words
For each **origin** (a population-weighted point in a block group), **clinic**, **day** and **appointment start time `s`** with visit length `d`:

1. **Can you get there?** Is there a trip (walk + bus + transfers + walk) that arrives at the clinic **at or before `s − 10 min`** (check-in buffer), leaving home no earlier than a sane hour (e.g., 5:30am)?
2. **Can you get home?** Is there a trip that **leaves the clinic at or after `s + d`** and gets home **the same day**?
3. A cell is **reachable** if both are yes, within limits: total travel ≤ 2h each way, walking ≤ 800 m per leg, at most 2 transfers. The limits are configurable.
4. **Reachable share** = the car-less adults in a community whose origin point can make the round trip ÷ all car-less adults there.

**Speed trick:** **rRAPTOR (range RAPTOR)** computes the answer for *every* departure time across the day in one pass per origin. With about 300 block groups × 2 directions, the whole week grid runs in seconds and is cached.

### 4.3 The optimizer (what-if → "suggest best schedule")
- **Decision:** which clinic blocks to shift by ±1–3 hours, and/or which single satellite day to add, within the clinic's open hours and its number of blocks.
- **Objective:** maximize **reachable visit-hours for EJ car-less adults**, weighted by visit priority (colonoscopy follow-up, prenatal and dialysis count more).
- **Method:** greedy with lazy evaluation, which is near-optimal for this coverage-style objective. A small exact solve (OR-Tools CP-SAT) checks the greedy result on tiny cases, as a differential test.

### 4.4 Visit Planner logic
A small, explicit **constraint solver**. Each candidate option is checked against hard rules:
- the escort rule
- the work shift
- the childcare window
- telehealth eligibility
- the round-trip transit result

Options are then ranked by burden (travel time, waiting, cost). **Every rule is data** (a `visit_rules.yaml` file), so it's auditable and easy to extend.

---

## 5. Data we need

| # | Dataset | What it gives us | Where / access | Notes |
|---|---|---|---|---|
| 1 | **PVTA GTFS** | Bus stops, routes, timetables, `wheelchair_boarding` | `pvta.com/g_trans/google_transit.zip` (live, 6.4 MB, updated 2026-09-18). Also MobilityDatabase `mdb-2416` | Validate on day 1 (it had 2 validation errors and lost its reliability seal 2026-09-03). **Service window ends ~Dec 19**, so plan the demo date inside it |
| 2 | **US Census ACS 5-yr** | Car-less households (**B25044**, tenure × vehicles, block-group level), population, age 65+, language | data.census.gov / Census API | Gives "car-less adults" per block group |
| 3 | **Census TIGER block groups** | Shapes + centroids | census.gov | Use population-weighted points, not plain centroids |
| 4 | **MassGIS Environmental Justice block groups** | EJ status, minority %, **limited-English %**, income | Portal kit `ej/` (ArcGIS REST) | Equity breakdown |
| 5 | **MassGIS Hospitals** | Hospital sites + bed counts | Portal kit `hospitals/` | Western MA acute hospitals |
| 6 | **CMS Provider Data** (hospital general info, ratings) | Hospital types, ED, ratings | Portal kit `cms-hospitals/` | Context |
| 7 | **CMS Dialysis Facility data** | Dialysis sites, stations, shift info (e.g., evening shifts) | data.cms.gov Provider Data | *(verify which shift fields are present)* Dialysis is a 3×/week high-stakes trip |
| 8 | **NPPES NPI Registry** | Specialist locations by taxonomy (GI 207RG0100X, OB/GYN 207V00000X, oncology) | `npiregistry.cms.hhs.gov/api` | Query by city/ZIP. `state` alone is rejected; max 200 per call |
| 9 | **Clinic schedule templates** | Which hours each clinic runs which visit type | **Input the user uploads** (CSV). Demo: built from **publicly posted clinic hours** for ~10–20 clinics + clearly labelled realistic templates | Real hours are rarely public, so the product takes the health system's own template |
| 10 | **OpenStreetMap** (Geofabrik MA extract) | Walk network to and from stops | download.geofabrik.de | Walk legs ≤ 800 m |
| 11 | **CDC PLACES** (tract) | Colorectal screening prevalence, chronic disease burden | `data.cdc.gov` `yjkw-uj5s` | Weights the high-stakes demand; model-based estimates |
| 12 | **Rural options table** (built by us) | Per Franklin/Hampshire town: dial-a-ride, Council on Aging volunteer drivers, PT-1 | FRTA, COA and MassHealth PT-1 pages | **Hand-verify each town on day 1.** Cite sources |
| 13 | **MassHealth PT-1 form** | Ride-request fields for the pre-fill | mass.gov | Provider-submitted |
| 14 | **CMS AHC HRSN screening tool** / **PRAPARE** | Barrier-check questions | Public screening tools | Base the 6 questions on them |
| 15 | *(Stretch)* **FRTA routes (PDF timetables)** | Rural fixed routes | frta.org | Could hand-encode 1–2 routes as mini-GTFS ("we built the first open feed") |

---

## 6. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language (engine) | **Python 3.12** | Fast to write; Hypothesis is the best PBT library |
| GTFS parsing | `gtfs-kit` or `partridge` + pandas | Mature GTFS loaders |
| Routing | **Our own RAPTOR / rRAPTOR in NumPy** (core) | Judges see real operations research; fully testable |
| Routing oracles | Brute-force Dijkstra-over-time-expanded-graph (tiny nets), **Connection Scan Algorithm** (second implementation), **r5py / Conveyal R5** (industry reference) | Three independent checks give a differential-testing story |
| Walk network | OSMnx (OSM) or a straight-line × detour factor (MVP) | Walk legs to stops |
| Optimizer | Greedy + **OR-Tools CP-SAT** (verifier) | Proven method plus an exact check |
| Property tests | **Hypothesis** (Python) | Shrinking counterexamples feed Kiro's bugfix specs |
| API | **FastAPI** | Typed, quick |
| Storage | **DuckDB + Parquet** caches | Zero-ops, fast |
| Frontend | **React + Vite + TypeScript**, **MapLibre GL + deck.gl** (map), **D3** (week grid, day ribbon) | Polished, interactive |
| UI kit | Tailwind + shadcn/ui; **WCAG 2.2 AA** (keyboard, contrast, screen reader), large-type mode | Accessibility is a scored item |
| i18n | `react-i18next`, EN + ES reviewed templates | Language access |
| PDF | WeasyPrint (server) or react-pdf | CHNA Access Audit + printable itinerary card |
| QR | `qrcode` | Itinerary card |
| Deploy | AWS via Kiro catalog powers (**CDK/SAM**, Lambda/Fargate + S3/CloudFront), or Netlify (frontend) + Fly/Render (API) | Simple, and the AWS sponsor likes it |
| CI | GitHub Actions + **headless Kiro CLI** | Quality gates |

---

## 7. How to build it: step by step

### 7.1 Repo layout
```
careleap/
├── .kiro/                     ← MUST be committed (never .gitignore)
│   ├── steering/              (product, tech, structure, + domain files)
│   ├── specs/                 (one folder per spec + bugfix specs)
│   ├── hooks/                 (agent hooks)
│   ├── agents/                (custom agents for CLI/IDE)
│   ├── skills/                (project skills)
│   └── settings/mcp.json      (MCP servers)
├── AGENTS.md                  (always-on agent rules)
├── engine/                    (GTFS ingest, RAPTOR, CSA, brute force, reachability cube, optimizer)
├── planner/                   (visit rules, barrier check, constraint solver, itinerary)
├── api/                       (FastAPI)
├── web/                       (React app)
├── mcp/                       (gtfs-mcp, reach-mcp, access-resources-mcp)
├── power/careleap/        (publishable Kiro power: plugin.json, skills/, mcp.json)
├── data/                      (raw/ + cache/ Parquet; small fixtures committed)
├── tests/                     (unit, property, differential, golden trips)
├── docs/                      (kiro-journal.md, traceability.md, methods.md, decisions/)
└── .github/workflows/         (kiro-ci.yml, pbt.yml, data-refresh.yml)
```

### 7.2 Build timeline (~30 hours, 4 people)
| Phase | Hours | Goal | Done when |
|---|---|---|---|
| **0. Prep** (before the clock, data only) | — | Download GTFS, ACS, TIGER, OSM extract, EJ. Collect public clinic hours. Draft the rural options table | Files in `data/raw/` |
| **1. Foundations** | 0–3 | Steering docs, repo skeleton, MCP servers stubbed, specs drafted in Kiro (requirements-first) | `.kiro/` populated; specs approved |
| **2. Engine** | 3–12 | GTFS ingest + validation → RAPTOR → round-trip check → brute force + CSA oracles → PBT green | Golden trips match hand-checked PVTA trips |
| **3. Audit** | 8–16 | Reachability cube, equity breakdown, what-if, greedy optimizer | Grid for Baystate GI × Holyoke computes in <5 s |
| **4. Planner** | 10–18 | Visit rulebook, barrier check, constraint solver, PT-1 pre-fill, itinerary | Maria's case produces the escort-aware plan |
| **5. UI** | 6–24 | Map, week grid, day ribbon, what-if drag, planner flow, phone mock, PDF | Demo path is clickable end to end |
| **6. Kiro depth** | throughout | Hooks, Crew jobs, Web PRs, power packaging, journal | Kiro scorecard page populated |
| **7. Polish + video** | 24–30 | Accessibility pass, copy review, record video, write-up | Video < 3:00, write-up done |

### 7.3 Team split
| Person | Owns |
|---|---|
| **A: Routing** | GTFS ingest, RAPTOR/rRAPTOR, CSA + brute-force oracles, `gtfs-mcp`, router PBT |
| **B: Audit + data** | ACS/EJ joins, origins, reachability cube, optimizer, rural table, `reach-mcp` |
| **C: Planner + content** | Visit rulebook, barrier check, solver, PT-1 pre-fill, EN/ES templates, itinerary card |
| **D: UI + Kiro ops + video** | React app, accessibility, PDF, Crew/Web/CLI wiring, power packaging, video, write-up |

---

## 8. Kiro plan: built to win "Best Use of Kiro"

**How the prize works:** the prize goes to the project with the **highest Implementation score that is also in the top 10% overall**. So we need *both* a strong product *and* a Kiro story judges can't miss.

**Our strategy has three moves:**
1. **Use every Kiro surface for the job it's best at**: IDE, CLI, Web, Crew, and Mobile (preview). Write down *why* each choice was made.
2. **Make correctness visible.** Specs → properties → tests → **every number in the UI**, all traceable.
3. **Experiment on purpose, and log it.** Try two routing algorithms and two spec styles, compare them, and record the decisions.

### 8.1 Surface map: which Kiro tool does what, and why
| Kiro surface | What we use it for | Why this surface |
|---|---|---|
| **IDE** | Specs (all types), **property-based testing** (IDE-only), hook authoring, steering, power building, checkpoints | The deep, interactive work, where PBT and spec traceability live |
| **CLI (headless)** | GitHub Actions gates; **custom least-privilege agents**; **parallel sub-agents** to precompute reachability for each clinic | Repeatable automation. It also re-runs hook checks, because hooks don't fire on human edits or Web PRs |
| **Web** | **Autonomous mode** builds independent modules from GitHub issues as PRs (PDF report, i18n, phone mock). **Schedule** runs a weekly GTFS/data refresh PR | Parallel builders while the IDE does the engine. Never auto-merges, so humans review |
| **Crew** | **Runtime operations agent:** heartbeat on the PVTA feed, auto re-audit when service changes, planner digest to Slack, overnight Task Runner, lessons → skills | Turns the tool into a *standing monitor*. A surprising, real use |
| **Mobile (preview)** | Review and steer Web PRs and Crew alerts from a phone during the hackathon | Shows variety. Note it as an experiment |

### 8.2 Specs: the right type for each part
| Spec | Type | Why that type |
|---|---|---|
| `raptor-router` | **Requirements-First** (EARS) + **Analyze Requirements** | A wrong answer strands a patient, so we start from precise requirements |
| `reachability-cube` | **Design-First** | The data model and algorithm (rRAPTOR profile) come first |
| `schedule-optimizer` | Requirements-First | The objective and constraints must be exact |
| `visit-planner` | Requirements-First | Rules about escorts, shifts and telehealth are safety-relevant |
| `ui-week-grid`, `ui-planner`, `audit-report-pdf` | **Quick Spec** | Low risk, so move fast |
| `bug-*` | **Bugfix specs**, generated from real PBT counterexamples | Shows the loop from counterexample to fix |

Use **"Run all tasks"** so independent tasks run in parallel waves, and log the wave plan in `docs/kiro-journal.md`.

**Experiment to log:** we build `ui-week-grid` *twice*, once by vibe coding and once from a Quick Spec, and compare time, bugs and rework in the write-up. That gives the "spec vs vibe" answer with data, not opinion.

### 8.3 Property-based testing: our strongest card
Write each property as an EARS requirement so Kiro links property ↔ requirement ↔ task.

**Router properties**
1. **Causality:** for every journey, arrival ≥ departure, and every leg starts after the previous one ends.
2. **FIFO:** leaving later never gets you there earlier, so `arrive(t1) ≤ arrive(t2)` when `t1 ≤ t2`.
3. **Transfer minimum:** every transfer respects the minimum transfer time.
4. **Pareto optimality:** no returned journey is beaten on both arrival time and number of transfers.
5. **Differential (brute force):** on small random GTFS networks, RAPTOR's earliest arrival equals the brute-force router's.
6. **Differential (two algorithms):** RAPTOR and Connection Scan agree on every query, on the real PVTA network.
7. **Reference check:** on a fixed sample of PVTA queries, results match R5/r5py within a 1-minute tolerance.
8. **Round-trip soundness:** a slot is "reachable" ⇔ an outbound arrival ≤ `s − buffer` *and* a return departure ≥ `s + d` both exist on the same day.
9. **Midnight/service-day safety:** trips crossing midnight and GTFS times > 24:00:00 are handled correctly (a classic GTFS trap).

**Audit properties**
10. **Monotone in buffer:** a bigger check-in buffer or longer visit never *increases* reachability.
11. **Monotone in access:** adding a stop, a trip or a satellite site never *decreases* reachability anywhere.
12. **Conservation:** reached + not reached = all car-less adults, for every community and cell.
13. **Optimizer never worse:** the suggested schedule's objective is ≥ the current schedule's, and it respects clinic hours and block counts.
14. **Greedy vs exact:** on tiny instances, greedy is within the proven bound of CP-SAT's optimum.

**Planner properties**
15. **Escort rule:** a sedated visit never gets a transit-only plan.
16. **Shift rule:** no recommended slot overlaps the patient's stated work shift (including the travel time).
17. **Telehealth rule:** a telehealth swap is offered only when the visit type allows it.
18. **No clinical or eligibility text:** generated output never contains clinical advice or "eligible" phrasing.
19. **Itinerary integrity:** the "last bus home" shown is truly the last departure that still reaches home, and plan B is always later than plan A.

**The live demo beat:** a seeded PBT run shrinks a real bug to one stop and one trip. A good candidate is a **GTFS `24:30:00` after-midnight return trip** being treated as 00:30 the same day. Kiro generates the **bugfix spec** and the fix, and the property goes green.

### 8.4 Steering: all four inclusion modes, on purpose
| File | Inclusion | What it says |
|---|---|---|
| `product.md` | **always** | Mission, users, guardrails: logistics only, no clinical or eligibility decisions |
| `tech.md` | **always** | Stack, coding standards, "all numbers carry source + vintage" |
| `structure.md` | **always** | Repo layout, module boundaries |
| `gtfs-domain.md` | **fileMatch** `engine/**` | GTFS quirks: times > 24:00, `calendar_dates` exceptions, `frequencies.txt`, transfers, wheelchair fields |
| `equity-and-language.md` | **fileMatch** `web/src/content/**, planner/templates/**` | Reviewed templates only (45 CFR 92.201), grade-6 reading level, EN/ES |
| `accessibility.md` | **fileMatch** `web/**` | WCAG 2.2 AA rules, keyboard paths, contrast, large type |
| `visit-rules.md` | **auto** (description: "visit types, escort, sedation, telehealth, dialysis, prenatal") | Visit rulebook semantics, with `#[[file:planner/visit_rules.yaml]]` |
| `optimizer-notes.md` | **auto** (description: "schedule optimization, coverage, satellite clinic") | Objective, constraints, bounds |
| `demo-script.md` | **manual** (`#demo-script`) | The exact demo path, used only when rehearsing |
| `AGENTS.md` | always (Kiro reads it) | Top-level rules shared with other agent tools |

**Logged experiment:** run the same router task with and without `gtfs-domain.md` and record which GTFS bugs the agent introduced without it.

### 8.5 Hooks: one for every trigger type that matters
| # | Trigger | Matcher / target | Action | Why |
|---|---|---|---|---|
| 1 | **Session Start** | — | command: check GTFS cache freshness + service window, print "feed valid until Dec 19" | Avoids silent stale data |
| 2 | **Prompt Submit** (IDE) | prompts mentioning "patient" text | agent: inject the reviewed-template rule | Stops ad-hoc patient copy at the source |
| 3 | **Pre Tool Use** (blocking) | writes to `planner/templates/**` | command: block unless `signoff.json` has a matching hash | Human review for translated text |
| 4 | **Pre Tool Use** (blocking) | shell or HTTP calls to live third-party routing APIs | command: block and point to `gtfs-mcp` | Keeps the demo deterministic |
| 5 | **Post Tool Use** | `@gtfs-mcp` | command: append query + result hash to `docs/provenance.jsonl` | Feeds the UI's "where did this number come from" |
| 6 | **File Save** | `engine/**` | command: fast Hypothesis suite + golden trips | Instant feedback on the router |
| 7 | **File Save** | `web/**` | command: axe-core accessibility check on the changed component | Accessibility as a gate |
| 8 | **File Create** | `data/raw/*.zip` | command: run the GTFS validator, write a report | Validates new feeds the agent downloads |
| 9 | **Pre Task Execution** | spec tasks | command: `make data` (caches present, checksums recorded) | Reproducible tasks |
| 10 | **Post Task Execution** | spec tasks | agent: update `docs/traceability.md` (requirement → property → test → UI number) | Makes Kiro usage visible to judges |
| 11 | **Agent Stop** | — | agent: append a dated entry to `docs/kiro-journal.md` (what was asked, which spec/hook/steering helped, what we changed) | **Auto-writes our Kiro write-up as we go** |

Hooks guard the *coding agent*. Runtime guardrails such as "no clinical text" and k-safe outputs live in app code, and **CLI CI re-runs hooks 3, 6 and 7** so human edits and Web PRs are covered too.

### 8.6 MCP: three custom servers, using more than basic tools
| Server | Tools | Resources / prompts / elicitation | Used by |
|---|---|---|---|
| **`gtfs-mcp`** | `plan_trip(origin, dest, depart_after/arrive_by)`, `round_trip(origin, clinic, slot, duration)`, `service_changes(since)`, `validate_feed()` | **Resources:** feed metadata, stop list. **Prompt:** `explain_trip` (plain-language day ribbon) | Agent while coding; the app's API; Crew |
| **`reach-mcp`** | `reachability(clinic, community, day)`, `what_if(clinic, block_shift)`, `suggest_schedule(clinic, k)` | **Resources:** cached cubes. **Elicitation:** asks for the visit duration if it's missing | Agent; Crew re-audits; CLI sub-agents |
| **`access-resources-mcp`** | `rural_options(town)`, `pt1_prefill(patient, visit)`, `visit_rules(type)` | **Resources:** the rural options table with sources | Planner; agent |
| *(existing)* GitHub, Playwright, AWS Documentation | PR/issue automation, end-to-end UI tests, deploy docs | — | Dev workflow |

### 8.7 Powers: publish one, use catalog ones
- **Publish `careleap` power** on GitHub, installable by any team or health system.
  - `plugin.json`: keywords "transit, GTFS, appointment, access, clinic schedule, reachability".
  - `mcp.json`: bundles `gtfs-mcp` + `reach-mcp`.
  - `skills/clinic-access-audit/`: how to audit a clinic schedule with any city's GTFS.
  - `skills/gtfs-debugging/`: the GTFS traps we hit, learned from Crew lessons.
  - **This is the scale story, packaged:** *swap in any GTFS feed in the US.*
- **Catalog powers:** **Amazon Location** (geocoding addresses to stops), **CDK or SAM** (deploy), **Figma** (design to code for the grid UI), **Snyk/Aikido** (security scan). Optionally **Postman** (API tests).

### 8.8 Custom agents and skills (CLI + IDE)
| Agent | Permissions | Job |
|---|---|---|
| `router-dev` | Write `engine/**` only, no network | Router work, with the PBT skill |
| `content-reviewer` | **Read-only** | Back-translates ES templates and diffs them against EN; can't edit |
| `audit-runner` | Read data, call `reach-mcp` | Used by CLI parallel sub-agents to precompute each clinic's reachability cube |
| `release-checker` | Read-only + run tests | CI gate: PBT, golden trips, a11y, traceability check |

**Skills:** `pbt-for-routing`, `gtfs-quirks`, `chna-report-writing`.

### 8.9 Crew: a real runtime role, not decoration
1. **Feed heartbeat.** Every 6 hours, check the PVTA GTFS URL (ETag / Last-Modified) and the service window. If it changed, run `validate_feed`, **re-run the audit** for tracked clinics through the Task Runner (with checkpoints and retries), and post a diff to Slack: *"New PVTA schedule: Baystate GI 8am reachable share for Holyoke ↓ from X% to Y%."*
2. **Service-end alarm.** The current feed ends around Dec 19. Crew alerts 14 days before any feed expiry.
3. **Day-before job.** Every evening, build tomorrow's itineraries for planned high-stakes visits. In the demo they land in the phone mock and a Slack "navigator digest". **Crew doesn't text patients.**
4. **Parallel research subagents.** Verify the rural options per town (dial-a-ride, Council on Aging, PT-1) from public pages, with a human approving each row.
5. **Lessons → skills.** Every GTFS bug we fix becomes a lesson, and the repeated ones are promoted into the `gtfs-quirks` skill shipped in the power.
- Configure Crew's MCP and steering **explicitly**, and verify with `kirocrew doctor`. Don't rely on unverified `.kiro` reuse.

### 8.10 Making Kiro use *visible*: the judges' "understanding" criterion
- **`docs/kiro-journal.md`** is written automatically by the Agent Stop hook. It's a dated log of decisions, experiments and outcomes.
- **`docs/traceability.md`** is updated by the Post Task hook. It maps **requirement → property → test → UI element**.
- **An in-app "How we know this is right" drawer.** Click any number in the UI to see:
  - its data source and vintage
  - the requirement it satisfies
  - the property tests guarding it, and their status
  - the Kiro spec link

  *Kiro's spec-driven correctness becomes a product feature.* This is the "surprising integration".
- **A "Kiro Scorecard" section in the README**, with counts: specs, tasks, properties, counterexamples found → bugfix specs, hooks fired, MCP calls, Web PRs, Crew alerts.
- **`docs/decisions/`** holds short ADRs, for example "RAPTOR vs CSA", "Design-First for the cube", "why hooks + CLI CI".

### 8.11 Logged experiments (the criterion asks for "experimentation and strategic decisions")
1. **RAPTOR vs Connection Scan.** Build both with Kiro, cross-check them, and pick one for speed and clarity. Use **checkpoints** to rewind and compare.
2. **Spec vs vibe.** Build the same UI module both ways and measure time, bugs and rework.
3. **Steering on vs off.** Run the router task with and without `gtfs-domain.md` and count bugs.
4. **Requirements-First vs Design-First** for the cube spec. Note which produced fewer revisions.
5. **IDE vs Web Autonomous** for the PDF module. Compare quality and review effort.

---

## 9. Scoring map: every judging line, answered

### Potential Value
| Judging line | How we answer it |
|---|---|
| Widely useful, easy to use, accessible | Two modes for two daily jobs. Patients need no app (phone mock + printed card). WCAG 2.2 AA; EN/ES; large type |
| Real, clearly defined problem | Specialty visits unreachable by transit; high-stakes follow-ups missed; free rides alone don't work (JAMA trial) |
| Scalable and realistic | **GTFS is a national standard** (most US agencies publish it), **ACS is national**, **CHNAs are required of every US nonprofit hospital**. Swap the feed and the clinic list. The power packages it |
| Unique needs of an affected community | Car-less, limited-English, shift-working and rural residents. EJ breakdown. Escort-aware sedation planning. "No option" rural map |
| Market uniqueness | No schedule-level, round-trip, equity-broken-out reachability audit exists (see §1.7) |
| Accessibility, equity, adoption | Equity panel. Reviewed translations. The adoption path runs through CHNA teams and ACOs, who have a mandate and a budget |
| Who benefits + how it scales | Patients (visits happen), clinics (fewer no-shows, recovered capacity), ACOs (quality metrics), transit planners (evidence). Next: any US city's GTFS, then dialysis networks and cancer centers |

### Implementation (Kiro)
| Judging line | How we answer it |
|---|---|
| Variety of Kiro tools | **IDE + CLI + Web + Crew + Mobile**, each with a written reason (§8.1) |
| Depth of a feature | **19 properties**, triple differential testing, PBT → bugfix specs, live in the demo |
| Experimentation + strategic decisions | **5 logged experiments** (§8.11), ADRs, and a journal written by a hook |
| Interesting or surprising integrations | Crew as a **runtime feed monitor** that re-audits schedules. The **"How we know this is right" drawer** turns spec traceability into a UI feature. A **published power**. MCP **resources, prompts and elicitation** |
| Judges must understand usage | Kiro journal, traceability doc, README scorecard, a 30-second Kiro segment in the video |

### Quality & Design
| Judging line | How we answer it |
|---|---|
| Creativity, originality | It turns a trip planner into a **schedule audit with counterfactual fixes**. Escort-aware planning |
| Polished, intuitive, intentional | One map + one grid. Drag-to-fix interaction. Day ribbons explain each red cell |
| Unique public resources | PVTA GTFS, ACS B25044, MassGIS EJ, CMS dialysis, NPPES, AHC HRSN screener, plus **our own rural options table** (and stretch: the first open FRTA mini-feed) |
| Surprising tech combination | **Operations research (RAPTOR + CP-SAT) + equity data + spec-driven correctness**, shown in the UI |
| UI takes the function further | The week grid is something you can only build with the engine. A "what-if" that can be dragged |

---

## 10. Demo video script (under 3:00)
| Time | Shot | Line |
|---|---|---|
| 0:00 | Black screen, then text | *"3.6 million Americans miss care each year because they can't get there."* |
| 0:08 | Map of western MA → click **Holyoke** | *"This is Baystate's GI clinic schedule, as seen from Holyoke without a car."* |
| 0:15 | **The week grid turns red** across morning cells | *"Red means you can't get there and back by bus."* |
| 0:25 | Hover a red cell → **day ribbon** | *"The 8am slot: the last useful bus left at 7:12."* |
| 0:35 | **Drag the GI block 8am → 10am** and the grid goes green | *"Move one block two hours, and N more Holyoke residents can make it."* (computed) |
| 0:50 | Click **"Suggest best schedule"** → 3 changes + impact | *"Or let the optimizer find the best fix."* |
| 1:00 | Rural lens → Franklin County **"no option" layer** | *"In these towns there is no option at all. That's a finding for planners."* |
| 1:10 | Switch to **Visit Planner** → Maria (positive FIT) | *"Now one patient. A colonoscopy after a positive test."* |
| 1:20 | Barrier check (6 taps) → **"Needs an escort — transit won't work."** | *"She'll be sedated. The bus is off the table."* |
| 1:30 | Plan: a slot after her shift inside a volunteer-driver window + **PT-1 pre-filled** + Spanish prep sheet | *"CareLeap builds a plan that can actually happen."* |
| 1:45 | **Phone mock** shows the day-before itinerary + last bus home; printed card | *"The night before, she gets the whole trip."* |
| 1:55 | **Kiro segment:** a PBT counterexample shrinks to a `24:30:00` return trip → bugfix spec → green | *"Kiro's property tests caught a bug that would have stranded patients after midnight."* |
| 2:15 | Click a number → **"How we know this is right"** drawer (requirement → property → test) | *"Every number on screen traces to a spec and a test."* |
| 2:25 | Slack: **Crew alert** "New PVTA schedule → Holyoke reachability ↓" | *"Kiro Crew watches the bus schedule and re-audits automatically."* |
| 2:40 | Closing card | *"CareLeap. Swap in any city's bus data. Every nonprofit hospital in America has to measure access. Now they can."* |

All numbers in the video are computed from real data at build time, never typed in.

---

## 11. Kiro write-up outline (required for submission)
1. **Tools we used and how they differed:** IDE (deep work, PBT), CLI (CI gates, parallel sub-agents, custom agents), Web (Autonomous PRs, Schedule), Crew (runtime monitor), Mobile (steering on the go). Include a table of what each was best and worst at.
2. **Spec-driven development:** which spec types we used where and why, and the spec-vs-vibe experiment with numbers.
3. **Agent hooks:** the 11 hooks, which triggers, what each prevented. "Hooks guard the agent; CI covers humans."
4. **Steering:** the four inclusion modes, and the steering on/off experiment.
5. **MCP:** three custom servers, including resources, prompts and elicitation, and what they made possible (a deterministic demo, Crew re-audits, the agent understanding GTFS).
6. **Property-based testing:** the 19 properties, the triple differential, and the counterexamples found (the midnight bug, and any others) → bugfix specs.
7. **Powers:** the published `careleap` power plus the catalog powers used.
8. **Strategy and experiments:** the 5 experiments, ADRs, and lessons promoted to skills.
9. **Evidence links:** `docs/kiro-journal.md`, `docs/traceability.md`, the README scorecard, PR history.

---

## 12. Risks and how we handle them
| Risk | Mitigation |
|---|---|
| Real clinic schedules aren't public | Use publicly posted hours where available. Otherwise use clearly labelled templates. The product's real input is the health system's own CSV |
| PVTA feed errors / service ends ~Dec 19 | Validate on day 1, pin a validated snapshot, record the demo inside the service window, Crew alarm |
| No FRTA GTFS | Honest rural layer (dial-a-ride / COA / PT-1 / none), hand-verified per town. Stretch: hand-encode 1–2 FRTA routes |
| Walking network complexity | MVP: straight-line × 1.3 detour, max 800 m. Stretch: OSMnx walk graph |
| Reachability ≠ attendance | Say it plainly. That's why the Visit Planner checks every barrier. Measure "reachable visit-hours", not "no-shows prevented" |
| Overclaiming the cancer impact | Cite rates, never invent counts, label every illustrative number |
| Translation compliance | EN + ES reviewed templates only; template-gate hook; content-reviewer agent |
| Scope creep | MVP = Audit (grid + what-if + optimizer) + Planner for **colonoscopy and prenatal**. Dialysis and chemo are stretch |
| Kiro feature claims | Stick to verified features (`kiro-features-verified.md`): PBT is IDE-only, hooks don't run on Web, Crew can't SMS, no `.kiro/workflows/` path |

---

## 13. Submission checklist
- [ ] Public GitHub repo with all source, assets and **run instructions** (`make data && make dev`)
- [ ] **`/.kiro` committed at the repo root**, not in `.gitignore`
- [ ] Demo video **< 3:00**, public on YouTube or Vimeo, no copyrighted music, showing the app running
- [ ] Text description of features and functionality
- [ ] Track: **Healthcare & Biotech, Challenge 3**
- [ ] Kiro write-up (§11) with links to the journal, traceability and scorecard
- [ ] Published `careleap` power link
- [ ] All on-screen numbers computed from cited data; synthetic patients only

---

## 14. What we submit (the final package)

The submission form gets **six things**:

| # | Item | What it contains |
|---|---|---|
| 1 | **Project name + tagline** | *CareLeap: Reachable Care* · "We show health systems which appointments their patients physically can't get to — then plan the high-stakes ones so they happen." |
| 2 | **Track** | Healthcare & Biotech · Challenge 3 ("A referral is not a finished visit") |
| 3 | **Text description** (~300 words) | Problem → the two modes (Clinic Audit, Visit Planner) → data used → who uses it → how it scales. See the draft below |
| 4 | **Demo video** (< 3:00, public YouTube) | The script in §15 |
| 5 | **Public GitHub repo** | All code, `/.kiro` committed at the root, `README.md` with run steps (`make data && make dev`), small data fixtures, and a "Kiro Scorecard" section |
| 6 | **Kiro write-up** | The §11 outline, with links to `docs/kiro-journal.md`, `docs/traceability.md`, the published `careleap` power, and example PRs from Kiro Web |

**What judges will find in the repo:**
- `.kiro/specs/`: 7 specs (requirements-first, design-first, quick, plus bugfix specs from real counterexamples)
- `.kiro/steering/`: all four inclusion modes
- `.kiro/hooks/`: 11 hooks
- `.kiro/agents/`: 4 custom agents
- `.kiro/settings/mcp.json`: 3 custom MCP servers
- `power/careleap/`: the publishable power
- `tests/`: 19 property tests plus the brute-force, Connection Scan and R5 differential tests
- `docs/`: Kiro journal, traceability, decision records, methods and data sources
- `.github/workflows/`: headless Kiro CLI gates

**Draft text description:**
> Millions of Americans miss care because they can't get there, and the visits missed most often are the ones that matter: colonoscopy after a positive test, prenatal care, dialysis. Clinic schedules are set without asking whether patients without a car can arrive and get home the same day.
>
> **CareLeap: Reachable Care** has two modes. **Clinic Audit** takes a specialty clinic's weekly schedule and, using a round-trip transit router over real PVTA bus data, computes what share of car-less adults in each western Massachusetts neighborhood can make each appointment hour. It breaks results out for environmental-justice and limited-English communities, maps rural towns with no transport option at all, and lets planners drag a clinic block or add a satellite day to see the fix. An optimizer suggests the best changes, and a one-click report feeds the hospital's required Community Health Needs Assessment. **Visit Planner** handles high-stakes visits. A 30-second barrier check (work shift, childcare, escort, cost, language) produces a plan that can actually happen. Sedated colonoscopies never get a bus-only plan, MassHealth PT-1 rides are pre-filled, and patients get the itinerary, including the last bus home, the day before.
>
> Built with Kiro: spec-driven development, 19 property-based tests with three independent router checks, 11 agent hooks, three custom MCP servers, a published Kiro power, headless CLI gates, Kiro Web PRs, and Kiro Crew monitoring the bus feed and re-auditing schedules. Swap in any US city's GTFS feed and it works there.

---

## 15. The 3-minute demo: exactly what we show

**Rules for the video:**
- **Screen recording of the real running app** (browser on a laptop, plus the phone mock). No slides except the first and last card.
- **Every number is computed** from the real data at build time. No typed-in numbers.
- **One clinic, one town, one patient.** Baystate GI (Springfield) × Holyoke × "Maria" (synthetic, labelled as such).
- **Pre-baked:** a validated PVTA snapshot, cached reachability cubes, a recorded PBT counterexample run, and a real Crew Slack alert screenshot or capture.
- **Voice-over plus captions** (accessibility). Royalty-free or no music.

### Shot list (3:00 total)

| Time | Length | What's on screen | What we say | Shows off |
|---|---|---|---|---|
| **0:00–0:10** | 10s | Title card: *"3.6M Americans miss care each year because they can't get there."* | Read the line | The problem |
| **0:10–0:25** | 15s | Map of western MA → click **Holyoke** → pick **Baystate GI**. The week grid fills and **morning cells turn red** | "This is Baystate's GI schedule, as seen from Holyoke without a car. Red means you can't get there *and* back by bus." | Value, Design |
| **0:25–0:35** | 10s | Hover a red 8am cell → the **day ribbon** shows the bus legs and the gap | "At 8am, the first bus arrives too late." | Design (explains *why*) |
| **0:35–0:50** | 15s | **Drag the GI block 8am → 10am** and the grid turns green. The counter shows **+N Holyoke residents can make it** | "Move one block two hours, and N more people can reach it." | **Headline insight**, Design |
| **0:50–1:00** | 10s | Click **"Suggest best schedule"** → 3 ranked changes with their impact. Flash the **equity panel** (EJ, limited-English) | "Or let the optimizer find the best fix, for the neighborhoods that need it most." | Value (equity), OR engine |
| **1:00–1:10** | 10s | **Rural lens:** Franklin County with the **"no option at all"** layer | "In these towns there is no bus, no dial-a-ride, nothing. That's a finding for planners." | Value (rural), honesty |
| **1:10–1:15** | 5s | Click **Export CHNA report** → the PDF opens | "One click gives the hospital's required needs-assessment evidence." | Adoption path |
| **1:15–1:30** | 15s | Switch to **Visit Planner** → **Maria**: positive FIT, works 7–3, Spanish → 6-tap barrier check | "Now one patient: a colonoscopy after a positive cancer screening." | Value (high stakes) |
| **1:30–1:45** | 15s | Banner: **"Needs an escort — transit won't work."** Plan: a slot after her shift inside a volunteer-driver window, a **PT-1 request pre-filled**, and a **Spanish prep sheet** | "She'll be sedated, so the bus is off the table. CareLeap builds a plan that can actually happen." | Value, Design |
| **1:45–1:55** | 10s | **Phone mock** shows the day-before itinerary + **last bus home**, plus the printed QR card | "The night before, she gets the whole trip, including how to get home." | Accessibility |
| **1:55–2:15** | 20s | **Kiro IDE:** a property test fails, shrinks to one `24:30:00` after-midnight trip → Kiro creates a **bugfix spec** → fix → green | "Kiro's property-based tests caught a bug that would have stranded patients after midnight, and turned it into a bugfix spec." | **Kiro depth (PBT, specs)** |
| **2:15–2:25** | 10s | Back in the app: click any number → **"How we know this is right"** drawer (source → requirement → property → test status) | "Every number on screen traces back to a spec and a passing test." | **Surprising Kiro integration** |
| **2:25–2:40** | 15s | Quick montage (2–3s each): **Kiro Web PR** → **CLI CI gate passing** → **Crew Slack alert** *"New PVTA schedule → Holyoke reachability ↓"* → the **published power** page | "Kiro Web built modules in parallel, the CLI gates every PR, and Kiro Crew watches the bus schedule and re-audits automatically." | **Kiro variety (IDE, CLI, Web, Crew, Powers)** |
| **2:40–3:00** | 20s | Closing card: logo · *"Any US city's bus data. Every nonprofit hospital must measure access. Now they can."* · repo URL | Read the line | Scale |

### What's real vs. prepared (be upfront in the write-up)
| Real, computed live from data | Prepared ahead of time |
|---|---|
| PVTA routes and timetables, the reachability grid, the drag what-if, the optimizer output, the equity breakdown, the itinerary and last bus home | Clinic schedule template (from publicly posted hours, labelled), "Maria" (a synthetic patient), the rural options table (hand-verified, sources cited), the recorded PBT run, the Crew alert capture |

### Backup plan for the recording
- Record each segment separately, then edit them together. Keep raw takes.
- If the live optimizer is slow, use its cached result. The cube is precomputed either way.
- If the Crew alert doesn't fire on recording day, use the real alert from the most recent feed check (with its timestamp).
- Keep a 2:45 cut ready in case the voice-over runs long. The 3:00 limit is hard: judges may stop watching after that.
