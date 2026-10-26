"""CareLeap feed watch (Kiro Crew heartbeat + expiry alarm). No LLM.

heartbeat(ctx): every 6h. HEAD the PVTA GTFS URL; if its ETag / Last-Modified /
                Content-Length changed since the last run, notify with the diff
                and the re-audit steps. Unchanged -> Skip (silent).
expiry(ctx):    daily. Read the cached feed_info.txt; if the feed ends within
                14 days, notify (Report keeps the job); otherwise Skip.

ctx.message carries the repo path (defaults to the hackachusetts checkout).
Re-auditing is NOT run here: the cube build is ~9 min/clinic, far past a
script timeout. The alert says exactly what to run.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import urllib.request
from pathlib import Path

from kiro_crew.cron_script import Report, Skip

PVTA_URL = "https://www.pvta.com/g_trans/google_transit.zip"
DEFAULT_REPO = "/Users/sumedhjadhav/Documents/Projects/hackachusetts"
STATE = Path(__file__).with_suffix(".state.json")
WARN_DAYS = 14


def _repo(ctx) -> Path:
    return Path((ctx.message or "").strip() or DEFAULT_REPO)


def _head(url: str) -> dict[str, str]:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "careleap-feedwatch"})
    with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 - fixed https URL
        h = r.headers
        return {k: h.get(k, "") for k in ("ETag", "Last-Modified", "Content-Length")}


def heartbeat(ctx) -> None:
    now = _head(PVTA_URL)
    old = json.loads(STATE.read_text()) if STATE.exists() else None
    STATE.write_text(json.dumps(now, indent=2))
    if old is None:
        raise Skip()  # first run: record the baseline only
    changed = {k: (old.get(k), v) for k, v in now.items() if old.get(k) != v}
    if not changed:
        raise Skip()
    diff = "\n".join(f"- {k}: {a!r} -> {b!r}" for k, (a, b) in changed.items())
    ctx.notify(
        "PVTA GTFS changed upstream.\n" + diff +
        f"\n\nRe-audit in {_repo(ctx)}:\n  make data\n  python pipeline/build_cube.py\n  pytest -q",
        session="slack",
    )


def expiry(ctx) -> None:
    info = _repo(ctx) / "data" / "cache" / "pvta" / "feed_info.txt"
    with info.open(newline="") as fh:
        row = next(csv.DictReader(fh))
    end = dt.datetime.strptime(row["feed_end_date"], "%Y%m%d").date()
    days = (end - dt.date.today()).days
    if days > WARN_DAYS:
        raise Skip()
    raise Report(f"PVTA GTFS feed expires {end.isoformat()} ({days} days). "
                 f"Refresh it: make data, then rebuild the cube.")
