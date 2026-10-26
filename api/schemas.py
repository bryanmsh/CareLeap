"""Pydantic models for the HTTP API. Shapes follow docs/contracts.md §3.

Do not change a shape without telling the whole team and updating the contract tests
(tests/contract/) in the same PR.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

LangCode = Annotated[
    str, Field(pattern=r"^[a-z]{2}$", description="ISO 639-1 language code, e.g. 'en', 'es'.")
]
Day = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    data_mode: Literal["mock", "real"]


class SourceRef(BaseModel):
    name: str
    vintage: str
    url: str | None = None


# --------------------------------------------------------------------------- #
# GET /audit, POST /whatif (owner: M2; scaffolded by M4)
# --------------------------------------------------------------------------- #
class AuditCell(BaseModel):
    day: Day
    hour: int
    share: float = Field(ge=0.0, le=1.0)
    n: int = Field(ge=0)
    reached: int = Field(ge=0)


class EquityGroup(BaseModel):
    share: float = Field(ge=0.0, le=1.0)
    n: int = Field(ge=0)


class Equity(BaseModel):
    ej: EquityGroup
    lep: EquityGroup
    age65: EquityGroup
    zero_veh: EquityGroup


class EquityCIGroup(BaseModel):
    """90% confidence interval from ACS margins of error (engine/equity.py)."""

    share: float = Field(ge=0.0, le=1.0)
    lo: float = Field(ge=0.0, le=1.0)
    hi: float = Field(ge=0.0, le=1.0)
    moe: float = Field(ge=0.0)
    n: int = Field(ge=0)


class EquityCI(BaseModel):
    ej: EquityCIGroup
    lep: EquityCIGroup
    age65: EquityCIGroup
    zero_veh: EquityCIGroup


class AuditResponse(BaseModel):
    cells: list[AuditCell]
    equity: Equity
    # null when ACS margins of error are not built (mock mode, CI without data/raw)
    equity_ci: EquityCI | None = None
    sources: list[SourceRef]


# --------------------------------------------------------------------------- #
# GET /clinics, GET /audit/blockgroups (additive, for the web Audit screen)
# --------------------------------------------------------------------------- #
class Clinic(BaseModel):
    clinic_id: str
    clinic_name: str
    visit_type: str
    visit_minutes: int = Field(ge=0)
    stop_id: str
    is_demo_anchor: bool


class ClinicsResponse(BaseModel):
    clinics: list[Clinic]
    sources: list[SourceRef]


class BlockGroupFeature(BaseModel):
    bg_geoid: str
    lat: float
    lon: float
    carless_adults: int = Field(ge=0)
    share: float = Field(ge=0.0, le=1.0)
    desert: bool


class BlockGroupsResponse(BaseModel):
    features: list[BlockGroupFeature]
    sources: list[SourceRef]


class WhatIfShift(_Strict):
    block: str = Field(pattern=r"^(mon|tue|wed|thu|fri|sat|sun)-\d{2}$", examples=["mon-08"])
    to: int = Field(ge=0, le=23, description="New start hour, 24h local.")


class WhatIfRequest(_Strict):
    clinic: str = Field(min_length=1, max_length=64)
    shift: WhatIfShift
    # Same scope as the /audit the user is looking at, so before/after compare like
    # with like. Optional and additive: omitted = the whole service area.
    community: str = Field(default="all", min_length=1, max_length=64)


# --------------------------------------------------------------------------- #
# POST /plan (owner: M4)
# --------------------------------------------------------------------------- #
class PatientIn(_Strict):
    """Synthetic patients only. Never send real PHI to this API."""

    id: str = Field(min_length=1, max_length=64)
    origin_bg: str = Field(pattern=r"^\d{12}$", description="12-digit Census block-group GEOID.")
    lang: LangCode


class BarriersIn(_Strict):
    has_transport: bool
    work_shift: list[int] | None = Field(
        default=None,
        description="[start_hour, end_hour], 24h local. Overnight shifts allowed (e.g. [22, 6]).",
    )
    childcare: bool
    has_escort: bool
    cost_worry: bool
    language: LangCode
    childcare_window: list[int] | None = Field(
        default=None,
        description="[start_hour, end_hour], 24h local (VP-20). Optional. May cross "
        "midnight (e.g. [22, 6]). No slot/ride whose travel window overlaps this is recommended.",
    )

    @field_validator("work_shift", "childcare_window")
    @classmethod
    def _valid_shift(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return value
        if len(value) != 2 or not all(0 <= h <= 24 for h in value):
            raise ValueError("must be [start_hour, end_hour] with hours in 0..24")
        return value


class PlanRequest(_Strict):
    patient: PatientIn
    visit_type: str = Field(min_length=1, max_length=64)
    barriers: BarriersIn


class LegOut(BaseModel):
    """Leg shape from docs/contracts.md §2. Times may exceed 86400; never wrapped."""

    kind: Literal["walk", "bus"]
    from_stop: str
    to_stop: str
    route_id: str | None
    dep: int
    arr: int


class OptionOut(BaseModel):
    kind: Literal["slot", "ride", "tele", "prep", "none"]
    details: dict[str, Any]
    why: str


class ItineraryOut(BaseModel):
    out_legs: list[LegOut]
    ret_legs: list[LegOut]
    last_bus_home: int | None
    plan_b: str | None = Field(description="Patient-facing; null until reviewed templates (M3) exist.")


class PlanResponse(BaseModel):
    options: list[OptionOut]
    itinerary: ItineraryOut
    pt1_prefill: dict[str, Any]


# --------------------------------------------------------------------------- #
# GET /provenance?id (owner: M4 with M1)
# --------------------------------------------------------------------------- #
class ProvenanceSource(BaseModel):
    name: str
    vintage: str


class PropertyStatus(BaseModel):
    name: str
    status: Literal["pass", "fail", "pending"]


class ProvenanceResponse(BaseModel):
    source: ProvenanceSource
    requirement_id: str
    properties: list[PropertyStatus]
    spec_link: str


# --------------------------------------------------------------------------- #
# GET /rural?town (owner: M1) — rural lens, see docs/contracts.md §3
# --------------------------------------------------------------------------- #
RuralVerdict = Literal["transit", "assisted_only", "none", "not_assessed"]


class RuralFeature(BaseModel):
    bg_geoid: str
    town: str
    county: str
    lat: float
    lon: float
    carless_adults: int = Field(ge=0)
    transit_share: float = Field(ge=0.0, le=1.0, description="share of ALL cube cells (every clinic x day x hour) that are reachable")
    desert: bool
    verdict: RuralVerdict
    coverage_tier: str


class RuralVerdictCount(BaseModel):
    n_bg: int = Field(ge=0)
    carless_adults: int = Field(ge=0)


class RuralSummary(BaseModel):
    n_bg: int = Field(ge=0)
    carless_adults: int = Field(ge=0)
    by_verdict: dict[str, RuralVerdictCount]


class RuralOption(BaseModel):
    """One town's row from the hand-collected rural tables, provenance included."""

    town: str
    county: str | None = None
    coverage_tier: str | None = None
    has_any_option: bool
    dial_a_ride: str | None = None
    coa_driver: str | None = None
    pt1: str | None = None
    source_url: str | None = None
    verified_by: str | None = None
    date: str | None = None


class RuralResponse(BaseModel):
    town: str | None = None
    features: list[RuralFeature]
    summary: RuralSummary
    options: list[RuralOption]
    towns_available: list[str]
    sources: list[SourceRef]
