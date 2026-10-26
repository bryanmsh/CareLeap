"""Download the raw data for CareLeap (plan.md section 2a).

Run from the repo root:   python scripts/get_data.py
Re-running is safe: files that already exist are skipped (use --force to re-download).
Every file is recorded in data/raw/manifest.json with its URL, download date and sha256.
Uses only the Python standard library, so there is nothing to pip install.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import os
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
MANIFEST = RAW / "manifest.json"

STATE = "25"  # Massachusetts
COUNTIES = {"013": "Hampden", "015": "Hampshire", "011": "Franklin"}
ACS_YEAR = "2024"  # ACS 5-year 2020-2024; uses 2020 block groups, same as TIGER 2024

# ACS variables (labels checked against api.census.gov/data/2024/acs/acs5/variables.json)
ACS_VARS = (
    ["B25044_001E", "B25044_003E", "B25044_010E"]                 # households; owner + renter with no vehicle
    + ["B01003_001E"]                                             # total population
    + [f"B01001_{i:03d}E" for i in (3, 4, 5, 6, 27, 28, 29, 30)]  # under 18 (male + female)
    + [f"B01001_{i:03d}E" for i in list(range(20, 26)) + list(range(44, 50))]  # 65+ (male + female)
    + ["C16002_001E", "C16002_004E", "C16002_007E", "C16002_010E", "C16002_013E"]  # limited-English households
)

EJ_URL = (
    "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/EJ2020/MapServer/0/query?"
    + urllib.parse.urlencode({
        "where": " OR ".join(f"GEOID LIKE '{STATE}{c}%'" for c in COUNTIES),
        "outFields": "GEOID,MUNICIPALITY,TOTAL_POP,PCT_MINORITY,TOTALHH,LIMENGHH,LIMENGHHPCT,BG_MHHI,EJ,EJ_CRIT_DESC",
        "returnGeometry": "false",
        "f": "json",
    })
)

SIMPLE_DOWNLOADS = [
    # (name, url, save_as, unzip_to)
    ("pvta_gtfs", "https://www.pvta.com/g_trans/google_transit.zip", "pvta_gtfs.zip", None),
    ("tiger_bg", "https://www2.census.gov/geo/tiger/TIGER2024/BG/tl_2024_25_bg.zip", "tiger_bg.zip", "tiger_bg"),
    ("portal_healthcare", "https://hackachusetts2026.vercel.app/kits/tracks/healthcare.zip",
     "portal_healthcare.zip", "portal_healthcare"),
    ("ej_west", EJ_URL, "ej_west.json", None),
    # towns (MA county subdivisions) for the rural lens: block group -> town join
    ("tiger_cousub", "https://www2.census.gov/geo/tiger/TIGER2024/COUSUB/tl_2024_25_cousub.zip",
     "tiger_cousub.zip", "tiger_cousub"),
]

# ---------------------------------------------------------------- helpers
def log(msg: str) -> None:
    print(msg, flush=True)

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "careleap/get_data"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()

def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}

def record(manifest: dict, name: str, url: str, path: Path, **extra) -> None:
    safe_url = url.split("&key=")[0]  # never store the API key
    manifest[name] = {
        "url": safe_url,
        "file": str(path.relative_to(ROOT)).replace("\\", "/"),
        "downloaded": dt.datetime.now().isoformat(timespec="seconds"),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        **extra,
    }

def read_census_key() -> str:
    key = os.environ.get("CENSUS_API_KEY", "").strip()
    env = ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("CENSUS_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key or "yourkey" in key:
        sys.exit("ERROR: CENSUS_API_KEY not found. Put CENSUS_API_KEY=<your key> in .env at the repo root.")
    return key

# ---------------------------------------------------------------- validators
def validate_gtfs(path: Path) -> dict:
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        need = {"stops.txt", "routes.txt", "trips.txt", "stop_times.txt"}
        missing = need - names
        if missing:
            raise ValueError(f"GTFS missing {missing}")
        if not ({"calendar.txt", "calendar_dates.txt"} & names):
            raise ValueError("GTFS has neither calendar.txt nor calendar_dates.txt")
        counts = {n: sum(1 for _ in z.open(n)) - 1 for n in sorted(need)}
        window = None
        if "calendar.txt" in names:
            rows = list(csv.DictReader(io.TextIOWrapper(z.open("calendar.txt"), "utf-8-sig")))
            if rows:
                window = [min(r["start_date"] for r in rows), max(r["end_date"] for r in rows)]
    return {"row_counts": counts, "service_window": window}

def validate_tiger(folder: Path) -> dict:
    needed = [folder / f"tl_2024_25_bg.{ext}" for ext in ("shp", "dbf", "shx", "prj")]
    missing = [p.name for p in needed if not p.exists()]
    if missing:
        raise ValueError(f"TIGER missing {missing}")
    with (folder / "tl_2024_25_bg.dbf").open("rb") as f:
        n = int.from_bytes(f.read(8)[4:8], "little")  # record count from the DBF header
    if n < 4000:
        raise ValueError(f"TIGER has only {n} block groups; expected ~5,100 for MA")
    return {"block_groups_MA": n}

def validate_cousub(folder: Path) -> dict:
    needed = [folder / f"tl_2024_25_cousub.{ext}" for ext in ("shp", "dbf", "shx", "prj")]
    missing = [p.name for p in needed if not p.exists()]
    if missing:
        raise ValueError(f"TIGER COUSUB missing {missing}")
    with (folder / "tl_2024_25_cousub.dbf").open("rb") as f:
        n = int.from_bytes(f.read(8)[4:8], "little")
    if n < 300:
        raise ValueError(f"TIGER COUSUB has only {n} rows; expected ~350 MA towns/cities")
    return {"county_subdivisions_MA": n}

def validate_portal(folder: Path) -> dict:
    for sub in ("ej", "hospitals"):
        if not (folder / sub / "data.csv").exists():
            raise ValueError(f"portal kit missing {sub}/data.csv")
    return {"folders": sorted(p.name for p in folder.iterdir() if p.is_dir())}

def validate_ej(path: Path) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    if "error" in d:
        raise ValueError(f"EJ service error: {d['error']}")
    feats = d.get("features", [])
    if d.get("exceededTransferLimit"):
        raise ValueError("EJ query hit the server record limit; results are incomplete")
    if len(feats) < 200 or "GEOID" not in feats[0]["attributes"]:
        raise ValueError(f"EJ result looks wrong ({len(feats)} rows)")
    return {"rows": len(feats), "note": "Layer lists EJ block groups only; absent GEOID => not EJ"}

VALIDATORS = {
    "pvta_gtfs": lambda p, u: validate_gtfs(p),
    "tiger_bg": lambda p, u: validate_tiger(u),
    "portal_healthcare": lambda p, u: validate_portal(u),
    "ej_west": lambda p, u: validate_ej(p),
    "tiger_cousub": lambda p, u: validate_cousub(u),
}

# ---------------------------------------------------------------- steps
def simple_downloads(manifest: dict, force: bool) -> None:
    for name, url, save_as, unzip_to in SIMPLE_DOWNLOADS:
        path = RAW / save_as
        if path.exists() and not force:
            log(f"[skip] {save_as} already exists")
        else:
            log(f"[get ] {name} ...")
            path.write_bytes(fetch(url))
        folder = RAW / unzip_to if unzip_to else None
        if folder and (force or not folder.exists()):
            with zipfile.ZipFile(path) as z:
                z.extractall(folder)
            log(f"[unzip] {save_as} -> {unzip_to}/")
        info = VALIDATORS[name](path, folder)
        record(manifest, name, url, path, validation=info)
        log(f"[ ok ] {name}: {info}")

def acs_download(manifest: dict, force: bool) -> None:
    path = RAW / "acs_bg.csv"
    if path.exists() and not force:
        log("[skip] acs_bg.csv already exists")
    else:
        key = read_census_key()
        header, rows = None, []
        for county, cname in COUNTIES.items():
            url = (f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5?get=NAME,{','.join(ACS_VARS)}"
                   f"&for=block%20group:*&in=state:{STATE}&in=county:{county}&in=tract:*&key={key}")
            log(f"[get ] ACS {ACS_YEAR} block groups for {cname} County ...")
            body = fetch(url)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                snippet = body[:300].decode("utf-8", "replace")
                sys.exit("ERROR: Census API did not return JSON (bad or missing key?). "
                         f"Response started with:\n{snippet}")
            header = header or data[0]
            rows += data[1:]
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["GEOID"] + header)
            for r in rows:
                rec = dict(zip(header, r))
                geoid = rec["state"] + rec["county"] + rec["tract"] + rec["block group"]
                w.writerow([geoid] + r)
    # validate
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    missing = [v for v in ACS_VARS if v not in rows[0]]
    if missing:
        raise ValueError(f"ACS file missing columns {missing}")
    if len(rows) < 480:
        raise ValueError(f"ACS file has only {len(rows)} block groups; expected ~506 (TIGER count)")
    by_county = {c: sum(1 for r in rows if r["county"] == c) for c in COUNTIES}
    info = {"rows": len(rows), "by_county": by_county, "vintage": f"ACS {ACS_YEAR} 5-year"}
    record(manifest, "acs_bg", f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5", path,
           variables=ACS_VARS, validation=info)
    log(f"[ ok ] acs_bg: {info}")


# ACS margins of error (90%) for the same variables -> data/raw/acs_bg_moe.csv.
# Kept in a SEPARATE file: estimates + margins together exceed the Census API's
# 50-variables-per-call limit, and acs_bg.csv stays byte-for-byte what it was.
# Used by engine/equity.py for the /audit equity confidence intervals (M3).
ACS_MOE_VARS = [v[:-1] + "M" for v in ACS_VARS]


def acs_moe_download(manifest: dict, force: bool) -> None:
    path = RAW / "acs_bg_moe.csv"
    if path.exists() and not force:
        log("[skip] acs_bg_moe.csv already exists")
    else:
        key = read_census_key()
        header, rows = None, []
        for county, cname in COUNTIES.items():
            url = (f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5?get={','.join(ACS_MOE_VARS)}"
                   f"&for=block%20group:*&in=state:{STATE}&in=county:{county}&in=tract:*&key={key}")
            log(f"[get ] ACS {ACS_YEAR} margins of error for {cname} County ...")
            body = fetch(url)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                sys.exit("ERROR: Census API did not return JSON for the MOE request (bad or missing key?).")
            header = header or data[0]
            rows += data[1:]
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["GEOID"] + header)
            for r in rows:
                rec = dict(zip(header, r))
                w.writerow([rec["state"] + rec["county"] + rec["tract"] + rec["block group"]] + r)
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    missing = [v for v in ACS_MOE_VARS if v not in rows[0]]
    if missing:
        raise ValueError(f"ACS MOE file missing columns {missing}")
    if len(rows) < 480:
        raise ValueError(f"ACS MOE file has only {len(rows)} block groups; expected ~506")
    info = {"rows": len(rows), "vintage": f"ACS {ACS_YEAR} 5-year (90% MOE)"}
    record(manifest, "acs_bg_moe", f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5", path,
           variables=ACS_MOE_VARS, validation=info)
    log(f"[ ok ] acs_bg_moe: {info}")

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="re-download everything")
    args = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    simple_downloads(manifest, args.force)
    acs_download(manifest, args.force)
    acs_moe_download(manifest, args.force)
    MANIFEST.write_text(json.dumps(manifest, indent=2))
    log(f"Done. Manifest written to {MANIFEST.relative_to(ROOT)}")

if __name__ == "__main__":
    main()
