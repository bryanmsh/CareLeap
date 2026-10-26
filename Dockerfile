# CareLeap — production image (Railway, or any Docker host). ONE service: FastAPI serves
# the API AND the built React app from the same origin (no CORS, one URL).
#
# Serves FastAPI in REAL mode on a frozen data snapshot committed in deploy/snapshot/
# (cube, origins, stops_walk, bg_towns parquets + the PVTA GTFS zip it was built from),
# so the deploy needs no Census key and no 5-minute cube build. Refresh the snapshot
# with `make deploy-snapshot` after `make data`.

# --- Stage 1: build the web app --------------------------------------------------------
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web ./
# Same-origin API: the client joins "/" + "/audit" -> "/audit".
ENV VITE_API_BASE=/
RUN npm run build

# --- Stage 2: the API ------------------------------------------------------------------
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
COPY --from=web /web/dist ./web/dist
RUN python -c "import zipfile; zipfile.ZipFile('deploy/snapshot/pvta_gtfs.zip').extractall('deploy/snapshot/pvta')" \
 && rm deploy/snapshot/pvta_gtfs.zip

# Real mode on the snapshot. CARELEAP_TODAY pins "today" inside the illustrative slot
# window the snapshot was built for. CARELEAP_WEB_DIST makes the API serve the web app.
ENV CARELEAP_DATA=real \
    CARELEAP_CACHE_DIR=/app/deploy/snapshot \
    CARELEAP_TODAY=2026-10-26 \
    CARELEAP_WEB_DIST=/app/web/dist \
    PORT=8000

EXPOSE 8000
# The port comes from $PORT inside api/__main__.py: no shell expansion needed.
CMD ["python", "-m", "api"]
