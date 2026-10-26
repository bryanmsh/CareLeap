"""Cube -> audit aggregation. The ONE place that turns cube.parquet into the
GET /audit shape (docs/contracts.md §3), so /audit, /whatif, reach-mcp and the
schedule optimizer can never disagree about a number.

Pure functions over pandas DataFrames:
    cube    : clinic_id, visit_type, day, hour, bg_geoid, reachable, reason
    origins : bg_geoid, lat, lon, carless_adults, pop, ej_flag, lep_pct, age65_pct

Weighting (documented in .kiro/specs/reachability-cube/design.md):
    - every share is weighted by carless_adults (people, not block groups)
    - cell n        = car-less adults in the community
    - cell reached  = car-less adults in block groups where the slot is reachable
    - equity groups (whole day, averaged over the clinic's hours):
        ej       : car-less adults in EJ block groups
        lep      : car-less adults x lep_pct     (expected limited-English adults)
        age65    : car-less adults x age65_pct   (expected 65+ adults)
        zero_veh : all car-less adults
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from engine.paths import ROOT, cache_dir

# CARELEAP_CACHE_DIR redirects these (make demo serves data/snapshots/demo-v1/).
CUBE_PATH = cache_dir() / "cube.parquet"
ORIGINS_PATH = cache_dir() / "origins.parquet"
MANIFEST_PATH = (cache_dir() / "manifest.json") if (cache_dir() / "manifest.json").exists() else ROOT / "data" / "raw" / "manifest.json"
PVTA_FEED_INFO = cache_dir() / "pvta" / "feed_info.txt"

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
COUNTY_FIPS = {"hampden": "25013", "hampshire": "25015", "franklin": "25011"}


class AuditDataError(LookupError):
    """Requested clinic/day/community has no data in the cube."""


# --------------------------------------------------------------------------- #
# loading
# --------------------------------------------------------------------------- #
def load_cube(path: Path = CUBE_PATH) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df["bg_geoid"] = df["bg_geoid"].astype(str)
    df["hour"] = df["hour"].astype(int)
    df["reachable"] = df["reachable"].astype(bool)
    return df


def load_origins(path: Path = ORIGINS_PATH, with_moe: bool = True) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df["bg_geoid"] = df["bg_geoid"].astype(str)
    if with_moe:
        # Attach ACS 90% margins (engine/equity.py) when data/raw has them; else the
        # audit simply returns equity_ci = None.
        from engine.equity import MOE_COLUMNS, load_bg_moe

        moe = load_bg_moe()
        if moe is not None:
            df = df.merge(moe[["bg_geoid", *MOE_COLUMNS]], on="bg_geoid", how="left")
            df[list(MOE_COLUMNS)] = df[list(MOE_COLUMNS)].fillna(0.0)
    return df


def filter_community(origins: pd.DataFrame, community: str) -> pd.DataFrame:
    """community: 'all' | county name (hampden/hampshire/franklin) | GEOID prefix digits."""
    key = community.strip().lower()
    if key in ("all", "*", ""):
        return origins
    if key in COUNTY_FIPS:
        return origins[origins.bg_geoid.str.startswith(COUNTY_FIPS[key])]
    if key.isdigit():
        return origins[origins.bg_geoid.str.startswith(key)]
    raise AuditDataError(f"unknown community {community!r} (use all, a county name, or a GEOID prefix)")


# --------------------------------------------------------------------------- #
# provenance
# --------------------------------------------------------------------------- #
def sources() -> list[dict[str, Any]]:
    """Source + vintage for every number /audit returns (guardrail)."""
    manifest: dict[str, Any] = {}
    if MANIFEST_PATH.exists():
        try:
            manifest = json.loads(MANIFEST_PATH.read_text())
        except json.JSONDecodeError:
            manifest = {}

    def _vintage(key: str, fallback: str) -> str:
        entry = manifest.get(key) if isinstance(manifest, dict) else None
        if isinstance(entry, dict):
            for k in ("vintage", "downloaded", "date", "downloaded_at"):
                if entry.get(k):
                    return str(entry[k])
        return fallback

    pvta_vintage = _vintage("pvta_gtfs", "unknown")
    if PVTA_FEED_INFO.exists():
        try:
            row = next(iter(pd.read_csv(PVTA_FEED_INFO, dtype=str).to_dict("records")))
            start, end = row.get("feed_start_date"), row.get("feed_end_date")
            if start and end:
                pvta_vintage = f"{start}..{end}"
        except (StopIteration, ValueError):
            pass
    return [
        {"name": "PVTA GTFS", "vintage": pvta_vintage, "url": "https://www.pvta.com/"},
        {"name": "ACS 5-yr B25044/B01001/C16002", "vintage": _vintage("acs_bg", "ACS 2024 5-year"),
         "url": "https://api.census.gov/data/2024/acs/acs5"},
        {"name": "MassGIS Environmental Justice 2020", "vintage": _vintage("ej_west", "2020"),
         "url": "https://www.mass.gov/info-details/massgis-data-2020-environmental-justice-populations"},
        {"name": "CareLeap reachability cube (engine.round_trip)", "vintage": "built from the feed above",
         "url": None},
        {"name": "ACS 5-yr 90% margins of error (equity_ci)",
         "vintage": _vintage("acs_bg_moe", "ACS 2024 5-year (90% MOE)"),
         "url": "https://api.census.gov/data/2024/acs/acs5"},
        {"name": "Census ACS General Handbook, ch. 8 (MOE formulas for equity_ci)",
         "vintage": "September 2020",
         "url": "https://www.census.gov/programs-surveys/acs/library/handbooks/general.html"},
    ]


# --------------------------------------------------------------------------- #
# aggregation
# --------------------------------------------------------------------------- #
def _join(cube: pd.DataFrame, origins: pd.DataFrame, clinic: str, day: str) -> pd.DataFrame:
    sub = cube[(cube.clinic_id == clinic) & (cube.day == day)]
    if sub.empty:
        raise AuditDataError(f"no cube rows for clinic={clinic!r} day={day!r}")
    joined = sub.merge(origins[["bg_geoid", "carless_adults", "ej_flag", "lep_pct", "age65_pct"]],
                       on="bg_geoid", how="inner")
    if joined.empty:
        raise AuditDataError(f"no origins in this community for clinic={clinic!r}")
    return joined


def hour_cells(cube: pd.DataFrame, origins: pd.DataFrame, clinic: str, day: str,
               hours: list[int] | None = None) -> list[dict[str, Any]]:
    """One cell per hour: share of car-less adults who can reach and return."""
    j = _join(cube, origins, clinic, day)
    n = int(origins.carless_adults.sum())
    cells = []
    for hour in sorted(hours if hours is not None else j.hour.unique()):
        h = j[j.hour == hour]
        reached = int(h.loc[h.reachable, "carless_adults"].sum())
        cells.append({"day": day, "hour": int(hour), "share": (reached / n) if n else 0.0,
                      "n": n, "reached": reached})
    return cells


def equity(cube: pd.DataFrame, origins: pd.DataFrame, clinic: str, day: str,
           hours: list[int] | None = None) -> dict[str, dict[str, Any]]:
    """Equity split over the day, averaged across the clinic's hours."""
    j = _join(cube, origins, clinic, day)
    if hours is not None:
        j = j[j.hour.isin(hours)]
    n_hours = max(j.hour.nunique(), 1)
    weights = {
        "ej": origins.carless_adults * origins.ej_flag.astype(bool),
        "lep": origins.carless_adults * origins.lep_pct,
        "age65": origins.carless_adults * origins.age65_pct,
        "zero_veh": origins.carless_adults.astype(float),
    }
    out: dict[str, dict[str, Any]] = {}
    for group, w in weights.items():
        wmap = dict(zip(origins.bg_geoid, w))
        n = float(sum(wmap.values()))
        reached = float(sum(wmap.get(bg, 0.0) for bg in j.loc[j.reachable, "bg_geoid"])) / n_hours
        out[group] = {"share": min(max(reached / n, 0.0), 1.0) if n else 0.0, "n": int(round(n))}
    return out


