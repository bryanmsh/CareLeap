"""Unit tests for GET /audit and POST /whatif in REAL mode.

No real cube needed: a tiny hand-built cube + origins DataFrame is injected through
FastAPI dependency_overrides, so these run in CI. They pin the real-mode contract:
shares in [0, 1], n/reached weighted by carless_adults, the four equity groups, a
non-empty sources list with a vintage, whatif actually changing the hour set, and an
unknown clinic -> 404.
"""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.deps import AuditSource, get_audit_data
from api.main import create_app

CLINIC = "TINY_CLINIC"


@pytest.fixture
def tiny_cube() -> pd.DataFrame:
    """One clinic, day thu, hours 8-10, two block groups.

    bg A (250130001001) is reachable at 8 and 10; bg B (250150002002) at 9 only.
    The hourly reachable set is therefore different per hour -> shares differ.
    """
    rows = []
    reach = {
        ("250130001001", 8): True, ("250130001001", 9): False, ("250130001001", 10): True,
        ("250150002002", 8): False, ("250150002002", 9): True, ("250150002002", 10): False,
    }
    for (bg, hour), ok in reach.items():
        rows.append({
            "clinic_id": CLINIC, "visit_type": "primary_care", "day": "thu",
            "hour": hour, "bg_geoid": bg, "reachable": ok,
            "reason": "ok" if ok else "too_slow",
        })
    return pd.DataFrame(rows)


@pytest.fixture
def tiny_origins() -> pd.DataFrame:
    return pd.DataFrame([
        {"bg_geoid": "250130001001", "lat": 42.1, "lon": -72.6, "carless_adults": 100,
         "pop": 400, "ej_flag": 1, "lep_pct": 0.20, "age65_pct": 0.10},
        {"bg_geoid": "250150002002", "lat": 42.2, "lon": -72.7, "carless_adults": 300,
         "pop": 900, "ej_flag": 0, "lep_pct": 0.05, "age65_pct": 0.30},
    ])


@pytest.fixture
def client(monkeypatch, tiny_cube, tiny_origins) -> TestClient:
    monkeypatch.setenv("CARELEAP_DATA", "real")
    app = create_app()
    app.dependency_overrides[get_audit_data] = lambda: AuditSource(
        mode="real", cube=tiny_cube, origins=tiny_origins
    )
    return TestClient(app)


# --------------------------------------------------------------------------- #
# GET /audit
# --------------------------------------------------------------------------- #
def test_audit_real_shape_and_weighting(client):
    r = client.get("/audit", params={"clinic": CLINIC, "community": "all", "day": "thu"})
    assert r.status_code == 200
    body = r.json()

    hours = {c["hour"]: c for c in body["cells"]}
    assert set(hours) == {8, 9, 10}

    # n is the car-less adults in the community (100 + 300), the same for every hour.
    assert all(c["n"] == 400 for c in body["cells"])
    # reached is weighted by carless_adults: hour 8 -> only bg A (100).
    assert hours[8]["reached"] == 100
    assert hours[9]["reached"] == 300          # only bg B reachable at 9
    assert hours[10]["reached"] == 100
    # share = reached / n, inside [0, 1].
    assert hours[8]["share"] == pytest.approx(100 / 400)
    assert hours[9]["share"] == pytest.approx(300 / 400)
    assert all(0.0 <= c["share"] <= 1.0 for c in body["cells"])


def test_audit_real_equity_groups(client):
    body = client.get("/audit", params={"clinic": CLINIC, "community": "all", "day": "thu"}).json()
    equity = body["equity"]
    assert set(equity) == {"ej", "lep", "age65", "zero_veh"}
    for group in equity.values():
        assert 0.0 <= group["share"] <= 1.0
        assert group["n"] >= 0
    # zero_veh n == all car-less adults; ej n == car-less adults in EJ bgs (only bg A).
    assert equity["zero_veh"]["n"] == 400
    assert equity["ej"]["n"] == 100


def test_audit_real_sources_have_vintage(client):
    body = client.get("/audit", params={"clinic": CLINIC, "community": "all", "day": "thu"}).json()
    assert body["sources"]
    assert all(s["name"] and s["vintage"] for s in body["sources"])


def test_audit_real_unknown_clinic_is_404(client):
    r = client.get("/audit", params={"clinic": "NOPE", "community": "all", "day": "thu"})
    assert r.status_code == 404


def test_audit_real_unknown_community_is_404(client):
    r = client.get("/audit", params={"clinic": CLINIC, "community": "atlantis", "day": "thu"})
    assert r.status_code == 404


