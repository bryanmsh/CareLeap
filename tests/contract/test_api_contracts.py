"""Contract tests: every endpoint's response validates against docs/contracts.md shapes."""

from pathlib import Path

import pytest

from api.deps import REAL_CLINIC_STOPS_PATH, REAL_ORIGINS_PATH, REAL_PVTA_DIR
from planner.transit import TimetableRoundTrip
from tests.contract import shapes

_ROUTING_CACHE_READY = TimetableRoundTrip.cache_ready(
    REAL_PVTA_DIR, REAL_ORIGINS_PATH, REAL_CLINIC_STOPS_PATH
)


def _assert_mock_mode(response):
    assert response.headers["X-Data-Mode"] == "mock"


# ---- /health --------------------------------------------------------------- #
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["data_mode"] == "mock"


# ---- GET /audit ------------------------------------------------------------ #
def test_audit_matches_contract(client):
    r = client.get("/audit", params={"clinic": "mock-clinic-gi", "community": "holyoke", "day": "tue"})
    assert r.status_code == 200
    _assert_mock_mode(r)
    body = shapes.Audit.model_validate(r.json())
    assert body.cells and all(c.day == "tue" for c in body.cells)
    assert all("MOCK" in s.name for s in body.sources)


def test_audit_requires_all_params(client):
    assert client.get("/audit", params={"clinic": "x", "community": "y"}).status_code == 422
    assert client.get("/audit", params={"clinic": "x", "community": "y", "day": "monday"}).status_code == 422


# ---- POST /whatif ---------------------------------------------------------- #
def test_whatif_returns_audit_shape(client):
    r = client.post("/whatif", json={"clinic": "mock-clinic-gi", "shift": {"block": "mon-08", "to": 10}})
    assert r.status_code == 200
    _assert_mock_mode(r)
    shapes.Audit.model_validate(r.json())


def test_whatif_rejects_bad_block(client):
    r = client.post("/whatif", json={"clinic": "c", "shift": {"block": "monday-8", "to": 10}})
    assert r.status_code == 422


# ---- POST /plan ------------------------------------------------------------ #
def test_plan_matches_contract(client, maria_request):
    r = client.post("/plan", json=maria_request)
    assert r.status_code == 200
    _assert_mock_mode(r)
    shapes.Plan.model_validate(r.json())


def test_maria_gets_escort_aware_plan(client, maria_request):
    """Done-by-H6: positive-FIT colonoscopy, works 7-15, Spanish, no escort."""
    body = client.post("/plan", json=maria_request).json()
    kinds = [o["kind"] for o in body["options"]]

    assert "slot" not in kinds  # escort required: never transit-only
    assert kinds[0] == "ride"
    ride = body["options"][0]
    assert ride["details"]["escort_required"] is True
    assert ride["details"]["has_escort"] is False
    assert ride["details"]["slot"] == "2026-11-12T15:30:00"  # the 08:00 slot is inside her shift
    assert "prep" in kinds
    prep = next(o for o in body["options"] if o["kind"] == "prep")
    assert prep["details"]["language"] == "es"
    assert body["pt1_prefill"]["mock_appointment_time"] == "15:30"
    assert body["pt1_prefill"]["mock_provider_attestation"] is None


def test_plan_unknown_visit_type(client, maria_request):
    r = client.post("/plan", json={**maria_request, "visit_type": "not-a-type"})
    assert r.status_code == 422


def test_plan_rejects_extra_fields(client, maria_request):
    bad = {**maria_request, "patient": {**maria_request["patient"], "ssn": "x"}}
    assert client.post("/plan", json=bad).status_code == 422


def test_plan_rejects_bad_geoid(client, maria_request):
    bad = {**maria_request, "patient": {**maria_request["patient"], "origin_bg": "25013"}}
    assert client.post("/plan", json=bad).status_code == 422


# ---- GET /provenance ------------------------------------------------------- #
def test_provenance_matches_contract(client):
    r = client.get("/provenance", params={"id": "mock-audit-cell"})
    assert r.status_code == 200
    _assert_mock_mode(r)
    body = shapes.Provenance.model_validate(r.json())
    assert "MOCK" in body.source.name


def test_provenance_unknown_id(client):
    assert client.get("/provenance", params={"id": "nope"}).status_code == 404


def test_provenance_requires_id(client):
    assert client.get("/provenance").status_code == 422


# ---- real mode: never falls back to mocks ---------------------------------- #
def test_real_mode_reports_unavailable(monkeypatch, maria_request):
    from fastapi.testclient import TestClient

    from api import deps
    from api.main import create_app
    from engine import audit as engine_audit

    monkeypatch.setenv("CARELEAP_DATA", "real")
    # Simulate "cube not built yet" regardless of what is cached on this machine.
    monkeypatch.setattr(engine_audit, "CUBE_PATH", engine_audit.ROOT / "does-not-exist.parquet")
    deps._load_cube_origins.cache_clear()
    real = TestClient(create_app())
    assert real.get("/health").json()["data_mode"] == "real"
    assert real.get("/audit", params={"clinic": "c", "community": "h", "day": "mon"}).status_code == 503
    # /provenance now serves from docs/provenance.jsonl in real mode: a mock-only id is
    # simply unknown there (404), not 503.
    assert real.get("/provenance", params={"id": "mock-audit-cell"}).status_code == 404
    # /plan in real mode: 503 while the routing cache is absent (routing unavailable),
    # 200 once data/cache/pvta + origins + clinic_stops are present.
    plan_status = real.post("/plan", json=maria_request).status_code
    assert plan_status == (200 if _ROUTING_CACHE_READY else 503)


