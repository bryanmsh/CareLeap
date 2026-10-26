# api/mocks/ — MOCK DATA (H1 scaffold)

Illustrative only. Nothing here is computed or sourced. While mocks are active the API
sends `X-Data-Mode: mock` on every response, and every mock source is named "MOCK ...".
Set `CARELEAP_DATA=real` to disable mocks; endpoints whose real data has not landed
return 503 instead of falling back.

| File | Stands in for | Replaced by |
|---|---|---|
| `audit.json` | `/audit` + `/whatif` (values = the example in `docs/contracts.md`) | M2 reachability cube |
| `provenance.json` | `/provenance` index (statuses `pending`) | M4 + M1: `docs/traceability.md`, `docs/provenance.jsonl` |
| `plan_request_maria.json` | A `POST /plan` body. **Synthetic** "Maria" (fictional composite from `final_plan/`). `origin_bg` uses tract `000000`, so it matches no real block group | stays as a demo request |
| `planner/visit_rules.yaml` | `planner/visit_rules.yaml` (colonoscopy only; see header comment) | M3 rulebook |
| `planner/pt1_fields.json` | `data/manual/pt1_fields.json` (placeholder field ids, not real PT-1 fields) | M3 |
| `planner/candidate_slots.json` | `data/manual/clinic_schedules.csv` (`mock-clinic-gi` is not a real clinic) | M3 |
| `planner/round_trips.json` | `engine.round_trip` (stops/routes `MOCK-*` are not PVTA) | M1 engine |

JSON files other than request bodies carry a `_mock_notice` key, which the loader strips.
