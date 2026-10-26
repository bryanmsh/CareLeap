"""POST /plan (owner: M4). Thin adapter over planner.solver."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import (
    CandidateSlotSource,
    get_candidate_slot_source,
    get_clinic_info,
    get_pt1_fields,
    get_round_trip,
    get_visit_rules,
)
from api.schemas import ItineraryOut, LegOut, OptionOut, PlanRequest, PlanResponse
from planner.guardrails import GuardrailViolation
from planner.models import Barriers, Leg, Patient, Plan, VisitRule
from planner.pt1 import Pt1Field
from planner.solver import plan_visit
from planner.transit import RoundTripFn

router = APIRouter(tags=["plan"])
log = logging.getLogger(__name__)


def _to_inputs(request: PlanRequest) -> tuple[Patient, Barriers]:
    p, b = request.patient, request.barriers
    patient = Patient(id=p.id, origin_bg=p.origin_bg, lang=p.lang)
    barriers = Barriers(
        has_transport=b.has_transport,
        work_shift=(b.work_shift[0], b.work_shift[1]) if b.work_shift else None,
        childcare=b.childcare,
        has_escort=b.has_escort,
        cost_worry=b.cost_worry,
        language=b.language,
        childcare_window=(b.childcare_window[0], b.childcare_window[1]) if b.childcare_window else None,
    )
    return patient, barriers


def _leg_out(leg: Leg) -> LegOut:
    return LegOut(
        kind=leg.kind,
        from_stop=leg.from_stop,
        to_stop=leg.to_stop,
        route_id=leg.route_id,
        dep=leg.dep,
        arr=leg.arr,
    )


def _to_response(plan: Plan) -> PlanResponse:
    it = plan.itinerary
    return PlanResponse(
        options=[OptionOut(kind=o.kind.value, details=dict(o.details), why=o.why) for o in plan.options],
        itinerary=ItineraryOut(
            out_legs=[_leg_out(x) for x in it.out_legs],
            ret_legs=[_leg_out(x) for x in it.ret_legs],
            last_bus_home=it.last_bus_home,
            plan_b=it.plan_b,
        ),
        pt1_prefill=dict(plan.pt1_prefill),
    )


@router.post("/plan", response_model=PlanResponse, summary="Build a Visit Planner plan")
def create_plan(
    request: PlanRequest,
    rules: Annotated[dict[str, VisitRule], Depends(get_visit_rules)],
    slots_for: Annotated[CandidateSlotSource, Depends(get_candidate_slot_source)],
    round_trip: Annotated[RoundTripFn, Depends(get_round_trip)],
    pt1_fields: Annotated[tuple[Pt1Field, ...], Depends(get_pt1_fields)],
    clinics: Annotated[dict[str, dict[str, str]], Depends(get_clinic_info)],
) -> PlanResponse:
    rule = rules.get(request.visit_type)
    if rule is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"error": "unknown visit_type", "known": sorted(rules)},
        )
    patient, barriers = _to_inputs(request)
    try:
        plan = plan_visit(patient, rule, barriers, slots_for(rule), round_trip, pt1_fields,
                          clinics=clinics)
    except GuardrailViolation:
        log.exception("plan withheld by logistics-only guardrail")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Plan withheld: output failed the logistics-only check.",
        ) from None
    return _to_response(plan)
