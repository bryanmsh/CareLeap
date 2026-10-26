# api/

FastAPI app. Routers: `audit`, `whatif`, `plan`, `provenance`.

All endpoints are tested against the shapes in `docs/contracts.md` (Playwright/pytest)
until the UI exists. M4 owns the contract tests.

Owner: M4.

## Run locally (Windows PowerShell, from the repo root)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"      # or: make install

python -m uvicorn api.main:app --reload --port 8000   # or: make api
python -m pytest tests/contract                       # or: make test-contract
python -m pytest tests/unit tests/property            # or: make test-planner
```

- Docs: http://127.0.0.1:8000/docs
- Demo request (synthetic Maria): `api/mocks/plan_request_maria.json`
- Data mode: `CARELEAP_DATA=mock` (default) serves the labelled mocks in `api/mocks/`.
  `real` uses real data only and returns 503 for anything not landed yet.
- No authentication or CORS yet: run on localhost only.