@pytest.mark.skipif(not _ROUTING_CACHE_READY, reason="routing cache (data/cache/pvta) not present")
def test_maria_real_routing_end_to_end(monkeypatch, maria_request):
    """Task 11: /plan in real mode routes through the real engine over the PVTA feed.
    Runs only when the pipeline cache is present (CI without data skips this)."""
    from fastapi.testclient import TestClient

    from api.main import create_app

    monkeypatch.setenv("CARELEAP_DATA", "real")
    client = TestClient(create_app())
    r = client.post("/plan", json=maria_request)
    assert r.status_code == 200
    body = shapes.Plan.model_validate(r.json())
    # Escort visit: never a transit-only slot, whatever the real feed says.
    assert "slot" not in {o.kind for o in body.options}


def test_real_provenance_serves_from_jsonl(monkeypatch):
    """Item 3: real-mode /provenance reads docs/provenance.jsonl and returns the
    source -> requirement -> properties -> status record for a known id."""
    from fastapi.testclient import TestClient

    from api.main import create_app

    monkeypatch.setenv("CARELEAP_DATA", "real")
    real = TestClient(create_app())
    r = real.get("/provenance", params={"id": "planner-logistics-only"})
    assert r.status_code == 200
    body = shapes.Provenance.model_validate(r.json())
    assert body.requirement_id == "VP-16"
    assert body.spec_link.endswith("#VP-16")
    assert any(p.status == "pass" for p in body.properties)
    assert real.get("/provenance", params={"id": "no-such-id"}).status_code == 404


# ---- real DATA, stubbed router: Maria on real rules + real clinic schedule --- #
def test_maria_on_real_data_with_stubbed_router(monkeypatch, maria_request):
    """Tasks 12/13: Maria's escort plan built from the REAL rulebook
    (planner/visit_rules.yaml) and the REAL clinic schedule
    (data/manual/clinic_schedules.csv), with only the router stubbed because task 11
    (engine.round_trip + stops_walk.parquet) is not landed yet.

    Proves: colonoscopy -> escort ride (never transit-only), the recommended slot is
    outside her 07-15 shift, the ES prep sheet is offered, and the PT-1 pre-fill uses
    M3's real field keys.
    """
    from fastapi.testclient import TestClient

    from api import deps
    from api.main import create_app
    from engine.types import Leg, RoundTripResult
    from planner.slots import load_slots, slots_for_rule
    from planner.rules import load_rules

    monkeypatch.setenv("CARELEAP_DATA", "real")

    # Build a stub router that answers for the real colonoscopy slots. A 16:30 slot
    # gets a clean round trip home after Maria's shift; the 08:00/12:15 slots are
    # inside her shift and will be filtered by the solver.
    root = Path(__file__).resolve().parents[2]
    rules = load_rules(root / "planner" / "visit_rules.yaml")
    scheduled = load_slots(root / "data" / "manual" / "clinic_schedules.csv")
    colo_slots = slots_for_rule(scheduled, rules["colonoscopy"])
    assert colo_slots, "expected real colonoscopy (GI consultation) slots"

    def stub_round_trip(origin, clinic, date, start, minutes):
        # A reachable trip whose return lands well after the 15:00 shift end.
        leave = max(start - 60 * 60, 5 * 3600 + 30 * 60)
        home = start + minutes * 60 + 45 * 60
        return RoundTripResult(
            reachable=True,
            out_legs=[Leg("bus", "origin", "clinic", "R10", leave, start - 15 * 60)],
            ret_legs=[Leg("bus", "clinic", "origin", "R10", home - 30 * 60, home)],
            last_bus_home=home - 30 * 60,
            reason="stub-real-data",
        )

    app = create_app()
    app.dependency_overrides[deps.get_round_trip] = lambda: stub_round_trip
    client = TestClient(app)

    r = client.post("/plan", json=maria_request)
    assert r.status_code == 200
    body = r.json()
    kinds = [o["kind"] for o in body["options"]]

    assert "slot" not in kinds           # escort required -> never transit-only
    assert kinds[0] == "ride"
    ride = body["options"][0]
    assert ride["details"]["escort_required"] is True
    assert ride["details"]["has_escort"] is False
    # The recommended slot must start outside her 07:00-15:00 shift.
    slot_hour = int(ride["details"]["slot"][11:13])
    assert slot_hour >= 15, f"recommended slot {ride['details']['slot']} is inside the shift"
    assert "prep" in kinds
    prep = next(o for o in body["options"] if o["kind"] == "prep")
    assert prep["details"]["language"] == "es"
    # PT-1 pre-fill keys off M3's real field inventory (member_id etc.).
    assert "member_id" in body["pt1_prefill"]
    assert body["pt1_prefill"]["member_id"] == "maria"
    shapes.Plan.model_validate(body)
