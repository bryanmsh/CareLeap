"""Visit Planner constraint solver (owner: M4). Spec: .kiro/specs/visit-planner/.

Pure function: no FastAPI, no Pydantic, no I/O. Uses only the standard library and
engine.types. The transit check is injected (`RoundTripFn`: `engine.round_trip` with
its timetable bound).

Hard rules (steering visit-rules.md):
  R0 unverified rule  -> any null field in the rulebook entry: a single `none` option.
  R1 escort_required  -> never a transit-only option; offer an escort-aware ride.
  R2 shift            -> no recommended slot overlaps the work shift, travel included.
  R3 telehealth_ok    -> a telehealth swap only when the visit type allows it.
  R4 nothing viable   -> exactly one `none` option with a reason for a navigator.
  R5 output text      -> logistics only (planner.guardrails).
  R6 ranking          -> deterministic; independent of candidate order.
"""

from __future__ import annotations

from typing import Any

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date as Date
from datetime import datetime, timedelta

from planner.driver_windows import DriverWindow, covering
from planner.guardrails import assert_logistics_only
from planner.models import (
    Barriers,
    CandidateSlot,
    Itinerary,
    Option,
    OptionKind,
    Patient,
    Plan,
    RoundTripResult,
    VisitRule,
)
from planner.plan_b import render as render_plan_b
from planner.prep_sheet import render_prep_sheet, template_status
from planner.pt1 import Pt1Field, prefill
from planner.transit import RoundTripFn, travel_window

SOLVER_VERSION = "0.1.0"
_DAY = 86_400
_HOUR = 3_600

# Rank of each kind in the output (contract order: slot | ride | tele | prep | none).
KIND_RANK: dict[OptionKind, int] = {kind: i for i, kind in enumerate(OptionKind)}

# Coordinator-facing reasons. Logistics only. These are NOT patient-facing text;
# patient text comes only from human-reviewed templates (M3).
REASONS: dict[str, str] = {
    "slot": "Round trip by transit fits outside the stated work shift.",
    "ride_escort": "This visit type requires an escort home, so a transit-only plan is not offered. "
    "Request an escort-aware ride.",
    "tele": "This visit type allows a telehealth visit.",
    "prep": "This visit type has a prep sheet. Attach the reviewed version in the preferred language.",
    "none_no_candidates": "No candidate slots were provided. Flag for a navigator to call.",
    "none_no_transit": "No candidate slot has a round trip by transit. Flag for a navigator to call.",
    "none_shift": "Every reachable slot overlaps the work shift or childcare window, including travel. "
    "Flag for a navigator to call.",
    "none_escort": "An escort-aware ride is needed, but no slot could be checked against the work "
    "shift including travel. Flag for a navigator to call.",
    "none_rules_unverified": "Logistics rules for this visit type are not verified yet. "
    "Flag for a navigator to call.",
}


@dataclass(frozen=True)
class _Checked:
    slot: CandidateSlot
    trip: RoundTripResult
    window: tuple[int, int] | None  # (leave home, arrive home), seconds
    shift_conflict: bool

    @property
    def burden(self) -> tuple[int, int]:
        # Known door-to-door time ranks ahead of unknown.
        if self.window is None:
            return (1, 0)
        return (0, self.window[1] - self.window[0])

    @property
    def sort_key(self) -> tuple:
        return (*self.burden, self.slot.date, self.slot.start, self.slot.clinic_id)


def slot_iso(slot: CandidateSlot) -> str:
    """ISO local datetime of the appointment start; start >= 86400 rolls to the next date."""
    base = datetime.combine(Date.fromisoformat(slot.date), datetime.min.time())
    return (base + timedelta(seconds=slot.start)).isoformat()


def shift_intervals(work_shift: tuple[int, int] | None) -> list[tuple[int, int]]:
    """The shift as second intervals over the service day and the next day, so trips with
    times > 86400 and overnight shifts are both covered."""
    if work_shift is None:
        return []
    start, end = work_shift[0] * _HOUR, work_shift[1] * _HOUR
    if start == end:
        return []
    base = [(start, end)] if start < end else [(0, end), (start, _DAY)]
    return [(s + d, e + d) for d in (0, _DAY) for s, e in base]


def _hhmm(seconds: int) -> str:
    # GTFS times may pass 24:00; show them as the clock time (00:30), never wrap the data.
    s = seconds % _DAY
    return f"{s // _HOUR:02d}:{s % _HOUR // 60:02d}"


