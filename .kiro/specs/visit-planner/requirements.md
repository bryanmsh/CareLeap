# visit-planner — Requirements (EARS)

> Feature spec, Requirements-First. Owner: M4 (solver + API); M3 owns the rulebook,
> PT-1 field list and templates. Turns a synthetic patient's barrier answers, a visit
> type and candidate clinic slots into a ranked "can this visit happen?" plan.
> Output shape fixed by `docs/contracts.md` §3 (`POST /plan`). Transit check calls
> `engine.round_trip` (§2), stubbed until a real feed is loaded.

Each requirement has a stable id (`VP-n`) referenced by `/provenance` and tests.

## Inputs
- **VP-1 (inputs).** THE planner SHALL accept a synthetic patient (`id`, `origin_bg`,
  `lang`), a `visit_type` and barrier answers (`has_transport`, `work_shift`,
  `childcare`, `has_escort`, `cost_worry`, `language`) in the `POST /plan` request shape.
- **VP-2 (rules are data).** THE planner SHALL read visit logistics (`duration`,
  `escort_required`, `telehealth_ok`, `prep`, `recurrence`) from `planner/visit_rules.yaml`
  and SHALL NOT hard-code visit logic.
- **VP-3 (unknown is not false).** WHEN any of `duration`, `escort_required`,
  `telehealth_ok` or `prep` is `null` for the visit type, THE planner SHALL return a single
  `none` option asking for navigator follow-up, and SHALL NOT read `null` as `0` or `false`.
- **VP-4 (unknown visit type).** WHEN `visit_type` is not in the rulebook, THE API SHALL
  respond 422 and list the known visit types.

## Hard rules
- **VP-5 (escort rule).** WHEN `escort_required` is true, THE planner SHALL NOT return any
  `slot` (transit-only) option and SHALL offer escort-aware `ride` options instead.
- **VP-6 (shift rule).** THE planner SHALL NOT recommend a `slot` or `ride` whose
  door-to-door window (leave home → arrive home) overlaps the work shift. Overnight shifts
  and trip times `>= 86400` SHALL be handled without wrapping.
- **VP-20 (childcare window).** WHEN a `childcare_window: [start, end]` is given, THE planner
  SHALL treat it as a second no-go band and SHALL NOT recommend a `slot` or `ride` whose
  door-to-door window overlaps it, by the same rule as VP-6 (overnight windows and trip
  times `>= 86400` handled without wrapping). An omitted window applies no time constraint.
- **VP-7 (no travel estimate).** WHEN a slot has no complete round trip, THE planner SHALL
  NOT offer it as a `slot`; it MAY offer it as a `ride` only when no work shift is stated.
- **VP-8 (telehealth rule).** THE planner SHALL offer a `tele` option only when
  `telehealth_ok` is true.
- **VP-9 (prep).** WHEN `prep` is true and at least one attendable option exists, THE
  planner SHALL add a `prep` option carrying the preferred language.
- **VP-10 (nothing viable).** WHEN no `slot`, `ride` or `tele` option survives, THE planner
  SHALL return exactly one `none` option, flagged for a navigator, with a reason that says
  which check failed (no candidates, no transit, shift conflict, escort, unverified rules).

## Output
- **VP-11 (contract shape).** THE API SHALL return `{options[{kind, details, why}],
  itinerary{out_legs, ret_legs, last_bus_home, plan_b}, pt1_prefill}` per contracts.md §3.
- **VP-12 (ranking).** THE planner SHALL order options by kind (`slot`, `ride`, `tele`,
  `prep`, `none`), then by door-to-door time, then by date, start and clinic id.
- **VP-13 (determinism).** GIVEN identical inputs in any candidate order, THE planner SHALL
  return an identical plan.
- **VP-14 (itinerary).** WHEN the top option is a `slot`, THE itinerary SHALL carry that
  slot's legs and `last_bus_home`; otherwise it SHALL be empty.
- **VP-15 (PT-1 pre-fill).** WHEN a `ride` is offered and a PT-1 field list is available,
  THE planner SHALL pre-fill each field from its declared source for the top ride, and
  leave fields with no source `null` for a person to complete.

## Safety
- **VP-16 (logistics only).** THE planner SHALL NOT emit clinical advice or eligibility
  wording; output failing the check SHALL be withheld (HTTP 500), never sent.
- **VP-17 (synthetic only).** THE planner SHALL be exercised only with synthetic patients.
- **VP-18 (no silent mocks).** WHEN real data is selected (`CARELEAP_DATA=real`) and a
  source has not landed, THE API SHALL respond 503 rather than fall back to mock data.
- **VP-19 (purity).** THE solver SHALL NOT import FastAPI, Pydantic or `api/`, and SHALL
  make no I/O; the transit check is injected.

## Not yet covered (open)
- **VP-21 (cost, has_transport).** How `cost_worry` and `has_transport` change the options.
- **VP-22 (recurrence).** Plan the repeating pattern (e.g. dialysis per week).
- **VP-23 (plan B).** `plan_b` text from human-reviewed templates only (M3).
- **VP-24 (volunteer-driver windows).** Ride slots inside driver windows (needs M3 data).

## Traceability
| Requirement | Verified by |
|---|---|
| VP-3 | `tests/unit/test_planner_solver.py::test_unverified_rule_hands_off_to_navigator`, `test_planner_data_loaders.py::test_null_means_unknown_not_false` |
| VP-4 | `tests/contract/test_api_contracts.py::test_plan_unknown_visit_type` |
| VP-5 | `tests/property/test_planner_properties.py::test_p15_escort_never_transit_only`, `test_planner_solver.py::test_escort_visit_gets_ride_not_slot` |
| VP-6 | `test_planner_properties.py::test_p16_no_recommended_slot_overlaps_shift`, `test_planner_solver.py::test_travel_into_shift_excludes_slot`, `test_overnight_shift_and_after_midnight_trip` |
| VP-20 | `test_planner_properties.py::test_p20_no_recommended_slot_overlaps_childcare_window`, `test_planner_solver.py::test_slot_overlapping_childcare_window_is_dropped`, `test_slot_outside_childcare_window_is_allowed`, `test_childcare_window_blocks_untimed_escort_ride` |
| VP-7 | `test_planner_solver.py::test_escort_without_travel_estimate_*` |
| VP-8 | `test_planner_properties.py::test_p17_telehealth_only_if_allowed` |
| VP-10 | `test_planner_properties.py::test_none_is_alone_and_only_when_nothing_viable`, `test_planner_solver.py::test_no_candidates_*`, `test_unreachable_*` |
| VP-11 | `tests/contract/test_api_contracts.py::test_plan_matches_contract` |
| VP-12, VP-14 | `test_planner_solver.py::test_slot_itinerary_uses_best_ranked_slot` |
| VP-13 | `test_planner_properties.py::test_ranking_is_deterministic` |
| VP-15 | `test_planner_solver.py::test_escort_visit_gets_ride_not_slot`, `test_api_contracts.py::test_maria_gets_escort_aware_plan` |
| VP-16 | `test_planner_properties.py::test_p18_no_clinical_or_eligibility_text`, `test_planner_solver.py::test_guardrail_catches_banned_wording` |
| VP-18 | `test_api_contracts.py::test_real_mode_reports_unavailable` |
| VP-19 | `test_planner_solver.py::test_planner_does_not_import_web_frameworks` |
| VP-23 | `test_planner_vp23_vp24.py::test_vp23_*`, `test_driver_windows_plan_b.py` |
| VP-24 | `test_planner_vp23_vp24.py::test_vp24_*`, `test_driver_windows_plan_b.py` |
