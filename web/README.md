# web/

React + Vite + TypeScript frontend for CareLeap.

- **MapLibre GL** block-group map; **D3 (`d3-scale`) only for scales**, React renders the DOM
- CSS design tokens (`src/styles/tokens.css`), light + dark; WCAG 2.2 AA; large-type ready
- **react-i18next** (EN + ES) for UI chrome labels only — patient-facing copy is out of scope here
- Routes (hash-based, no router dependency): `/audit`, `/planner` (placeholder, owned by M4), `/about`

Owner: M4 (lead), M3 (content/equity).
Governed by steering `accessibility.md` and `ui-style.md` (fileMatch `web/**`), and `equity-and-language.md`.

## Stack (versions pinned exactly in `package.json`)

React 19 · Vite 8 · TypeScript 5.9 (strict) · MapLibre GL 6 · d3-scale 4 · react-i18next 17.
Tests: Vitest + Testing Library + fast-check. Playwright + axe-core scripts are wired in
`package.json` (`e2e`, `a11y`) for when the e2e specs land.

## Run

```bash
npm install
npm run dev        # vite dev server, 127.0.0.1:5173, proxies /api -> FastAPI
npm run build      # tsc -b (typecheck) + vite build
npm run test       # vitest unit/property tests
```

The dev server binds to `127.0.0.1` only and proxies `/api` to the FastAPI backend
(`VITE_API_TARGET`, default `http://127.0.0.1:8000`).

## API client

`src/api/client.ts` is the typed client; all UI data comes through it (never a live
third-party routing/geocoding API from the browser). Base URL from `VITE_API_BASE`
(default `http://127.0.0.1:8000`; set to `/api` to use the dev proxy).

- `getAudit({ clinic, community, day })` → `GET /audit`
- `postWhatIf({ clinic, shift: { block, to } })` → `POST /whatif` (same shape as `/audit`)
- `getClinics()` → `GET /clinics`
- `getBlockGroups({ clinic, day, hour?, community? })` → `GET /audit/blockgroups`

Contract types in `src/api/types.ts` mirror `docs/contracts.md §3` and are compile-time
checked against the generated OpenAPI schema (`src/api/schema.d.ts`). Regenerate the
schema with `npm run gen:api` when the API changes.

## Map data (optional, local only)

The block-group map reads an optional static `public/data/origins.geojson`. If it is
missing the map shows an accessible "map data not loaded" notice instead of crashing.
Generate it from the (gitignored) parquet cache with the repo venv python:

```bash
../.venv/bin/python scripts/export_origins.py
```

`public/data/` is gitignored (the source parquet is local-only and absent in CI).

## Accessibility notes

Full keyboard operation; every drag has a keyboard equivalent (week grid: arrow keys move,
Enter picks up / drops, Esc cancels); visible focus via `--focus-ring`; every grid cell and
map class pairs colour with a number/label (never colour-only); `prefers-reduced-motion`
respected; charts and the map have a table/text alternative; what-if updates announce via
`aria-live`. Every on-screen number carries a source (sources footer + provenance chip).
