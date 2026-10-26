"""GET /report — CHNA-ready audit report, one page per clinic (owner: M3).

Spec: .kiro/specs/audit-report-pdf/. Every number on the page comes from the SAME
engine.audit.audit(...) call that serves GET /audit (no copies, no hard-coded
findings), with its sources + vintages and a short method box.

    GET /report?clinic=A&clinic=B&community=all&day=thu            -> application/pdf
    GET /report?...&format=html                                     -> text/html

PDF rendering uses WeasyPrint, which needs the Pango/GTK system libraries. When they
are missing the PDF request answers 503 (the HTML view still works); nothing is faked.
Logistics only: the page reports reachable visit-hours, never attendance or clinical
outcomes.
"""

from __future__ import annotations

import html
from collections.abc import Sequence
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from api.deps import AuditSource, get_audit_data
from api.routers.clinics import load_clinics
from api.schemas import Day
from engine.audit import AuditDataError, audit as engine_audit

router = APIRouter(tags=["report"])

GROUP_LABELS = {
    "ej": "Environmental-justice neighborhoods (Census block groups)",
    "lep": "Limited-English households",
    "age65": "Adults 65+",
    "zero_veh": "All adults with no car in the household",
}
DAY_NAMES = {"mon": "Monday", "tue": "Tuesday", "wed": "Wednesday", "thu": "Thursday",
             "fri": "Friday", "sat": "Saturday", "sun": "Sunday"}

METHOD = (
    "Each cell is the share of adults with no car in the household (\"car-less adults\", an "
    "ACS 2024 5-year estimate) in the community who can reach the clinic by scheduled bus, "
    "arrive before the appointment, and get home the same day (engine.round_trip, PVTA + FRTA "
    "GTFS). Shares are weighted by people, not block groups. The 90% range on each equity "
    "group is a confidence interval carried from the published ACS margins of error (Census "
    "ACS General Handbook, ch. 8). Reachability is not attendance: this measures whether the "
    "trip is possible, not whether a visit happens."
)
RANGE_NOTE = "Wide ranges mean small samples: read them as uncertain, not as findings."
FOOTER = "Logistics only. Your care team decides your care. Synthetic patients only; no PHI."

CSS = """
@page { size: Letter; margin: 0.6in; @bottom-center { content: counter(page) " / " counter(pages);
        font-size: 8pt; color: #555; } }
body { font-family: "DejaVu Sans", Arial, sans-serif; font-size: 10pt; color: #111; }
section.clinic { page-break-after: always; }
section.clinic:last-of-type { page-break-after: auto; }
h1 { font-size: 16pt; margin: 0 0 4pt; } h2 { font-size: 11pt; margin: 12pt 0 4pt; }
.meta { color: #333; margin-bottom: 8pt; }
table { border-collapse: collapse; width: 100%; } th, td { border: 1px solid #999;
        padding: 2pt 5pt; text-align: right; } th:first-child, td:first-child { text-align: left; }
.method, .footer { font-size: 8.5pt; color: #333; } .mock { color: #a00; font-weight: bold; }
ul.sources { font-size: 8.5pt; padding-left: 14pt; }
"""


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _e(s: Any) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def clinic_section(clinic_id: str, clinic_name: str, community: str, day: str,
                   data: dict[str, Any], mock: bool = False) -> str:
    """One page for one clinic, from an /audit payload."""
    rows = "".join(
        f"<tr><td>{c['hour']:02d}:00</td><td>{_pct(c['share'])}</td>"
        f"<td>{c['reached']:,}</td><td>{c['n']:,}</td></tr>"
        for c in data["cells"]
    )
    ci = data.get("equity_ci") or {}
    eq_rows = []
    for g, label in GROUP_LABELS.items():
        e = data["equity"][g]
        c = ci.get(g)
        rng = f"{_pct(c['lo'])} – {_pct(c['hi'])}" if c else "not available"
        eq_rows.append(f"<tr><td>{_e(label)}</td><td>{_pct(e['share'])}</td><td>{rng}</td>"
                       f"<td>{e['n']:,}</td></tr>")
    sources = "".join(
        f"<li>{_e(s['name'])} — {_e(s['vintage'])}"
        + (f" — {_e(s['url'])}" if s.get("url") else "") + "</li>"
        for s in data["sources"]
    )
    banner = '<p class="mock">MOCK DATA — illustrative, not a finding.</p>' if mock else ""
    return (
        f'<section class="clinic" data-clinic="{_e(clinic_id)}">'
        f"{banner}<h1>{_e(clinic_name)}</h1>"
        f'<p class="meta">Clinic id {_e(clinic_id)} · Community: {_e(community)} · '
        f"{_e(DAY_NAMES.get(day, day))}</p>"
        "<h2>Who can get there and back by bus, by appointment hour</h2>"
        "<table><thead><tr><th>Hour</th><th>Reachable share</th><th>Car-less adults reached</th>"
        f"<th>Car-less adults</th></tr></thead><tbody>{rows}</tbody></table>"
        "<h2>Equity view (whole day, averaged across the appointment hours above)</h2>"
        "<table><thead><tr><th>Group</th><th>Reachable share</th><th>90% range (margin of error)</th>"
        f"<th>People (n)</th></tr></thead><tbody>{''.join(eq_rows)}</tbody></table>"
        f'<p class="method">{_e(RANGE_NOTE)}</p>'
        f'<h2>Method</h2><p class="method">{_e(METHOD)}</p>'
        f'<h2>Sources</h2><ul class="sources">{sources}</ul>'
        f'<p class="footer">{_e(FOOTER)}</p></section>'
    )


