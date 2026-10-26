# Requirements Document

Manual Data Collection (M3). Branch: `M3-Bryan`. Owner: M3. Status: draft.

## Introduction

The CareLeap app depends on hand-collected, every-row-cited data that cannot be
pulled from a single machine-readable feed: posted clinic hours, per-town rural ride
options, the MassHealth PT-1 form schema, barrier-screening questions, the visit-type
logistics rulebook, human-reviewed patient templates, and a fact-check list for the
narrative's `(verify)` claims. This spec defines what each artifact must contain, the
provenance rules it must satisfy, and the human-verification gates that automation
cannot close.

All requirements inherit the non-negotiable guardrails in `AGENTS.md`:
logistics only, synthetic patients only, every number carries source + vintage,
patient-facing text only from human-reviewed templates, no secrets committed.

## Glossary

- **PT-1**: The MassHealth transportation request form whose field schema `/plan` pre-fills via `pt1_prefill`.
- **GTFS**: General Transit Feed Specification; the standard text-file format for transit schedules used by the FRTA mini-feed.
- **FRTA**: Franklin Regional Transit Authority, the agency whose routes are hand-encoded in the mini-GTFS set.
- **FICTIONAL / demo slot**: A clinic slot that is an illustrative template value, labelled not-bookable and never presented as a finding.
- **TODO-VERIFY**: A cell value standing in for data not yet confirmed against a cited source; never an invented value.
- **Provenance**: The `source` plus `vintage` pair that every on-screen number must trace back to; a value lacking it is a defect.
- **MISSING / MANUAL-CHECK**: The closing section each artifact carries, naming the human step required and why it cannot be automated.
- **PRAPARE**: Protocol for Responding to and Assessing Patients' Assets, Risks, and Experiences; a source for barrier-screening questions.
- **AHC HRSN**: Accountable Health Communities Health-Related Social Needs screening tool; a source for barrier-screening questions.
- **DRAFT ES**: Spanish template or question text labelled DRAFT, not treated as patient-facing until human review.
- **Clinic Audit**: The component that computes reachability per clinic-hour from posted clinic schedules.
- **Visit Planner**: The component that offers ride options and pre-fills transportation requests for a patient visit.

## Requirements

### R1 — Clinic schedules
**User story:** As the Clinic Audit, I need posted clinic hours and slots so I can
compute reachability per clinic-hour.

Acceptance criteria (EARS):
- R1.1 WHEN a row is added to `data/manual/clinic_schedules.csv` THE row SHALL carry
  `clinic_id`, `source_url`, and a `status`/`notes` field stating whether it is real or
  a labelled demo assumption.
- R1.2 IF a slot is a demo/template value THEN it SHALL be labelled "FICTIONAL" /
  "illustrative" and marked not-bookable, never presented as a finding.
- R1.3 THE `clinic_id` values SHALL match the keys used by `data/cache/cube.parquet`
  and the `/audit` API (docs/contracts.md).

### R2 — Rural options
**User story:** As the Visit Planner, I need per-town ride options so I can offer an
escort-aware or demand-response ride where transit fails.

Acceptance criteria
- R2.1 THE file `data/manual/rural_options.csv` SHALL contain one row per Franklin and
  Hampshire County town with columns: `town, dial_a_ride, coa_driver, pt1, hours,
  source_url, verified_by, date`.
- R2.2 WHERE a value is not confirmed against a cited source THE cell SHALL read
  `TODO-VERIFY` and `verified_by` SHALL be empty — never an invented value.
- R2.3 WHEN a `coa_driver` or `hours` value is filled THEN `verified_by` and `date`
  SHALL be set to the human who confirmed it (e.g. by phone).

### R3 — PT-1 form fields
**User story:** As the Visit Planner, I need the PT-1 field schema so `/plan` can
pre-fill a transportation request.

Acceptance criteria:
- R3.1 THE file `data/manual/pt1_fields.json` SHALL list each PT-1 field with `key`,
  `label`, `type`, `required`, and a `verified` flag.
- R3.2 THE field `key`s SHALL be the keys `/plan` writes into `pt1_prefill`
  (docs/contracts.md §3).
