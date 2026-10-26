"""Unit tests for GET /rural in REAL mode (no real caches needed).

Tiny cube / origins / towns / rural tables are injected through dependency_overrides,
so these run in CI. They pin the contract (docs/contracts.md §3 /rural): the four
verdicts and their rule, shares in [0, 1], the town filter, 404 on an unknown town,
summary totals that add up, and a non-empty sources list with a vintage.
"""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from hypothesis import given, strategies as st

from api.deps import RuralSource, get_rural_data
from api.main import create_app
from engine.rural import VERDICTS, _verdict, rural

A, B, C, D = "250110001001", "250110002002", "250130003003", "250150004004"


@pytest.fixture
def tiny_cube() -> pd.DataFrame:
    # A reachable at one hour; B never (no stop); C no cube rows at all; D never (too slow)
    rows = [
        {"bg_geoid": A, "hour": 8, "reachable": True, "reason": "ok"},
        {"bg_geoid": A, "hour": 9, "reachable": False, "reason": "no return"},
        {"bg_geoid": B, "hour": 8, "reachable": False, "reason": "origin resolves to no stop within walk limit"},
        {"bg_geoid": B, "hour": 9, "reachable": False, "reason": "origin resolves to no stop within walk limit"},
        {"bg_geoid": D, "hour": 8, "reachable": False, "reason": "too slow"},
    ]
    for r in rows:
        r.update({"clinic_id": "TINY", "visit_type": "primary_care", "day": "thu"})
    return pd.DataFrame(rows)


@pytest.fixture
def tiny_origins() -> pd.DataFrame:
    return pd.DataFrame([
        {"bg_geoid": A, "lat": 42.59, "lon": -72.60, "carless_adults": 100, "pop": 400, "ej_flag": 1, "lep_pct": 0.1, "age65_pct": 0.2},
        {"bg_geoid": B, "lat": 42.70, "lon": -72.92, "carless_adults": 20, "pop": 80, "ej_flag": 0, "lep_pct": 0.0, "age65_pct": 0.4},
        {"bg_geoid": C, "lat": 42.10, "lon": -72.59, "carless_adults": 300, "pop": 900, "ej_flag": 1, "lep_pct": 0.3, "age65_pct": 0.1},
        {"bg_geoid": D, "lat": 42.33, "lon": -72.64, "carless_adults": 50, "pop": 200, "ej_flag": 0, "lep_pct": 0.0, "age65_pct": 0.3},
    ])


@pytest.fixture
def tiny_towns() -> pd.DataFrame:
    return pd.DataFrame([
        {"bg_geoid": A, "town": "Greenfield", "town_geoid": "2501127900", "county": "Franklin", "method": "polygon"},
        {"bg_geoid": B, "town": "Rowe", "town_geoid": "2501158720", "county": "Franklin", "method": "polygon"},
        {"bg_geoid": C, "town": "Springfield", "town_geoid": "2501367000", "county": "Hampden", "method": "polygon"},
        {"bg_geoid": D, "town": "Hadley", "town_geoid": "2501527900", "county": "Hampshire", "method": "nearest"},
    ])


@pytest.fixture
def tiny_coverage() -> pd.DataFrame:
    # Rowe: nothing at all. Hadley: assisted only. Springfield: not in the table.
    return pd.DataFrame([
        {"town": "Greenfield", "county": "Franklin", "coverage_tier": "demand_response", "has_any_option": True,
         "dial_a_ride": "FRTA demand response", "coa_driver": "", "pt1": "MassHealth PT-1",
         "source_url": "https://frta.org", "verified_by": "web", "date": "2026-10-24"},
        {"town": "Rowe", "county": "Franklin", "coverage_tier": "none", "has_any_option": False,
         "dial_a_ride": "", "coa_driver": "", "pt1": "", "source_url": "https://example.org/rowe",
         "verified_by": "phone", "date": "2026-10-24"},
        {"town": "Hadley", "county": "Hampshire", "coverage_tier": "assisted_only", "has_any_option": True,
         "dial_a_ride": "", "coa_driver": "Hadley COA van", "pt1": "MassHealth PT-1",
         "source_url": "https://example.org/hadley", "verified_by": "web", "date": "2026-10-23"},
    ])


