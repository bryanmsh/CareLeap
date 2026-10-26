"""FastAPI dependencies: where each endpoint's data comes from.

`CARELEAP_DATA` selects the data mode:
  mock (default) - labelled mocks in api/mocks/ (H1 scaffold).
  real           - real files/engine only. Anything not landed yet returns 503 rather
                   than falling back to mock data silently.
Tests override these dependencies with their own synthetic fixtures.
"""

from __future__ import annotations

import functools
import json
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from fastapi import HTTPException, status

from api import mocks
from engine.paths import cache_dir
from planner.models import CandidateSlot, VisitRule
from planner.pt1 import Pt1Field, Pt1FieldsError, load_fields, load_fields_inventory
from planner.rules import RulebookError, load_rules
from planner.slots import ClinicScheduleError, load_slots, slots_for_rule
from planner.transit import FixtureRoundTrip, RoundTripFn, TimetableRoundTrip

if TYPE_CHECKING:  # pragma: no cover - typing only
    import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_RULES_PATH = REPO_ROOT / "planner" / "visit_rules.yaml"
REAL_PT1_PATH = REPO_ROOT / "data" / "manual" / "pt1_fields.json"
REAL_CLINIC_SCHEDULE_PATH = REPO_ROOT / "data" / "manual" / "clinic_schedules.csv"
REAL_PROVENANCE_PATH = REPO_ROOT / "docs" / "provenance.jsonl"
REAL_PVTA_DIR = cache_dir() / "pvta"  # CARELEAP_CACHE_DIR-aware (make demo)
REAL_ORIGINS_PATH = cache_dir() / "origins.parquet"
REAL_CLINIC_STOPS_PATH = REPO_ROOT / "data" / "manual" / "clinic_stops.csv"

DataMode = Literal["mock", "real"]
CandidateSlotSource = Callable[[VisitRule], Sequence[CandidateSlot]]


def data_mode() -> DataMode:
    mode = os.environ.get("CARELEAP_DATA", "mock")
    if mode not in ("mock", "real"):
        raise RuntimeError(f"CARELEAP_DATA must be 'mock' or 'real', got {mode!r}")
    return mode  # type: ignore[return-value]


def _unavailable(what: str) -> HTTPException:
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"{what} is not available yet.")


# --------------------------------------------------------------------------- #
# /audit, /whatif (M2)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class AuditSource:
    """What /audit and /whatif read from.

    mock mode : `payload` is the ready-made audit dict (api/mocks/audit.json);
                routers return it verbatim (stamped with the requested day).
    real mode : `cube` and `origins` are the DataFrames engine.audit aggregates;
                routers call engine.audit.audit(...) / whatif(...) per request.
    """

    mode: DataMode
    payload: dict[str, Any] | None = None
    cube: "pd.DataFrame | None" = None
    origins: "pd.DataFrame | None" = None


@functools.lru_cache(maxsize=1)
def _load_cube_origins() -> tuple["pd.DataFrame", "pd.DataFrame"]:
    """Load + cache the real cube and origins. Cache lives for the process."""
    from engine import audit as engine_audit

    if not engine_audit.CUBE_PATH.is_file() or not engine_audit.ORIGINS_PATH.is_file():
        raise FileNotFoundError  # translated to 503 by the caller
    return engine_audit.load_cube(), engine_audit.load_origins()


def get_audit_data() -> AuditSource:
    if data_mode() == "mock":
        return AuditSource(mode="mock", payload=mocks.load("audit.json"))
    try:
        cube, origins = _load_cube_origins()
    except (FileNotFoundError, OSError) as exc:
        raise _unavailable("Reachability cube (data/cache/cube.parquet, M2)") from exc
    return AuditSource(mode="real", cube=cube, origins=origins)


# --------------------------------------------------------------------------- #
# /rural (M1) — rural lens
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RuralSource:
    """What /rural reads from: the cube + origins (as /audit) joined to towns and the
    hand-collected rural tables. mock mode carries no frames (empty, labelled answer)."""

    mode: DataMode
    cube: "pd.DataFrame | None" = None
    origins: "pd.DataFrame | None" = None
    towns: "pd.DataFrame | None" = None
    coverage: "pd.DataFrame | None" = None
    options: "pd.DataFrame | None" = None


@functools.lru_cache(maxsize=1)
def _load_rural_tables() -> tuple["pd.DataFrame", "pd.DataFrame", "pd.DataFrame"]:
    from engine import rural as engine_rural

    if not engine_rural.towns_path().is_file():
        raise FileNotFoundError
    return engine_rural.load_towns(), engine_rural.load_coverage(), engine_rural.load_options()


def get_rural_data() -> RuralSource:
    if data_mode() == "mock":
        return RuralSource(mode="mock")
    try:
        cube, origins = _load_cube_origins()
    except (FileNotFoundError, OSError) as exc:
        raise _unavailable("Reachability cube (data/cache/cube.parquet)") from exc
    try:
        towns, coverage, options = _load_rural_tables()
    except (FileNotFoundError, OSError) as exc:
        raise _unavailable("Rural lens (data/cache/bg_towns.parquet: run `make towns`)") from exc
    return RuralSource(mode="real", cube=cube, origins=origins, towns=towns, coverage=coverage, options=options)