def reach_fraction(cube: pd.DataFrame, origins: pd.DataFrame, clinic: str, day: str,
                   hours: list[int] | None = None) -> dict[str, float]:
    """bg_geoid -> fraction of the clinic's hours that day the block group is reachable.

    Same averaging as equity(): reached weight summed over hours / number of hours."""
    j = _join(cube, origins, clinic, day)
    if hours is not None:
        j = j[j.hour.isin(hours)]
    n_hours = max(j.hour.nunique(), 1)
    counts = j.loc[j.reachable].groupby("bg_geoid").size()
    return {str(bg): float(c) / n_hours for bg, c in counts.items()}


def audit(cube: pd.DataFrame, origins: pd.DataFrame, clinic: str, community: str, day: str,
          hours: list[int] | None = None) -> dict[str, Any]:
    """The full GET /audit payload.

    equity_ci (M3, engine/equity.py): 90% intervals from ACS margins of error, or None
    when the origins carry no MOE columns (MOE data not built)."""
    from engine.equity import equity_ci  # local: keeps engine.audit importable on its own

    orig = filter_community(origins, community)
    return {
        "cells": hour_cells(cube, orig, clinic, day, hours),
        "equity": equity(cube, orig, clinic, day, hours),
        "equity_ci": equity_ci(reach_fraction(cube, orig, clinic, day, hours), orig),
        "sources": sources(),
    }


