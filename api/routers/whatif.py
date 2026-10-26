"""POST /whatif (owner: M2).

Returns the same shape as GET /audit (docs/contracts.md §3).

mock mode : return the labelled mock, day stamped (existing behaviour).
real mode : recompute through engine.audit.whatif (the ONE aggregation path).
            An unknown clinic -> 404; a block/hour outside the clinic's schedule
            -> 422 (the request was well-formed but refers to a slot that does
            not exist).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import AuditSource, get_audit_data
from api.routers.audit import with_day
from api.schemas import AuditResponse, WhatIfRequest
from engine.audit import AuditDataError, whatif as engine_whatif

router = APIRouter(tags=["whatif"])


def _clinic_known(cube: Any, clinic: str) -> bool:
    return bool((cube.clinic_id == clinic).any())


@router.post("/whatif", response_model=AuditResponse, summary="Recompute after moving a clinic block")
def post_whatif(
    request: WhatIfRequest,
    source: Annotated[AuditSource, Depends(get_audit_data)],
) -> AuditResponse:
    day = request.shift.block.split("-", 1)[0]
    if source.mode == "mock":
        return AuditResponse.model_validate(with_day(source.payload or {}, day))

    if not _clinic_known(source.cube, request.clinic):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"unknown clinic {request.clinic!r}")
    try:
        data = engine_whatif(source.cube, source.origins, request.clinic,
                             request.shift.block, request.shift.to, community=request.community)
    except AuditDataError as exc:
        # clinic exists but the block/hour is outside its schedule: unprocessable.
        raise HTTPException(422, detail=str(exc)) from exc
    return AuditResponse.model_validate(data)