# --------------------------------------------------------------------------- #
# POST /whatif
# --------------------------------------------------------------------------- #
def test_whatif_moving_a_block_changes_the_hour_set(client):
    """Moving the 09:00 block to 10:00 drops 9 and adds 10 to the computed hours."""
    base = client.get("/audit", params={"clinic": CLINIC, "community": "all", "day": "thu"}).json()
    base_hours = {c["hour"] for c in base["cells"]}
    assert base_hours == {8, 9, 10}

    r = client.post("/whatif", json={"clinic": CLINIC, "shift": {"block": "thu-09", "to": 10}})
    assert r.status_code == 200
    moved_hours = {c["hour"] for c in r.json()["cells"]}
    assert 9 not in moved_hours        # the 09:00 block was moved away
    assert 10 in moved_hours
    assert moved_hours != base_hours


def test_whatif_real_unknown_clinic_is_404(client):
    r = client.post("/whatif", json={"clinic": "NOPE", "shift": {"block": "thu-08", "to": 9}})
    assert r.status_code == 404


def test_whatif_real_bad_block_hour_is_422(client):
    # thu-11 is not in the clinic's schedule (hours are 8-10) -> 422.
    r = client.post("/whatif", json={"clinic": CLINIC, "shift": {"block": "thu-11", "to": 9}})
    assert r.status_code == 422


def test_whatif_real_target_hour_outside_cube_is_422(client):
    r = client.post("/whatif", json={"clinic": CLINIC, "shift": {"block": "thu-08", "to": 15}})
    assert r.status_code == 422


# ---- GET /audit/blockgroups, GET /clinics (web Audit screen) ------------- #
def test_blockgroups_day_share_is_fraction_of_hours(client):
    r = client.get("/audit/blockgroups", params={"clinic": CLINIC, "day": "thu"})
    assert r.status_code == 200
    body = r.json()
    by_bg = {f["bg_geoid"]: f for f in body["features"]}
    assert by_bg["250130001001"]["share"] == pytest.approx(2 / 3)
    assert by_bg["250150002002"]["share"] == pytest.approx(1 / 3)
    assert all(0.0 <= f["share"] <= 1.0 and f["desert"] is False for f in body["features"])
    assert body["sources"] and all(s["vintage"] for s in body["sources"])


def test_blockgroups_single_hour_and_unknown_hour(client):
    r = client.get("/audit/blockgroups", params={"clinic": CLINIC, "day": "thu", "hour": 9})
    shares = {f["bg_geoid"]: f["share"] for f in r.json()["features"]}
    assert shares == {"250130001001": 0.0, "250150002002": 1.0}
    assert client.get("/audit/blockgroups",
                      params={"clinic": CLINIC, "day": "thu", "hour": 15}).status_code == 404


def test_blockgroups_marks_transit_desert(monkeypatch, tiny_cube, tiny_origins):
    from engine.audit import NO_STOP_REASON
    cube = tiny_cube.copy()
    cube.loc[cube.bg_geoid == "250150002002", ["reachable", "reason"]] = [False, NO_STOP_REASON]
    monkeypatch.setenv("CARELEAP_DATA", "real")
    app = create_app()
    app.dependency_overrides[get_audit_data] = lambda: AuditSource(mode="real", cube=cube,
                                                                   origins=tiny_origins)
    feats = {f["bg_geoid"]: f for f in TestClient(app).get(
        "/audit/blockgroups", params={"clinic": CLINIC, "day": "thu"}).json()["features"]}
    assert feats["250150002002"]["desert"] is True
    assert feats["250130001001"]["desert"] is False


def test_clinics_lists_clinic_stops(client):
    r = client.get("/clinics")
    assert r.status_code == 200
    ids = {c["clinic_id"] for c in r.json()["clinics"]}
    assert "BAY_GI_SPRINGFIELD" in ids
    assert r.json()["sources"][0]["vintage"]


# ---- GET /suggest (optimizer behind the Suggest panel) -------------------- #
def test_suggest_moves_a_block_and_is_never_worse(client):
    r = client.get("/suggest", params={"clinic": CLINIC, "day": "thu", "k": 1, "blocks": "9"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["suggested_score"] >= body["baseline_score"]
    assert body["baseline_blocks"] == [9]
    for ch in body["changes"]:
        assert ch["change"]["block"] == "thu-09" and ch["sources"]


def test_suggest_rejects_bad_blocks_and_unknown_clinic(client):
    assert client.get("/suggest", params={"clinic": CLINIC, "day": "thu", "blocks": "x"}).status_code == 422
    assert client.get("/suggest", params={"clinic": "NOPE", "day": "thu"}).status_code == 404


def test_suggest_unavailable_in_mock_mode(monkeypatch):
    monkeypatch.setenv("CARELEAP_DATA", "mock")
    assert TestClient(create_app()).get("/suggest", params={"clinic": "c", "day": "mon"}).status_code == 503
