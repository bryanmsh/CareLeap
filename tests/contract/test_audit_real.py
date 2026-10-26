"""Real-cube contract test for GET /audit.

Skipped when data/cache/cube.parquet is absent (CI has no cache). When the real
cube IS present, it asserts the endpoint returns the real aggregation and that the
hourly share is NOT flat for BAY_GI_SPRINGFIELD on thu -- a flat curve would mean
the cube degenerated back to a mock/placeholder.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from engine.audit import CUBE_PATH, ORIGINS_PATH

pytestmark = pytest.mark.skipif(
    not (CUBE_PATH.is_file() and ORIGINS_PATH.is_file()),
    reason="real cube/origins not present (CI has no data/cache)",
)

CLINIC = "BAY_GI_SPRINGFIELD"


@pytest.fixture
def real_client(monkeypatch) -> TestClient:
    monkeypatch.setenv("CARELEAP_DATA", "real")
    # drop any cached frames from a previous mode so lru_cache reloads cleanly
    from api.deps import _load_cube_origins
    _load_cube_origins.cache_clear()
    from api.main import create_app
    return TestClient(create_app())


def test_real_audit_is_not_flat(real_client):
    r = real_client.get("/audit", params={"clinic": CLINIC, "community": "all", "day": "thu"})
    assert r.status_code == 200
    body = r.json()

    assert len(body["cells"]) == 12            # hours 7..18
    assert all(c["day"] == "thu" for c in body["cells"])
    assert all(0.0 <= c["share"] <= 1.0 for c in body["cells"])

    shares = [c["share"] for c in body["cells"]]
    assert max(shares) - min(shares) > 0.05, f"hourly share looks flat: {shares}"

    assert set(body["equity"]) == {"ej", "lep", "age65", "zero_veh"}
    assert body["sources"] and all(s["vintage"] for s in body["sources"])


def test_real_whatif_keeps_shape(real_client):
    r = real_client.post("/whatif", json={"clinic": CLINIC, "shift": {"block": "thu-08", "to": 10}})
    assert r.status_code == 200
    body = r.json()
    assert body["cells"] and set(body["equity"]) == {"ej", "lep", "age65", "zero_veh"}


def test_real_audit_equity_ci(real_client):
    """equity_ci (M3): present when data/raw has the ACS margins; every interval holds
    its point estimate, and that estimate equals the plain equity share."""
    from engine.equity import ACS_MOE_PATH

    r = real_client.get("/audit", params={"clinic": CLINIC, "community": "all", "day": "thu"})
    assert r.status_code == 200
    body = r.json()
    if not ACS_MOE_PATH.is_file():
        assert body["equity_ci"] is None
        return
    ci = body["equity_ci"]
    assert set(ci) == {"ej", "lep", "age65", "zero_veh"}
    for g, v in ci.items():
        assert 0.0 <= v["lo"] <= v["share"] <= v["hi"] <= 1.0, g
        assert v["share"] == pytest.approx(body["equity"][g]["share"], abs=1e-9), g
        assert v["n"] == body["equity"][g]["n"], g
        assert v["moe"] >= 0