NO_STOP_REASON = "origin resolves to no stop within walk limit"


def blockgroups(cube: pd.DataFrame, origins: pd.DataFrame, clinic: str, day: str,
                hour: int | None = None, community: str = "all") -> dict[str, Any]:
    """Per-block-group view for the map (GET /audit/blockgroups).

    share  : with `hour`, 1.0/0.0 = that slot is reachable and returnable;
             without it, the fraction of the clinic's hours that day that are.
    desert : no PVTA stop within the walk limit (the cube's own reason code).
    """
    orig = filter_community(origins, community)
    sub = cube[(cube.clinic_id == clinic) & (cube.day == day)]
    if sub.empty:
        raise AuditDataError(f"no cube rows for clinic={clinic!r} day={day!r}")
    if hour is not None:
        sub = sub[sub.hour == hour]
        if sub.empty:
            raise AuditDataError(f"hour {hour} is not in the clinic's schedule")
    g = sub.groupby("bg_geoid").agg(share=("reachable", "mean"),
                                    desert=("reason", lambda r: bool((r == NO_STOP_REASON).all())))
    j = orig[["bg_geoid", "lat", "lon", "carless_adults"]].merge(g, left_on="bg_geoid",
                                                                  right_index=True, how="inner")
    features = [
        {"bg_geoid": r.bg_geoid, "lat": float(r.lat), "lon": float(r.lon),
         "carless_adults": int(r.carless_adults), "share": float(min(max(r.share, 0.0), 1.0)),
         "desert": bool(r.desert)}
        for r in j.itertuples(index=False)
    ]
    return {"features": features, "sources": sources()}


def whatif(cube: pd.DataFrame, origins: pd.DataFrame, clinic: str, block: str, to: int,
           community: str = "all") -> dict[str, Any]:
    """POST /whatif: move the block `day-HH` to hour `to` and recompute.

    The clinic's day is modelled as one appointment block per cube hour. Moving
    `mon-08` to 10 removes the 08:00 block and offers it at 10:00 instead; that
    block's cell is recomputed from the cube's 10:00 reachability. Same shape as
    /audit, so the UI reuses one renderer.
    """
    day, hh = block.split("-", 1)
    frm = int(hh)
    available = sorted(cube[(cube.clinic_id == clinic) & (cube.day == day)].hour.unique())
    if frm not in available:
        raise AuditDataError(f"block {block!r} is not in the clinic's schedule")
    if to not in available:
        raise AuditDataError(f"hour {to} is outside the cube's hours {available}")
    hours = [h for h in available if h != frm]
    if to not in hours:
        hours.append(to)
    return audit(cube, origins, clinic, community, day, sorted(hours))
