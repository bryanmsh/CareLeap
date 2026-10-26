"""Tests for GET /report (spec: .kiro/specs/audit-report-pdf)."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from api.routers.report import clinic_section, render_pdf, report_html
from engine.audit import CUBE_PATH, ORIGINS_PATH
from planner.guardrails import find_banned

TAG = re.compile(r"<[^>]+>")
REAL = CUBE_PATH.is_file() and ORIGINS_PATH.is_file()


def _weasy_ok() -> bool:
    try:
        render_pdf("<p>x</p>")
        return True
    except RuntimeError:
        return False


WEASY = _weasy_ok()


def _client(monkeypatch, mode: str) -> TestClient:
    monkeypatch.setenv("CARELEAP_DATA", mode)
    from api.deps import _load_cube_origins
    _load_cube_origins.cache_clear()
    from api.main import create_app
    return TestClient(create_app())


def _text(doc: str) -> str:
    return " ".join(TAG.sub(" ", doc).split())


def test_mock_report_is_labelled_mock(monkeypatch):
    r = _client(monkeypatch, "mock").get("/report", params={"format": "html"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert "MOCK DATA" in r.text
    assert not find_banned(_text(r.text))


def test_section_escapes_untrusted_text():
    data = {"cells": [{"day": "mon", "hour": 8, "share": 0.5, "n": 2, "reached": 1}],
            "equity": {g: {"share": 0.1, "n": 1} for g in ("ej", "lep", "age65", "zero_veh")},
            "equity_ci": None,
            "sources": [{"name": "<b>x</b>", "vintage": "v", "url": None}]}
    html = clinic_section("c1", "<script>alert(1)</script>", "all", "mon", data)
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "not available" in html  # no CI -> said plainly, not invented


@pytest.mark.skipif(not REAL, reason="real cube/origins not present (CI has no data/cache)")
def test_real_report_numbers_equal_audit(monkeypatch):
    c = _client(monkeypatch, "real")
    doc = c.get("/report", params={"format": "html", "day": "thu"}).text
    sections = re.findall(r'<section class="clinic" data-clinic="([^"]+)">(.*?)</section>', doc, re.S)
    import pandas as pd
    clinics = sorted(pd.read_parquet(CUBE_PATH).clinic_id.unique())
    assert [cid for cid, _ in sections] == clinics  # one page per clinic in the cube
    for cid, body in sections:
        a = c.get("/audit", params={"clinic": cid, "community": "all", "day": "thu"}).json()
        text = _text(body)
        for cell in a["cells"]:
            assert f"{cell['hour']:02d}:00 {cell['share'] * 100:.1f}% {cell['reached']:,} {cell['n']:,}" in text
        for g, e in a["equity"].items():
            assert f"{e['share'] * 100:.1f}%" in text
            if a["equity_ci"]:
                ci = a["equity_ci"][g]
                assert f"{ci['lo'] * 100:.1f}% – {ci['hi'] * 100:.1f}%" in text
        for s in a["sources"]:
            assert s["name"] in text and s["vintage"] in text
        assert not find_banned(text)


@pytest.mark.skipif(not REAL, reason="real cube/origins not present")
def test_unknown_clinic_is_404(monkeypatch):
    r = _client(monkeypatch, "real").get("/report", params={"clinic": "NOPE", "format": "html"})
    assert r.status_code == 404


def test_pdf_or_honest_503(monkeypatch):
    r = _client(monkeypatch, "mock").get("/report")
    if WEASY:
        assert r.status_code == 200 and r.content.startswith(b"%PDF")
    else:
        assert r.status_code == 503 and "format=html" in r.json()["detail"]


@pytest.mark.skipif(not WEASY, reason="WeasyPrint system libraries (Pango/GTK) not installed")
def test_pdf_has_one_page_per_clinic():
    data = {"cells": [{"day": "mon", "hour": 8, "share": 0.5, "n": 2, "reached": 1}],
            "equity": {g: {"share": 0.1, "n": 1} for g in ("ej", "lep", "age65", "zero_veh")},
            "equity_ci": None, "sources": [{"name": "s", "vintage": "v", "url": None}]}
    pdf = render_pdf(report_html([clinic_section(f"c{i}", f"C{i}", "all", "mon", data) for i in range(3)]))
    assert len(re.findall(rb"/Type\s*/Page[^s]", pdf)) == 3