def _plan_b(trip: RoundTripResult, sections: Mapping[str, str] | None) -> str | None:
    """VP-23: plan B text from the signed template only; None when there is none.

    later_bus: the chosen return bus is not the last one, so the last bus home is the
    fallback. last_bus: the chosen return already is the last bus (or it is unknown).
    """
    if not sections or not trip.ret_legs:
        return None
    ret_dep = trip.ret_legs[0].dep
    last = trip.last_bus_home
    if last is not None and last > ret_dep:
        return render_plan_b(sections, "later_bus", {"later_bus_time": _hhmm(last)})
    return render_plan_b(sections, "last_bus", {})


def overlaps(window: tuple[int, int], intervals: Iterable[tuple[int, int]]) -> bool:
    lo, hi = window
    return any(lo < e and hi > s for s, e in intervals)


def _check(
    patient: Patient,
    rule: VisitRule,
    slots: Iterable[CandidateSlot],
    round_trip: RoundTripFn,
    shift: list[tuple[int, int]],
) -> list[_Checked]:
    checked = []
    for slot in slots:
        trip = round_trip(patient.origin_bg, slot.clinic_id, slot.date, slot.start, rule.duration_min)
        window = travel_window(trip)
        conflict = window is not None and overlaps(window, shift)
        checked.append(_Checked(slot, trip, window, conflict))
    return sorted(checked, key=lambda c: c.sort_key)


def trip_details(c: _Checked) -> dict[str, Any]:
    """Navigator-facing summary of the checked round trip, so two options of the same
    kind are tellable apart: when to leave, which buses, when you are home. Times are
    seconds since local midnight (may exceed 86400, never wrapped); the UI formats them.
    Empty when there is no complete transit round trip (ride-only, no estimate)."""
    t = c.trip
    if not (t.reachable and t.out_legs and t.ret_legs):
        return {}
    out_bus = [leg.route_id for leg in t.out_legs if leg.kind == "bus"]
    ret_bus = [leg.route_id for leg in t.ret_legs if leg.kind == "bus"]
    return {
        "transit": {
            "leave_home": t.out_legs[0].dep,
            "arrive_clinic": t.out_legs[-1].arr,
            "depart_clinic": t.ret_legs[0].dep,
            "arrive_home": t.ret_legs[-1].arr,
            "last_bus_home": t.last_bus_home,
            "routes_out": out_bus,
            "routes_ret": ret_bus,
            "buses": len(out_bus) + len(ret_bus),
            "door_to_door_min": (t.ret_legs[-1].arr - t.out_legs[0].dep) // 60,
        }
    }


def _none_reason(rule: VisitRule, checked: Sequence[_Checked]) -> str:
    if not checked:
        return REASONS["none_no_candidates"]
    if rule.escort_required:
        return REASONS["none_escort"]
    if all(c.window is None for c in checked):
        return REASONS["none_no_transit"]
    return REASONS["none_shift"]


CHECKIN_BUFFER_S = 600  # arrive 10 min early (engine Limits.checkin_buffer)


def _trip_signature(c: _Checked) -> tuple:
    t = c.trip
    legs = tuple((leg.kind, leg.route_id, leg.dep, leg.arr) for leg in (*t.out_legs, *t.ret_legs))
    return (c.slot.clinic_id, c.slot.start, legs)


def _collapse_repeats(attend: list[tuple[Option, _Checked | None]]) -> list[tuple[Option, _Checked | None]]:
    """One option per distinct trip. The timetable repeats every weekday, so the same
    clinic + start time + bus legs on Mon, Tue, Wed... is ONE choice offered on several
    dates, not several choices. Keep the earliest (attend is already sorted) and list the
    other dates in `also_on`, in order."""
    kept: list[tuple[Option, _Checked | None]] = []
    index: dict[tuple, int] = {}
    for opt, c in attend:
        if c is None or opt.kind not in (OptionKind.SLOT, OptionKind.RIDE):
            kept.append((opt, c))
            continue
        key = (opt.kind, _trip_signature(c))
        if key in index:
            i = index[key]
            first, fc = kept[i]
            also = [*first.details.get("also_on", []), c.slot.date]
            kept[i] = (Option(first.kind, first.why, {**first.details, "also_on": also}), fc)
            continue
        index[key] = len(kept)
        kept.append((opt, c))
    return kept


