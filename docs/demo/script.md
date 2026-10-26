# CareLeap — 3-minute demo script

Run on the frozen snapshot (`make demo` + `cd web && VITE_API_BASE=/api npm run dev`,
open http://127.0.0.1:5173). Every number below is what the app computes on that
snapshot (PVTA + FRTA GTFS, ACS 2024 5-year). Clinic appointment slots are an
**illustrative** demo schedule; say so if asked.

Target: 2:50. Timings are cumulative.

---

## 0:00 – 0:20 · The problem

**Screen:** CareLeap home → Audit. Clinic: **Baystate GI / Endoscopy**.

> "A referral isn't a finished visit. In western Massachusetts, tens of thousands of
> adults don't have a car, so whether they get their colonoscopy depends on the bus
> schedule. CareLeap shows a clinic which of its own appointment hours its patients can
> physically get to — there and back — and then plans the visits that matter."

## 0:20 – 0:50 · The audit: Hampshire County

**Screen:** Community → **Hampshire County**. Point at the Monday 7am cell (0%), then 8am
(2%), then the midday cells (~57%).

> "Each cell is the share of car-less adults in Hampshire County — 11,166 people — who can
> take the bus to this clinic, arrive ten minutes early, and get home the same day. That's
> computed from the real PVTA timetable, one round trip per neighborhood per hour.
> Look at 7am: zero. Not low — zero. The first buses out of Hampshire County don't reach
> Springfield in time. Yet that's exactly when endoscopy suites like to start."

(Optional: hover a cell to show the day ribbon — outbound, appointment, return, last bus home.)

## 0:50 – 1:25 · Suggest a change, then move the block

**Screen:** Scroll to **Suggest changes** → run it. Top suggestion: **move Mon 7:00 → 10:00**.
Drag the 7am block to 10am. The "Block moved" card shows **0% → 57% (+57)**.

> "CareLeap's optimizer looks for the smallest schedule changes with the biggest gain, and
> its first suggestion is: move the Monday 7am block to 10am. Let's do it."
>
> *(drag)*
>
> "Plus 57 points. Same clinic, same staff, same number of appointments — one block moved
> three hours, and 6,344 car-less adults in Hampshire County go from zero ways to get there
> to a bus trip that gets them there and home. No new buses, no new budget. That's the kind
> of change a scheduling manager can make on Monday morning, and the kind of evidence a
> hospital needs for its Community Health Needs Assessment."

## 1:25 – 2:20 · The Visit Planner: Maria

**Screen:** Visit Planner → **Colonoscopy** → barrier check:
- Reliable way to get there and back? **No**
- Do work hours make some times hard? **Yes** (7am – 3pm)
- Caring for a child or someone else? **No**
- Can another adult come along and help get home? **No**
- Does the cost worry the patient? **No**
- Language: English (or Spanish to show the ES sheet)

> "Now one patient. Maria has a positive stool test and needs a colonoscopy. She works
> seven to three, has no car, and no one to take her home."
>
> *(results)*
>
> "Colonoscopy uses sedation, so she needs an adult to take her home. CareLeap never offers
> a bus-only plan for that — it offers an escort-aware ride. The best time is 4:30pm, after
> her shift, and the same trip works any weekday. Here's why a ride and not the bus: the bus
> estimate is six buses and almost six hours door to door, with the last bus home at 7:56."
>
> *(open the prep sheet)*
>
> "She gets a prep sheet in her language — written by people and reviewed by a bilingual
> reviewer, never machine-translated on the fly. Her trip: check in by 4:20, done around
> 7:30, an adult rides home with her. And the MassHealth PT-1 ride form is already drafted,
> with the clinic address filled in — staff complete the rest."

**Point at a provenance chip** (optional, 5 s):

> "Every number here traces back to a requirement in our spec and the test that checks it."

## 2:20 – 2:50 · Built with Kiro

**Screen:** Kiro IDE → Specs panel → `bug-csa-transfer-cap`; then terminal running
`pytest tests/property/test_csa_transfer_cap.py -q` (green); flash Hooks and Steering.

> "We built CareLeap spec-first in Kiro: eleven specs, eleven hooks, property-based tests on
> the router. Running our differential tests against the real bus network caught a bug in
> both of our test oracles — the production router was right, and Kiro turned the
> counterexample into a bugfix spec. That's why we trust the numbers you just saw."
>
> "CareLeap: see which appointments patients can't reach, fix the schedule, and plan the
> visits that matter."

---

## Numbers to have ready (snapshot 2026-10-26)

| What | Value |
|---|---|
| Car-less adults, all three counties | 55,901 |
| Car-less adults, Hampshire County | 11,166 |
| Baystate GI, Hampshire, Mon 7am / 8am / 10am | 0% / 2% / 57% |
| Move Mon 7am → 10am (Hampshire) | 0% → 57%, +57 points, 6,344 people |
| Baystate GI, Franklin County, any hour | 0% (backup beat) |
| Rural lens: assisted-only block groups | 86 (3,270 car-less adults) |
| Maria: best ride | weekdays 4:30pm; bus estimate 6 buses, 350 min, last bus home 7:56pm |

## Don'ts
- Don't call the slot times real clinic hours — they are an illustrative schedule.
- Don't say "eligible" or give clinical advice; CareLeap does logistics only.
- Keep the 11-option list collapsed (top 3 + prep sheet are enough).
