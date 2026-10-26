"""GET /suggest — "Suggest best schedule" for the web Audit screen.

Thin HTTP wrapper over engine.optimizer.suggest_schedule (the same function the
reach-mcp `suggest_schedule` tool calls), so the UI and MCP can never disagree.

`blocks` is the clinic's CURRENT block start hours for that day (comma list,
e.g. "7,8,17"). Omit it and the engine's default applies (one block per cube
hour), which leaves no free hour to move into, so zero changes is the honest
answer. Mock mode has no cube -> 503.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from api.deps import AuditSource, get_audit_data
from api.schemas import Day
from engine.audit import AuditDataError

router = APIRouter(tags=["suggest"])


class SuggestChangeOut(BaseModel):
    kind: str
    day: str
    block: str
    to: int


class SuggestionOut(BaseModel):
    change: SuggestChangeOut
    gain_visit_hours: float
    gain_people: int
    sources: list[dict[str, Any]]


class SuggestResponse(BaseModel):
    clinic: str
    day: str
    k: int
    baseline_score: float
    suggested_score: float
    baseline_blocks: list[int]
    suggested_blocks: list[int]
    open_hours: list[int]
    changes: list[SuggestionOut]
    sources: list[dict[str, Any]]


def _parse_blocks(raw: str | None) -> list[int] | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        hours = [int(x) for x in raw.split(",") if x.strip() != ""]
    except ValueError as exc:
        raise HTTPException(422, detail="blocks must be comma-separated hours, e.g. 7,8,17") from exc
    if any(h < 0 or h > 23 for h in hours):
        raise HTTPException(422, detail="block hours must be 0..23")
    return hours


@router.get("/suggest", response_model=SuggestResponse, summary="Top-k schedule changes (optimizer)")
def get_suggest(
    clinic: Annotated[str, Query(min_length=1, max_length=64)],
    day: Annotated[Day, Query()],
    source: Annotated[AuditSource, Depends(get_audit_data)],
    k: Annotated[int, Query(ge=1, le=10)] = 3,
    blocks: Annotated[str | None, Query(max_length=100)] = None,
    community: Annotated[str, Query(min_length=1, max_length=64)] = "all",
) -> SuggestResponse:
    if source.mode == "mock":
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Schedule suggestions need the real cube (CARELEAP_DATA=real).")
    from engine.optimizer import suggest_schedule

    from engine.audit import filter_community

    try:
        # Optimize for the community on screen (default: the whole service area).
        origins = filter_community(source.origins, community)
        payload = suggest_schedule(source.cube, origins, clinic, day, k=k,
                                   baseline_blocks=_parse_blocks(blocks))
    except AuditDataError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return SuggestResponse.model_validate(payload)