def _prep_details(lang: str, first: tuple[Option, _Checked] | None,
                  clinics: Mapping[str, Mapping[str, str]]) -> dict[str, Any]:
    """The prep option: its review status and, when signed off, the filled sheet for the
    top choice."""
    details: dict[str, Any] = {"language": lang, "template_status": template_status(lang)}
    if first is None:
        return details
    top, c = first
    info = clinics.get(c.slot.clinic_id, {})
    t = c.trip
    values = {
        "clinic_name": info.get("name", c.slot.clinic_id),
        "appt_date": c.slot.date,
        "appt_time": _hhmm(c.slot.start),
        # leave-home time only when the bus IS the plan; for a ride the broker sets the
        # pickup, so the line stays blank for the navigator
        "leave_home_time": (_hhmm(t.out_legs[0].dep)
                            if top.kind is OptionKind.SLOT and t.reachable and t.out_legs else ""),
    }
    sheet = render_prep_sheet(lang, values)
    if sheet is not None:
        details["sheet"] = sheet
    return details


def plan_visit(
    patient: Patient,
    rule: VisitRule,
    barriers: Barriers,
    candidate_slots: Sequence[CandidateSlot],
    round_trip: RoundTripFn,
    pt1_fields: tuple[Pt1Field, ...] = (),
    driver_windows: Sequence[DriverWindow] = (),
    patient_town: str | None = None,
    plan_b_sections: Mapping[str, str] | None = None,
    clinics: Mapping[str, Mapping[str, str]] | None = None,
) -> Plan:
    """Plan one visit.

    driver_windows / patient_town (VP-24): a ride is marked `volunteer_driver` only when a
    sourced window for the patient's town covers the whole trip; otherwise it stays a
    PT-1 broker ride. plan_b_sections (VP-23): the SIGNED plan_b template for the
    patient's language (planner.plan_b.load_plan_b); None keeps plan_b null.
    clinics: clinic_id -> {name, address, town} for the prep sheet and the PT-1
    treatment address; unknown clinics fall back to the id.
    """
    if not rule.is_complete:
        # R0: unknown (null) rules are never guessed. Without a verified escort rule we
        # cannot rule out a transit-only plan, so hand off to a navigator.
        return Plan(
            options=(
                Option(
                    OptionKind.NONE,
                    REASONS["none_rules_unverified"],
                    {"navigator_followup": True, "rules_status": rule.source_status},
                ),
            ),
            itinerary=Itinerary(),
            pt1_prefill={},
        )

    shift = shift_intervals(barriers.work_shift)
    # VP-20: a childcare window is a second no-go band. A slot/ride whose
    # door-to-door window (travel included) overlaps it is not recommended, for
    # the same reason as the work shift — the patient must be home then. Both
    # bands are checked together; overnight windows and trip times >= 86400 are
    # handled by shift_intervals without wrapping.
    blocked = shift + shift_intervals(barriers.childcare_window)
    checked = _check(patient, rule, set(candidate_slots), round_trip, blocked)

    # VP-21: cost_worry and has_transport never change the FIXED kind order
    # (slot | ride | tele | prep | none, R6) and never gate an option out — doing
    # either would be a logistics judgement we cannot source. They are recorded as
    # navigator-facing flags so the UI and a human can weigh burden and out-of-pocket
    # cost, and they break ties among same-kind slots in favour of the lowest burden.
    access_flags = {
        "cost_sensitive": barriers.cost_worry,
        "no_personal_transport": not barriers.has_transport,
    }

    attend: list[tuple[Option, _Checked | None]] = []
    if rule.escort_required:
        # R1: rides only. The transit round trip is used as a conservative travel-time
        # proxy for the no-go bands (work shift + childcare window); without any travel
        # estimate the slot is only usable when there is no band to conflict with.
        for c in checked:
            if c.shift_conflict or (c.window is None and blocked):
                continue
            details = {
                "slot": slot_iso(c.slot),
                "clinic_id": c.slot.clinic_id,
                "escort_required": True,
                "has_escort": barriers.has_escort,
                "pt1_request": True,
                "visit_minutes": rule.duration_min,
                "check_in_by": c.slot.start - CHECKIN_BUFFER_S,
                "visit_ends": c.slot.start + rule.duration_min * 60,
                **access_flags,
                # the bus round trip is only the travel-time ESTIMATE behind the ride
                **{k + "_estimate": v for k, v in trip_details(c).items()},
            }
            # VP-24: a volunteer driver / COA van only when a sourced window covers the
            # whole trip (transit travel window as the proxy, else the visit itself).
            span = c.window or (c.slot.start, c.slot.start + rule.duration_min * 60)
            w = covering(driver_windows, patient_town, c.slot.date, span)
            details["ride_mode"] = "volunteer_driver" if w else "pt1_broker"
            details["window"] = w.as_details() if w else None
            attend.append((Option(OptionKind.RIDE, REASONS["ride_escort"], details), c))
    else:
        for c in checked:
            if c.window is None or c.shift_conflict:
                continue
            details = {"slot": slot_iso(c.slot), "clinic_id": c.slot.clinic_id, **access_flags,
                       **trip_details(c)}
            attend.append((Option(OptionKind.SLOT, REASONS["slot"], details), c))

    if rule.telehealth_ok:  # R3
        # A telehealth visit removes the trip entirely, so flag it as the zero-travel
        # option when the patient has no transport of their own or is cost-sensitive.
        tele_details = {
            "zero_travel": True,
            "relieves_no_transport": not barriers.has_transport,
            "relieves_cost": barriers.cost_worry,
        }
        attend.append((Option(OptionKind.TELE, REASONS["tele"], tele_details), None))

    # R6: stable order by kind, then by the candidate's burden/sort key.
    attend.sort(key=lambda oc: (KIND_RANK[oc[0].kind], oc[1].sort_key if oc[1] else ()))
    attend = _collapse_repeats(attend)

    if not attend:  # R4
        options: list[Option] = [
            Option(OptionKind.NONE, _none_reason(rule, checked), {"navigator_followup": True})
        ]
    else:
        options = [o for o, _ in attend]
        # VP-22 (task 1): a recurring visit (e.g. dialysis 3x/week, infusion per cycle)
        # is not a one-off. Carry a structured recurrence plan on the top attend option
        # so the UI/navigator arranges the REPEATING trip, and so a ride reflects the
        # PT-1-once-per-destination rule (the broker then schedules each repeat — see
        # data/manual/pt1_fields.json recurrence_note). Logistics only: the cadence is
        # the rulebook's sourced number, never a clinical schedule we invent.
        if rule.recurrence_per_week and options:
            top = options[0]
            per_week = rule.recurrence_per_week
            recurrence = {
                "per_week": per_week,
                "repeats": True,
                "same_trip_each_session": True,
                "note": (
                    f"This visit repeats about {per_week}x per week. "
                    "Plan the same round trip for every session."
                ),
            }
            if top.kind is OptionKind.RIDE:
                # One PT-1 per destination; the broker (MART/GATRA) schedules the repeats.
                recurrence["pt1_once_per_destination"] = True
                recurrence["note"] += (
                    " Submit one PT-1 for this destination; the broker schedules each ride."
                )
            options[0] = Option(top.kind, top.why, {**top.details, "recurrence": recurrence})
        if rule.prep:
            first = next(((o, c) for o, c in attend if c is not None), None)
            options.append(
                Option(OptionKind.PREP, REASONS["prep"],
                       _prep_details(barriers.language, first, clinics or {}))
            )

    top_slot = next((c for o, c in attend if o.kind is OptionKind.SLOT), None)
    itinerary = (
        Itinerary(
            out_legs=tuple(top_slot.trip.out_legs),
            ret_legs=tuple(top_slot.trip.ret_legs),
            last_bus_home=top_slot.trip.last_bus_home,
            plan_b=_plan_b(top_slot.trip, plan_b_sections),
        )
        if top_slot
        else Itinerary()
    )

    top_ride = next((c for o, c in attend if o.kind is OptionKind.RIDE), None)
    pt1 = (
        prefill(pt1_fields, patient, rule, top_ride.slot, barriers.language,
                (clinics or {}).get(top_ride.slot.clinic_id))
        if top_ride and pt1_fields
        else {}
    )

    plan = Plan(options=tuple(options), itinerary=itinerary, pt1_prefill=pt1)
    assert_logistics_only([[o.why, o.details] for o in plan.options])  # R5
    assert_logistics_only(plan.itinerary.plan_b or "")  # R5 also covers plan B text
    return plan
