# CareLeap API — production image (Railway, or any Docker host).
#
# Serves FastAPI in REAL mode on a frozen data snapshot committed in deploy/snapshot/
# (cube, origins, stops_walk, bg_towns parquets + the PVTA GTFS zip it was built from),
# so the deploy needs no Census key and no 5-minute cube build. Refresh the snapshot
# with `make deploy-snapshot` after `make data`.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first (cached layer): API + planner + pipeline libs (pandas/pyarrow).
COPY pyproject.toml README.md ./
COPY api/__init__.py api/__init__.py
COPY planner/__init__.py planner/__init__.py
# Install only the DEPENDENCIES; the code runs from /app (python -m uvicorn puts the
# working directory first on sys.path), so drop the half-copied package afterwards.
RUN pip install ".[pipeline]" && pip uninstall -y careleap

# Source + committed manual data + the snapshot.
COPY api ./api
COPY engine ./engine
COPY planner ./planner
COPY data/manual ./data/manual
COPY docs/provenance.jsonl docs/traceability.md ./docs/
COPY deploy/snapshot ./deploy/snapshot
RUN python -c "import zipfile; zipfile.ZipFile('deploy/snapshot/pvta_gtfs.zip').extractall('deploy/snapshot/pvta')" \
 && rm deploy/snapshot/pvta_gtfs.zip

# Real mode on the snapshot. CARELEAP_TODAY pins "today" inside the illustrative slot
# window the snapshot was built for. Set CARELEAP_WEB_ORIGINS to the web app's URL.
ENV CARELEAP_DATA=real \
    CARELEAP_CACHE_DIR=/app/deploy/snapshot \
    CARELEAP_TODAY=2026-10-26 \
    PORT=8000

EXPOSE 8000
# The port comes from $PORT inside api/__main__.py: no shell expansion needed.
CMD ["python", "-m", "api"]
