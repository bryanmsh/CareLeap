# CareLeap — daily-driver commands (plan.md §7).
#   make data       download raw sources + build every cache, incl. one cube per clinic
#   make test       fast suite (unit + property fast profile + golden + contract)
#   make test-full  everything, incl. slow differential / full Hypothesis profiles
#   make snapshot   freeze data/cache into data/snapshots/demo-v1/
#   make demo       run the API (real mode) on that frozen snapshot
# Activate the virtualenv first, or pass PYTHON=.venv/bin/python.
PYTHON ?= python
SNAPSHOT ?= data/snapshots/demo-v1
CUBE_DATE ?= 2026-11-12
# Frozen "today" for the frozen snapshot: the demo slots in clinic_schedules.csv cover
# 2026-10-10..11-10, so the planner's [today, today+14d] window must sit inside that.
DEMO_TODAY ?= 2026-10-26
# Clinic ids come from the manual clinic table, so a new clinic row is picked up
# automatically by `make data` — nobody has to hand-list clinics here.
CLINICS := $(shell tail -n +2 data/manual/clinic_stops.csv | cut -d, -f1)
CUBE_PARTS := $(CLINICS:%=data/cache/cubes/%.parquet)

.PHONY: install api web dev test test-full test-contract test-planner \
        data raw pvta origins stops-walk towns cubes snapshot demo deploy-snapshot clean-cache

install:
	$(PYTHON) -m pip install -e ".[dev,pipeline]"

# ---------------------------------------------------------------- run
api:
	$(PYTHON) -m uvicorn api.main:app --reload --port 8000

web:
	cd web && npm run dev

dev:
	$(MAKE) -j2 api web

# ---------------------------------------------------------------- tests
test:
	$(PYTHON) -m pytest -q -m "not slow"

test-full:
	$(PYTHON) -m pytest -q

test-contract:
	$(PYTHON) -m pytest tests/contract

test-planner:
	$(PYTHON) -m pytest tests/unit tests/property

# ---------------------------------------------------------------- data
# Each step is idempotent: get_data.py skips files it already has, and a cube
# part is only rebuilt when its clinic row or the origins change.
data: raw pvta origins stops-walk towns cubes

raw:
	$(PYTHON) scripts/get_data.py

# The engine, the golden tests and gtfs-mcp read the EXTRACTED PVTA feed.
pvta: data/cache/pvta/stops.txt
data/cache/pvta/stops.txt: data/raw/pvta_gtfs.zip
	mkdir -p data/cache/pvta
	$(PYTHON) -c "import zipfile; zipfile.ZipFile('data/raw/pvta_gtfs.zip').extractall('data/cache/pvta')"
data/raw/pvta_gtfs.zip:
	$(PYTHON) scripts/get_data.py

origins: data/cache/origins.parquet
data/cache/origins.parquet: scripts/get_data.py pipeline/build_origins.py
	$(PYTHON) pipeline/build_origins.py

stops-walk: data/cache/stops_walk.parquet
data/cache/stops_walk.parquet: data/cache/origins.parquet pipeline/stops_walk.py
	$(PYTHON) pipeline/stops_walk.py

towns: data/cache/bg_towns.parquet
data/cache/bg_towns.parquet: data/cache/origins.parquet pipeline/build_towns.py
	$(PYTHON) pipeline/build_towns.py

# One parquet per clinic (built in parallel inside build_cube.py), then merged.
cubes: $(CUBE_PARTS)
	$(PYTHON) pipeline/merge_cubes.py

data/cache/cubes/%.parquet: data/cache/pvta/stops.txt data/cache/origins.parquet data/cache/stops_walk.parquet data/manual/clinic_stops.csv
	$(PYTHON) pipeline/build_cube.py --date $(CUBE_DATE) --clinic $* --out $@

# ---------------------------------------------------------------- demo
snapshot:
	rm -rf $(SNAPSHOT)
	mkdir -p $(SNAPSHOT)
	cp data/cache/*.parquet $(SNAPSHOT)/
	cp -R data/cache/pvta $(SNAPSHOT)/pvta
	cp -R data/cache/cubes $(SNAPSHOT)/cubes
	cp data/raw/manifest.json $(SNAPSHOT)/manifest.json
	@echo "frozen -> $(SNAPSHOT) ($$(du -sh $(SNAPSHOT) | cut -f1))"

demo:
	@test -f $(SNAPSHOT)/cube.parquet || { echo "no snapshot at $(SNAPSHOT): run 'make snapshot' (or 'make data' first)"; exit 1; }
	CARELEAP_DATA=real CARELEAP_CACHE_DIR=$(SNAPSHOT) CARELEAP_TODAY=$(DEMO_TODAY) \
	  $(PYTHON) -m uvicorn api.main:app --port 8000

# Refresh the small COMMITTED snapshot the Docker/Railway image serves (deploy/snapshot/).
deploy-snapshot:
	mkdir -p deploy/snapshot
	cp data/cache/cube.parquet data/cache/origins.parquet data/cache/stops_walk.parquet \
	   data/cache/bg_towns.parquet deploy/snapshot/
	cp data/raw/manifest.json data/raw/pvta_gtfs.zip deploy/snapshot/
	@du -sh deploy/snapshot

clean-cache:
	rm -rf data/cache/cubes data/cache/*.parquet
