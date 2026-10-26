# How we used Kiro — CareLeap: Reachable Care

CareLeap tells western-Massachusetts health systems which appointment hours their
car-less patients can actually reach **and get home from** by bus, and plans the
high-stakes visits (colonoscopy, prenatal, dialysis, chemo) so they can happen. A wrong
routing answer strands a patient, so we treated Kiro as a way to build a
**safety-relevant** system, not a fast demo. Every claim below points at a file in this
repo, and every number is one we reproduced.

Evidence lives in `.kiro/` (11 steering files, 13 specs, 8 IDE hooks, 5 CLI agents, MCP
config), `docs/kiro-journal/` (per-person Kiro logs), `docs/decisions/` (ADRs and
experiments), and the README's **Kiro Scorecard**.

---

## 1. Which Kiro tools we used, and how they differed

| Tool | What we used it for | What it was good at | Limits we hit |
|---|---|---|---|
| **Kiro Crew** | Most implementation. Parallel agents on disjoint files (M1 Phase A: 4 agents; Phase B: 5 agents), long multi-step tasks (multi-feed router, equity intervals, `/report`), two no-LLM cron jobs (6-hourly PVTA feed heartbeat, 14-day feed-expiry alarm, `ops/crew/`). | Long autonomous runs with memory across sessions; parallel fan-out; real shell, so it ran the full test suite, the GTFS validator and the data build itself. | **File hooks do not fire in Crew.** We closed the gap with an always-on steering rule (§4). Thin "lite" sub-agents sometimes *claimed* file writes they never made, so the parent re-checked every claimed file and test against disk before merging. |
| **Kiro CLI** (`kiro-cli`) | Headless runs: the steering on/off experiment (ADR 003), the `content-reviewer` agent on the CHNA report, `kiro-cli agent validate` in CI, a `release-checker` gate job. Custom agents in `.kiro/agents/`. | Scriptable and repeatable. Least-privilege agents (`content-reviewer` can only `fs_read`, with network and writes denied). CLI agent hooks (`preToolUse` exit 2 = block). | `--no-interactive` cannot approve tools, so one experiment arm was write-denied (documented as a confound). An agent whose resource glob pulled 14 MB of data overflowed its context; we narrowed it to the content files. |
| **Kiro IDE** | The 8 `.kiro.hook` files (fast router tests on `engine/**` save, axe on `web/**` save, traceability after tasks, journal hooks). Specs and steering authored in the IDE's spec/steering layout. | Event hooks on save/task-finish give instant local feedback. | Hooks fire only on agent/IDE edits, so **CI repeats every hook check**; the hook is an early signal, never the only gate. |
| **Kiro Web** | Issues [#8](https://github.com/SSJ-07/hackachusetts/issues/8), [#9](https://github.com/SSJ-07/hackachusetts/issues/9), [#10](https://github.com/SSJ-07/hackachusetts/issues/10) filed for Web Autonomous (EN/ES i18n, phone itinerary, QR card). | Good fit for self-contained UI units with an issue → PR flow; it never auto-merges. | IDE-vs-Web comparison protocol is fixed (ADR 005), but the run is still pending. We do not claim a result. |

**How they differed in practice:** Crew was the workhorse for depth and parallelism. The
CLI was the tool for anything that had to be **repeatable** (experiments, CI, a
reviewer we could re-run). The IDE carried the event-driven guardrails. Web was reserved
for isolated UI modules.

---

## 2. Spec-driven development

### How we structured specs
Every feature gets `.kiro/specs/<name>/requirements.md` (EARS `SHALL` clauses with
**stable ids**: `MF-n`, `VP-n`, `SO-n`, `RC-n`, `AR-n`, `RP-n`), then `design.md`, then
`tasks.md`. Each task cites the ids it satisfies, and tests cite the ids they defend.
That id chain is what lets a judge trace an on-screen number to a requirement, a
property and a test.

We used **all three spec types**, on purpose:

| Type | Specs | Why |
|---|---|---|
| Requirements-First | `raptor-router`, `schedule-optimizer`, `visit-planner`, `multi-feed`, `access-resources-mcp`, `audit-report-pdf`, `manual-data`, `ui-planner` | New features: write the contract first, so the tests exist before the code. |
| Design-First | `reachability-cube` | Retrofitting a spec onto code that already existed. |
| Bugfix | `bug-transfer-limit`, `bug-csa-transfer-cap` | Written from a real counterexample, so the regression test fails before the fix and passes after. |
| Quick spec | `connection-scan`, `ui-week-grid` | Low-risk second implementation / UI. |

### How specs improved the process
- **Contracts first.** `docs/contracts.md` is pulled into every session by
  `structure.md` (`#[[file:docs/contracts.md]]`). When we added `equity_ci` to `/audit`,
  the strict contract shapes (`extra="forbid"`) failed until the spec, the contract doc
  and the contract tests were updated **in the same change**. The spec process made
  shape drift impossible to ship silently.
- **Specs carry the hard parts of the domain.** The `multi-feed` spec pinned three
  properties before any code: "loading FRTA never makes a PVTA-only trip worse", "every
  merged trip keeps its agency", "results are identical when FRTA has no service that
  day". All three now run on the real feeds.
- **Specs record what *not* to do.** The `reachability-cube` design records a discarded
  "fast" profile-search shortcut that under-reported reachability (**1.2% flat vs the
  true ~31%**). It is a requirement now, so nobody can reintroduce it.
- **Gaps are labelled, never guessed.** `manual-data/tasks.md` marks human-only steps
  `[MANUAL]` with the reason (a PDF that blocks scripts, a legally required bilingual
  reviewer). The `plan_b` templates ship `reviewed:false`, so the planner returns no
  plan-B text until a human signs.

### Measured: Requirements-First vs Design-First (ADR 002)
| | Requirements-First (`schedule-optimizer`) | Design-First (`reachability-cube`) |
|---|---:|---:|
| Requirement ids cited directly in test code | **9 of 16** | **0 of 24** |
| Tasks closed | 9/9 | 9/12 at the time |

Our working rule: **Requirements-First for new features, Design-First to retrofit.**
(Single sample, labelled as such in the ADR.)

### Compared to vibe coding
The one place we skipped a full spec (the rural lens) we still went **contract-first**:
shapes went into `contracts.md` and a test pinned them before the UI. Our clearest
vibe-style failure was delegation without a spec: lite sub-agents reported "4 success"
on research-heavy data files and wrote **zero** files. After that, every delegated task
got a written goal, inputs, owned files and a verifiable output, and the parent checked
disk state. The controlled spec-vs-vibe run (ADR 004) has a fixed protocol but has not
been run yet. We do not report a number for it.

---

## 3. Agent hooks

**11 of 11 planned hooks exist** (`.kiro/hooks/README.md`, 35 unit tests for the hook scripts).

| Hook | Trigger | What it automates |
|---|---|---|
| block-live-routing | CLI `preToolUse` (shell, web) | **Exit 2** on Google Maps / OSRM / Mapbox calls, returning "use gtfs-mcp". Keeps every route deterministic and on cached GTFS. |
| guard-templates | CLI `preToolUse` (write) | **Blocks** a write to `planner/templates/**` unless `signoff.json` changes too. This enforces the 45 CFR 92.201(c)(3) human-review rule in tooling, not just in policy. |
| remind-templates | CLI `userPromptSubmit` | Reminds the agent that patient text comes only from reviewed templates. |
| log-provenance | CLI `postToolUse` (`@gtfs-mcp`) | Appends every routing call to `docs/provenance-log.jsonl`. |
| feed-expiry | CLI `agentSpawn` + IDE session start | Warns when the PVTA feed ends within 14 days or the data is over 7 days old. |
| engine-fast-tests-on-save | IDE `fileEdited engine/**` | Runs the property, golden and differential router suite on every engine save. |
| a11y-on-web-save | IDE `fileEdited web/**` | Runs axe. It found **2 serious a11y bugs** on its first runs. |
| validate-gtfs-on-create | IDE `fileCreated` | Structural GTFS check when a feed lands. |
| traceability-post-task | IDE `postTaskExecution` | Regenerates `docs/traceability-matrix.md` (requirement → test). |
| journal hooks (×2) | IDE save of spec/steering + task finish | Appends to the per-person Kiro journal. |

**How they helped:** the two blocking hooks turn our two non-negotiables (no live
routing APIs, no unreviewed patient text) from "please remember" into "cannot happen".
The save hooks shortened the loop on the router to seconds. Because file hooks do not
fire for merges, CI runs the same checks. Because they do not fire in Crew, journaling
moved into steering (§4).

---

## 4. Steering

**11 steering files, using every inclusion mode:**

| Mode | Files | Why that mode |
|---|---|---|
| `always` | `product.md` (guardrails), `tech.md` (provenance and time rules), `structure.md` (module boundaries + `#[[file:docs/contracts.md]]`), `journaling.md` | Rules that must hold in every session. |
| `fileMatch` | `gtfs-domain.md` → `engine/**`; `accessibility.md`, `ui-style.md` → `web/**`; `equity-and-language.md` → templates + web content | Domain rules load only where they matter, keeping context small. |
| `auto` | `visit-rules.md` (pulls in `planner/visit_rules.yaml`), `optimizer-notes.md` | Loaded when the task is about that topic. |
| `manual` | `demo-script.md` | Only when recording the video. |

**Strategies that made the biggest difference:**
1. **Guardrails as always-on steering, mirrored in code.** "Logistics only", "every
   number has a source and vintage", "synthetic patients only" sit in `product.md` *and*
   in `planner/guardrails.py`, which raises on clinical or eligibility wording. Every
   MCP response, planner option, plan-B text and report page runs through that check.
2. **Pull the contract into steering with `#[[file:]]`.** Agents saw the exact API and
   file shapes in every session, which is why four people's parallel work fit together.
3. **Steering as a hook substitute.** Crew has no file hooks, so `journaling.md` tells
   every agent to log its own verified work with `scripts/log_kiro.py`. That is how
   `docs/kiro-journal/` filled up from Crew sessions.
4. **Defence in depth beats one file.** Experiment ③ (ADR 003) deleted `gtfs-domain.md`
   and asked Kiro to re-implement the GTFS time parser. Both arms kept the midnight rule
   (`24:30:00` → 88200, never wrapped), and both passed 12/12, because the rule is *also*
   pinned by `tests/property/test_midnight.py` and `tech.md`. Lesson: put the rule in
   steering for the agent, and in a test so it survives anything.

---

## 5. MCP

Three project MCP servers (`mcp/`, registered in `.kiro/settings/mcp.json`). All are
wired to real code; no stubs remain.

| Server | Tools / resources | What it enabled |
|---|---|---|
| `gtfs-mcp` | `round_trip`, `plan_trip`, `service_changes`, `validate_feed` | One deterministic router every agent calls, on cached GTFS. With the block-live-routing hook, no agent can quietly use a live maps API and produce numbers nobody can reproduce. Every call is logged for provenance. |
| `reach-mcp` | `reachability`, `what_if`, `suggest_schedule` (+ cached cubes) | Agents ask "who can reach this clinic at 8 am, and what if we move the block?" straight from the cube and the CELF optimizer, so the same numbers back the UI and the agent. |
| `access-resources-mcp` | `rural_options`, `pt1_prefill`, `visit_rules` + resource `access://rural-options` | Hand-verified manual data (rural ride options, MassHealth PT-1 fields, visit rulebook) for agents. **Every response carries `source_url` + `vintage` and passes the logistics-only guardrail.** It refuses non-synthetic patient IDs. |

We also registered third-party servers: **GitHub** (issues/PRs), **Playwright**
(browser + a11y runs) and **AWS Documentation**. The MCP layer made two things possible
that would otherwise be hard: (1) agents doing *analysis* on our own verified engine
rather than guessing, and (2) provenance by construction, since every number an agent
quotes came through a tool that stamps its source.

---

## 6. Property-based testing

PBT (Hypothesis) and differential testing are the core of our correctness story.
**Bugs PBT and differential tests caught that unit tests missed:**

| Bug | How it was caught | Why unit tests missed it |
|---|---|---|
| **Transfer limit** — RAPTOR boarded from stops reached in the same round, allowing more than 2 transfers | Golden trip on the real PVTA feed (4 out / 6 back buses), then a chain-feed property that **shrank to n=4**, pinned as `@example` → Bugfix spec `bug-transfer-limit` | Hand-written feeds never had chains long enough. |
| **Both oracles wrong** — CSA *and* brute force kept one label per stop, which is invalid under a transfer cap (time × buses is bi-criteria) | Differential test RAPTOR == CSA on the **real** feed: CSA lost **21 stops** RAPTOR reached → Bugfix spec `bug-csa-transfer-cap` | Two agreeing oracles looked like proof. Only the real network had the trap shape. |
| Origin foot-transfers skipped; CSA transfer-unlock | RAPTOR == CSA == brute force over 120 random feeds | Edge cases appear only in random topologies. |
| Equity intervals: float cancellation, and huge margins for tiny groups | Properties "every interval contains its estimate" and "more error never narrows the interval" shrank to one-block-group cases | Hand examples used round numbers. |

**Requirements we put under PBT:** causality / FIFO / transfer minimums / ≤2 transfers;
**midnight safety** (GTFS times ≥ 24:00 never wrap); RAPTOR == CSA == brute force;
`latest_departure` agrees with forward `earliest_arrival` (626 reverse results, 0
violations); **multi-feed** never-worse, agency kept, no-service identity (on real
PVTA + FRTA); optimizer **never worse** and **greedy ≥ (1 − 1/e) × CP-SAT optimum**;
planner safety: **escort ⇒ never transit-only**, no slot overlaps the work shift
including travel, telehealth only if allowed, no clinical or eligibility text;
**volunteer-driver rides only inside a sourced window**; **plan B only from signed
templates**; equity **intervals contain their point estimate** and stay in [0, 1].

Current totals: **535 passed** pytest on the full local run (Python 3.12, with the data
caches present), plus 20 vitest, 2 Playwright e2e and 2 axe runs.

---

## 7. Kiro powers

We **built and published our own power**: `power/careleap/` (`plugin.json`, an
`mcp.json` that launches `gtfs-mcp` + `reach-mcp` via `CARELEAP_HOME`, and two skills:
`clinic-access-audit` and `gtfs-debugging`). It is public at
[github.com/SSJ-07/slot-to-stop-power](https://github.com/SSJ-07/slot-to-stop-power) (v0.1.0,
published under the project's old name).

We test-installed it into a **fresh, empty workspace** and drove it over MCP stdio
(`initialize`, `tools/list`, a real `round_trip` call). That found a real bug: the tool was
exposed as `round_trip_tool`, not the contract name `round_trip`. Fixed before release.

**Third-party tooling we would not otherwise have wired in:** GitHub, Playwright and AWS
Docs MCP servers; MobilityData **gtfs-validator** v8.0.1 (reports and triage in
`docs/validation/`); OR-Tools **CP-SAT** as the exact oracle for the optimizer; the Census
ACS API, including published margins of error for the equity intervals. We did not install
catalog powers (e.g. Amazon Location, CDK/SAM); our deploy and routing needs were covered
by our own power and MCP servers.

---

## What we would tell another team

1. **Make the spec ids load-bearing.** Cite them in tests, or traceability is a story.
2. **Put every non-negotiable in three places:** steering (so the agent knows), a hook
   (so the tool refuses), and a test or CI step (so it survives merges and other tools).
3. **Differential testing is only as strong as its inputs.** Run it on real data. Our two
   oracles agreed and were both wrong until the real PVTA network exposed it.
4. **Never trust an agent's "done".** Verify disk state and re-run the tests. Our journal
   rule is "log only what was verified."