# --------------------------------------------------------------------------- #
# /provenance
# --------------------------------------------------------------------------- #
def get_provenance_index() -> Mapping[str, Mapping[str, Any]]:
    if data_mode() == "mock":
        return mocks.load("provenance.json")["records"]
    # Real mode: read docs/provenance.jsonl (one JSON record per on-screen id). The
    # human-readable view is docs/traceability.md; this file is the machine source.
    if not REAL_PROVENANCE_PATH.is_file():
        raise _unavailable("Provenance index (docs/provenance.jsonl)")
    records: dict[str, dict[str, Any]] = {}
    for lineno, line in enumerate(REAL_PROVENANCE_PATH.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"provenance.jsonl line {lineno} is not valid JSON: {exc}") from exc
        rid = record.pop("id", None)
        if not isinstance(rid, str) or not rid:
            raise RuntimeError(f"provenance.jsonl line {lineno} is missing a string 'id'")
        records[rid] = record
    return records


# --------------------------------------------------------------------------- #
# /plan
# --------------------------------------------------------------------------- #
def get_visit_rules() -> dict[str, VisitRule]:
    mock = data_mode() == "mock"
    path = mocks.PLANNER_MOCKS_DIR / "visit_rules.yaml" if mock else REAL_RULES_PATH
    try:
        return load_rules(path)
    except RulebookError as exc:
        raise _unavailable("Visit rulebook (planner/visit_rules.yaml, M3)") from exc


def get_pt1_fields() -> tuple[Pt1Field, ...]:
    if data_mode() == "real":
        # Real mode: adapt M3's verified PT-1 field inventory (keys/labels from
        # MassHealth bulletins) into planner Pt1Fields via the planner's source map.
        if not REAL_PT1_PATH.is_file():
            return ()  # pt1_prefill stays {} until the field list lands
        try:
            return load_fields_inventory(REAL_PT1_PATH)
        except Pt1FieldsError as exc:
            raise _unavailable("PT-1 field list") from exc
    try:
        return load_fields(mocks.PLANNER_MOCKS_DIR / "pt1_fields.json")
    except Pt1FieldsError as exc:
        raise _unavailable("PT-1 field list") from exc


def _slot_window() -> tuple[str, str]:
    """[today, today + CARELEAP_SLOT_HORIZON_DAYS] as ISO dates.

    CARELEAP_TODAY freezes "today" so a frozen demo snapshot (whose slots were
    generated for a fixed date range) keeps answering the same way; `make demo` sets it.
    """
    import datetime as _dt

    today_s = os.environ.get("CARELEAP_TODAY", "").strip()
    today = _dt.date.fromisoformat(today_s) if today_s else _dt.date.today()
    days = int(os.environ.get("CARELEAP_SLOT_HORIZON_DAYS", "14"))
    return today.isoformat(), (today + _dt.timedelta(days=days)).isoformat()


def get_candidate_slot_source() -> CandidateSlotSource:
    if data_mode() == "real":
        # Real mode: demo/illustrative slots from data/manual/clinic_schedules.csv (M3).
        # Every row is is_template=TRUE ("Demo assumption"), not a bookable slot.
        try:
            scheduled = load_slots(REAL_CLINIC_SCHEDULE_PATH)
        except ClinicScheduleError as exc:
            raise _unavailable("Clinic schedules (data/manual/clinic_schedules.csv, M3)") from exc

        today, horizon = _slot_window()

        def real_source(rule: VisitRule) -> list[CandidateSlot]:
            # Only slots from today through today + horizon: a past date is not an option,
            # and a navigator books within a short window. Both ends are dates, no times.
            return [s for s in slots_for_rule(scheduled, rule) if today <= s.date <= horizon]

        return real_source
    by_type = mocks.load("planner/candidate_slots.json")["slots"]

    def source(rule: VisitRule) -> list[CandidateSlot]:
        return [CandidateSlot(**s) for s in by_type.get(rule.visit_type, [])]

    return source


@functools.lru_cache(maxsize=1)
def get_clinic_info() -> dict[str, dict[str, str]]:
    """clinic_id -> {name, address, town} from data/manual/clinics.csv (first row per
    clinic), with clinic_stops.csv names as a fallback. Committed manual data, so the
    same in mock and real mode."""
    import csv as _csv

    info: dict[str, dict[str, str]] = {}
    clinics_csv = REPO_ROOT / "data" / "manual" / "clinics.csv"
    if clinics_csv.is_file():
        with clinics_csv.open(encoding="utf-8", newline="") as fh:
            for row in _csv.DictReader(fh):
                cid = (row.get("clinic_id") or "").strip()
                if cid and cid not in info:
                    info[cid] = {"name": row.get("clinic_name", "").strip(),
                                 "address": row.get("address", "").strip(),
                                 "town": row.get("town", "").strip()}
    if REAL_CLINIC_STOPS_PATH.is_file():
        with REAL_CLINIC_STOPS_PATH.open(encoding="utf-8", newline="") as fh:
            for row in _csv.DictReader(fh):
                cid = (row.get("clinic_id") or "").strip()
                if cid and cid not in info:
                    info[cid] = {"name": row.get("clinic_name", "").strip(), "address": "", "town": ""}
    return info


def get_round_trip() -> RoundTripFn:
    if data_mode() == "real":
        # Task 11: real routing over the PVTA feed via the engine's authoritative
        # round_trip, resolving origin_bg/clinic_id to coordinates. Requires the
        # pipeline caches; when any is missing, routing is genuinely unavailable (503)
        # rather than silently stubbed.
        if TimetableRoundTrip.cache_ready(REAL_PVTA_DIR, REAL_ORIGINS_PATH, REAL_CLINIC_STOPS_PATH):
            return TimetableRoundTrip(REAL_PVTA_DIR, REAL_ORIGINS_PATH, REAL_CLINIC_STOPS_PATH)
        raise _unavailable("Routing engine (needs data/cache/pvta + origins.parquet + clinic_stops.csv)")
    return FixtureRoundTrip.from_records(mocks.load("planner/round_trips.json")["records"])