def report_html(sections: Sequence[str], title: str = "CareLeap clinic audit") -> str:
    return (f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>{_e(title)}</title>"
            f"<style>{CSS}</style></head><body>{''.join(sections)}</body></html>")


def render_pdf(doc_html: str) -> bytes:
    """HTML -> PDF via WeasyPrint. Raises RuntimeError when its system libraries are missing."""
    try:
        from weasyprint import HTML  # noqa: PLC0415 - optional, heavy system deps
    except (ImportError, OSError) as exc:
        raise RuntimeError("WeasyPrint is unavailable (needs the Pango/GTK libraries)") from exc
    return HTML(string=doc_html).write_pdf()


def _with_day(data: dict[str, Any], day: str) -> dict[str, Any]:
    return {**data, "cells": [{**c, "day": day} for c in data["cells"]]}


@router.get("/report", summary="CHNA-ready audit report, one page per clinic",
            responses={200: {"content": {"application/pdf": {}, "text/html": {}}}})
def get_report(
    source: Annotated[AuditSource, Depends(get_audit_data)],
    day: Annotated[Day, Query()] = "thu",
    community: Annotated[str, Query(min_length=1, max_length=64)] = "all",
    clinic: Annotated[list[str] | None, Query(max_length=20)] = None,
    format: Annotated[Literal["pdf", "html"], Query()] = "pdf",
) -> Response:
    names = {c.clinic_id: c.clinic_name for c in load_clinics()}
    if source.mode == "mock":
        ids = clinic or ["mock-clinic"]
        sections = [clinic_section(cid, names.get(cid, cid), community, day,
                                   _with_day(source.payload or {}, day), mock=True) for cid in ids]
    else:
        available = sorted(source.cube.clinic_id.unique())
        ids = clinic or available
        sections = []
        for cid in ids:
            try:
                data = engine_audit(source.cube, source.origins, cid, community, day)
            except AuditDataError as exc:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
            sections.append(clinic_section(cid, names.get(cid, cid), community, day, data))
    doc = report_html(sections)
    if format == "html":
        return Response(content=doc, media_type="text/html; charset=utf-8")
    try:
        pdf = render_pdf(doc)
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail=f"{exc}; use format=html, or install the GTK runtime") from exc
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": 'inline; filename="careleap-audit.pdf"'})
