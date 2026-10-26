# CareLeap: Reachable Care — submission text

> **Track:** Healthcare & Biotech · **Challenge 3:** "Improving healthcare access and
> coordination" ("A referral is not a finished visit").
> Draft owner: M3. Every on-screen number is computed and carries a source; template
> values are labelled "illustrative". Synthetic patients only — no real PHI.

## Tagline
We show western Massachusetts health systems **which of their own appointments their
patients physically can't get to by bus** — then plan the high-stakes visits so they
actually happen.

## Short description (≈60 words)
CareLeap: Reachable Care audits a clinic's whole weekly schedule for **round-trip**
transit reachability, neighborhood by neighborhood, and shows which schedule change fixes
the gap. Then, for high-stakes visits — colonoscopy after a positive FIT, prenatal,
dialysis, chemo — it runs a 30-second barrier check and builds a plan that can actually
happen: a reachable slot, an escort-aware ride, a telehealth swap, or an in-language prep
sheet.

## The problem
A referral is not a finished visit. About **3.6 million Americans** miss or delay care each
year because of transportation (Wallace et al.). The visits that matter most are the ones
that get missed: after a positive FIT stool test, **about half** of patients don't complete
the follow-up colonoscopy within six months (50% in a 2,157-patient cohort, PubMed
39843790) — that's how a screen-detected cancer becomes a late-stage cancer. Clinic hours
are set around staff and rooms, not around whether a patient without a car can arrive **and
get home**. An 8:00am slot can be "on a bus route" and still be impossible.

## What it does
**① Clinic Audit (the headline).** For every clinic hour in a weekly schedule, it computes
what share of car-less adults in each neighborhood can get there *and back* by bus. It
shows where the schedule fails whole communities — and which change fixes it: shift a block
or add a satellite day. Export a CHNA-ready report.

**② Visit Planner (the follow-through).** For a high-stakes visit it runs a barrier check
(transport, work shift, childcare, escort, cost, language) and outputs a plan: a reachable
slot that fits the patient's shift, an escort-aware ride with a PT-1 pre-fill, a telehealth
swap where allowed, or an in-language prep sheet — with the last bus home, sent the day
before.

## Why it's new
No tool today computes **round-trip** transit reachability for a clinic's whole weekly
schedule against the neighborhoods it serves. Google Maps plans one trip; we audit
**thousands of visit-hours at once** and show what a schedule change would do. Closed-loop
referral tools track referrals but don't plan transit or test clinic schedules.

## How it works
A round-trip transit router (RAPTOR in NumPy over real GTFS) powers both modes, cross-checked
against two independent oracles (Connection Scan + brute force) with property-based tests.
Reachability means an outbound journey arriving before check-in **and** a same-day return
after the visit ends — within real limits (≤2 transfers, ≤2h each way, ≤800m walk). Every
number traces back through a requirement and a test to its source ("How we know this is
right").

## Guardrails (non-negotiable)
- **Logistics only** — never a clinical or eligibility decision. "Your care team decides
  your care."
- **Synthetic patients only.** No real PHI.
- **Every number carries a source and vintage;** template numbers are labelled illustrative.
- **Patient-facing text comes only from human-reviewed templates (EN + ES)**, per
  45 CFR 92.201(c)(3) — no live machine translation to patients.
- **Reachability is not attendance.** We measure reachable visit-hours, not no-shows
  prevented; the Planner checks every barrier, not just transport.

## Western Mass focus
Built for Franklin and Hampshire counties and the rural Hilltowns, using real PVTA and FRTA
transit data, real posted clinic hours, and per-town ride options (FRTA demand response,
PVTA Senior Dial-A-Ride, Council on Aging drivers, MassHealth PT-1) — the places a
car-centric tool leaves out.