@pytest.fixture
def tiny_options(tiny_coverage) -> pd.DataFrame:
    return tiny_coverage.drop(columns=["coverage_tier", "has_any_option"])


@pytest.fixture
def client(monkeypatch, tiny_cube, tiny_origins, tiny_towns, tiny_coverage, tiny_options) -> TestClient:
    monkeypatch.setenv("CARELEAP_DATA", "real")
    app = create_app()
    app.dependency_overrides[get_rural_data] = lambda: RuralSource(
        mode="real", cube=tiny_cube, origins=tiny_origins, towns=tiny_towns,
        coverage=tiny_coverage, options=tiny_options)
    return TestClient(app)


def _by_bg(body):
    return {f["bg_geoid"]: f for f in body["features"]}


def test_verdict_rule_per_block_group(client):
    r = client.get("/rural")
    assert r.status_code == 200
    f = _by_bg(r.json())
    assert f[A]["verdict"] == "transit" and 0.0 < f[A]["transit_share"] <= 1.0
    assert f[B]["verdict"] == "none" and f[B]["desert"] is True
    assert f[C]["verdict"] == "not_assessed" and f[C]["transit_share"] == 0.0  # no cube rows, Hampden
    assert f[D]["verdict"] == "assisted_only" and f[D]["coverage_tier"] == "assisted_only"
    assert all(0.0 <= x["transit_share"] <= 1.0 for x in f.values())
    assert all(x["verdict"] in VERDICTS for x in f.values())


def test_summary_adds_up_and_sources_have_vintage(client):
    body = client.get("/rural").json()
    s = body["summary"]
    assert s["n_bg"] == 4 and s["carless_adults"] == 470
    assert sum(v["n_bg"] for v in s["by_verdict"].values()) == s["n_bg"]
    assert sum(v["carless_adults"] for v in s["by_verdict"].values()) == s["carless_adults"]
    assert s["by_verdict"]["none"] == {"n_bg": 1, "carless_adults": 20}
    assert body["towns_available"] == ["Greenfield", "Hadley", "Rowe", "Springfield"]
    assert body["sources"] and all(src["vintage"] for src in body["sources"])
    assert any("rural_options" in src["name"] for src in body["sources"])


def test_town_filter_and_options_are_cited(client):
    body = client.get("/rural", params={"town": "rowe"}).json()  # case-insensitive
    assert body["town"] == "rowe"
    assert [f["bg_geoid"] for f in body["features"]] == [B]
    assert len(body["options"]) == 1
    opt = body["options"][0]
    assert opt["town"] == "Rowe" and opt["has_any_option"] is False and opt["source_url"]
    assert body["towns_available"] == ["Greenfield", "Hadley", "Rowe", "Springfield"]  # unfiltered list


def test_unknown_town_is_404(client):
    r = client.get("/rural", params={"town": "Atlantis"})
    assert r.status_code == 404


def test_mock_mode_is_empty_and_labelled(monkeypatch):
    monkeypatch.setenv("CARELEAP_DATA", "mock")
    from api.deps import _load_cube_origins
    _load_cube_origins.cache_clear()
    r = TestClient(create_app()).get("/rural")
    assert r.status_code == 200
    body = r.json()
    assert body["features"] == [] and body["summary"]["n_bg"] == 0
    assert body["sources"][0]["vintage"] == "illustrative"


@given(share=st.floats(min_value=0.0, max_value=1.0), in_table=st.booleans(), has_any=st.booleans())
def test_verdict_rule_properties(share, in_table, has_any):
    v = _verdict(share, in_table, has_any)
    assert v in VERDICTS
    assert (v == "transit") == (share > 0)
    if v == "none":
        assert in_table and not has_any and share == 0
    if v == "not_assessed":
        assert not in_table and share == 0


def test_engine_rural_rejects_unknown_town(tiny_cube, tiny_origins, tiny_towns, tiny_coverage, tiny_options):
    from engine.rural import RuralDataError
    with pytest.raises(RuralDataError):
        rural(tiny_cube, tiny_origins, tiny_towns, tiny_coverage, tiny_options, town="Nowhere")
