# methods.md — how each computed number is derived

Every number in CareLeap carries a source and a method. This file records the
estimation choices made in the data pipeline so reviewers can audit them.

## origins.parquet (pipeline/build_origins.py)

Sources:
- **ACS 2024 5-year** (U.S. Census API) — `data/raw/acs_bg.csv`
- **MassGIS Environmental Justice 2020** (ArcGIS REST) — `data/raw/ej_west.json`
- **TIGER 2024 block groups** (U.S. Census) — `data/raw/tiger_bg/`

Scope: Hampden (25013), Hampshire (25015), Franklin (25011) counties. 506 block groups.

### carless_adults — ESTIMATE
ACS `B25044` counts *households* with no vehicle, not adults. We estimate car-less
adults by scaling the adult population by the zero-vehicle household share:

```
adults_18plus   = B01003_001E (total pop) − under-18 bins (B01001 _003..006, _027..030)
zero_vehicle_hh = B25044_003E (owner, no vehicle) + B25044_010E (renter, no vehicle)
all_hh          = B25044_001E
carless_adults  = adults_18plus × (zero_vehicle_hh / all_hh)
```

This assumes car-less adults are distributed across households in proportion to the
zero-vehicle household rate. It is an approximation, labelled as such wherever shown.

### pop
`B01003_001E` (total population), rounded to int.

### age65_pct
Sum of 65+ age bins (`B01001` male _020..025, female _044..049) ÷ total population.
Range 0.0–1.0.

### lep_pct — limited-English-proficient household share
`C16002` limited-English-speaking household bins (_004 + _007 + _010 + _013) ÷ all
households (`C16002_001E`). Range 0.0–1.0.

> Note: the portal kit's EJ CSV has no GEOID, so it cannot be joined to block groups.
> Limited-English data therefore comes from ACS C16002, pulled directly from the Census.

### ej_flag
True if the block-group GEOID appears in the MassGIS EJ 2020 layer with `EJ = "Yes"`.
The layer lists EJ block groups only, so any GEOID absent from it is `False`.

### lat / lon — MVP substitute
TIGER interior point (`INTPTLAT` / `INTPTLON`), a point guaranteed to fall inside the
block-group polygon. This is an honest substitute for a true population-weighted
centroid, which would require areal interpolation against population rasters.

## stops_walk.parquet (pipeline/stops_walk.py)

Sources:
- **origins.parquet** (block-group points) — from build_origins.py
- **PVTA GTFS** `stops.txt` — `data/raw/pvta_gtfs.zip`

For each block-group origin, we find every PVTA stop within 800 m straight-line and
estimate the walk time:

```
distance_m = haversine(origin_lat, origin_lon, stop_lat, stop_lon)
keep if distance_m <= 800
walk_min   = distance_m × 1.3 (detour factor) / 80 (metres per minute, ~4.8 km/h)
```

Only real boarding stops are kept (GTFS `location_type` 0 or blank; stations and
entrances are skipped).

### Transit-desert note (a finding, not a bug)
193 of 506 block groups have **no** PVTA stop within 800 m. By county:
Hampden 249/336 served, Hampshire 59/108, Franklin **5/62**. Franklin County is almost
entirely unserved by fixed-route transit, which is the evidence behind the product's
rural "no option at all" layer.

The straight-line × 1.3 detour is an MVP substitute for a true OSM walk network.

## equity_ci — 90% confidence intervals (engine/equity.py, M3)

The equity shares in `/audit` rest on ACS 5-year estimates, which have sampling error.
`equity_ci` carries the published 90% margins of error (`data/raw/acs_bg_moe.csv`, the
`_M` twins of every `_E` variable above, fetched by `scripts/get_data.py`) through to a
90% interval on each group's reachable share.

Source: U.S. Census Bureau, *Understanding and Using American Community Survey Data:
What All Data Users Need to Know* (September 2020), ch. 8, "Calculating Measures of Error
for Derived Estimates" — https://www.census.gov/programs-surveys/acs/library/handbooks/general.html

```
sum / difference   MOE_A = sqrt(Σ MOE_i²)
proportion p=X/Y   MOE_p = sqrt(MOE_X² − p²·MOE_Y²) / Y      (ratio form with + if < 0)
product C=A·B      MOE_C = sqrt(A²·MOE_B² + B²·MOE_A²)
interval           [x − MOE, x + MOE], clipped to [0, 1]
```

Per block group: adults (difference), zero-vehicle share (proportion), car-less adults
(product), lep_pct and age65_pct (proportions). Group weights: zero_veh = C, ej = C × flag
(the flag is exact), lep = C × lep_pct, age65 = C × age65_pct (products). Group share
= Σ f·w / Σ w, where f (fraction of the clinic's hours a block group is reachable) is
exact from the cube; the proportion formula then gives the share's MOE.

Limits: errors are treated as independent across block groups and tables, as in the
handbook, so intervals are approximate. A share's MOE is capped at 1.0. ACS annotation
codes (negative MOE values) are treated as 0; none occur in the 2024 pull (506 block
groups). `share` and `n` in `equity_ci` equal `equity` exactly; `lo <= share <= hi`
always (property test `tests/property/test_equity_ci.py`).
