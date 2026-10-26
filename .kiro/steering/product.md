---
inclusion: always
---

# Product — CareLeap: Reachable Care

## Mission
Show western Massachusetts health systems which of their own appointments their patients
physically can't get to by transit, then plan the high-stakes visits so they happen.

## Two modes (one routing engine)
1. **Clinic Audit** — for every clinic hour in a weekly schedule, compute what share of
   car-less adults in each neighborhood can get there *and back* by bus. Drag a block or
   add a satellite day to see the fix. Export a CHNA-ready report.
2. **Visit Planner** — for high-stakes visits (colonoscopy after a positive FIT, prenatal,
   dialysis, chemo), run a barrier check and build a plan that can actually happen: a
   reachable slot, an escort-aware ride with PT-1 pre-fill, a telehealth swap, or an
   in-language prep sheet.

## Users
Clinic operations managers, CHNA / community-benefit teams, MassHealth ACO planners,
referral coordinators / navigators, regional transit planners, and patients (car-less,
limited-English, shift-working, rural).

## Guardrails (non-negotiable — enforced in code and hooks)
- **Logistics only.** Never make a clinical decision or decide eligibility.
  "Your care team decides your care."
- **Synthetic patients only.** No real PHI anywhere.
- **Every number carries a source and vintage.** Numbers from templates are labelled
  "illustrative" and never presented as findings.
- **Patient-facing text comes only from human-reviewed templates** (EN + ES), per
  45 CFR 92.201(c)(3). No live machine translation to patients.
- **Reachability is not attendance.** We measure reachable visit-hours, not no-shows
  prevented. The Visit Planner checks every barrier, not just transport.