- R3.3 IF a field is reconstructed rather than confirmed against the live form THEN
  `verified` SHALL be `false` and the reason recorded in MISSING_MANUAL_CHECK.

### R4 — Barrier questions
**User story:** As the Visit Planner, I need six logistics barrier questions so the
30-second barrier check maps to plan options.

Acceptance criteria:
- R4.1 THE file `data/manual/barrier_questions.yaml` SHALL contain exactly six
  questions covering transport, work shift, childcare, escort, cost, language/worry.
- R4.2 EACH question SHALL have an `en` and an `es` field and a `maps_to` equal to a
  `/plan` barrier key (`has_transport, work_shift, childcare, has_escort, cost_worry,
  language`).
- R4.3 EACH question SHALL name a `source` (AHC HRSN or PRAPARE) and a `verbatim` flag;
  IF `verbatim` is false THEN a TODO-VERIFY note SHALL be present.
- R4.4 THE `es` text SHALL be labelled DRAFT and SHALL NOT be treated as patient-facing
  until human review.

### R5 — Visit rulebook
**User story:** As the planner engine, I need visit-type logistics as DATA so no visit
logic is hard-coded.

Acceptance criteria:
- R5.1 THE file `planner/visit_rules.yaml` SHALL have an entry per visit type
  (colonoscopy, prenatal, dialysis, chemo/infusion) with `duration`,
  `escort_required`, `telehealth_ok`, `prep`, `recurrence`.
- R5.2 WHERE `escort_required` is true (e.g. colonoscopy) THE rule SHALL be the basis
  for the planner NEVER offering a transit-only plan for that visit type.
- R5.3 WHERE `telehealth_ok` is false THE planner SHALL NOT offer a telehealth swap.
- R5.4 ANY value not sourced from steering SHALL be labelled an assumption inline and
  listed in MISSING / MANUAL-CHECK.

### R6 — Patient templates (EN/ES)
**User story:** As a patient, I need itinerary and prep text I can read, in my language,
that a human approved.

Acceptance criteria:
- R6.1 THE directory `planner/templates/{en,es}/` SHALL contain `itinerary.md` and
  `prep_sheet.md`, written at a grade-6 reading level, using `{{token}}` placeholders
  and NO real patient data.
- R6.2 THE manifest `planner/templates/signoff.json` SHALL record per template:
  `path, lang, reviewer, reviewed, date, reading_level_target`.
- R6.3 EVERY template SHALL ship `reviewed: false` until a named human reviewer signs
  off (45 CFR 92.201(c)(3)).
- R6.4 NO template SHALL contain clinical advice or eligibility text.

### R7 — Fact-check list
**User story:** As the "How we know this is right" drawer, I need every `(verify)`
claim traced to a source or flagged.

Acceptance criteria:
- R7.1 THE file `docs/sources.md` SHALL contain one entry per `(verify)` claim in
  `final_plan/FINAL-careleap.md`.
- R7.2 EACH entry SHALL carry claim text, a candidate source (name + URL where known),
  vintage, and a status of `verified | needs-manual-verification | unsourced`.
- R7.3 NO URL SHALL be fabricated; an unconfirmed source SHALL be a domain-level
  pointer with a "locate, do not assume" note.

### R8 — FRTA mini-GTFS (stretch)
**User story:** As the engine, I need 1–2 hand-encoded FRTA routes to route rural trips.

Acceptance criteria:
- R8.1 THE directory `data/manual/frta_minigtfs/` SHALL hold a valid minimal GTFS set
  (agency, stops, routes, calendar, trips, stop_times).
- R8.2 GTFS times past midnight SHALL be encoded as `24:00:00`+ and SHALL NOT be wrapped
  (steering/tech.md).
- R8.3 UNTIL timetables are transcribed, the directory MAY contain only a scaffold +
  README naming exactly what must be hand-encoded and why.

### R9 — Provenance (cross-cutting)
- R9.1 ANY on-screen number derived from these files SHALL be traceable to a `source`
  with a `vintage`; a value with no provenance is a defect.
- R9.2 EACH artifact SHALL end with a MISSING / MANUAL-CHECK section naming the human
  step required and the reason it cannot be automated.
