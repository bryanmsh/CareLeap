# careleap — Kiro power

**Reachable Care.** Audit which clinic hours car-less patients can actually reach
**and return from** by transit (round trip), and debug GTFS routing — against a
cached GTFS feed, never a live third-party routing API. Wraps the CareLeap
routing engine via two bundled MCP servers, `gtfs-mcp` and `reach-mcp`.

> Logistics only. Every number carries its source and vintage. Reachability is not
> attendance. Synthetic patients only.

## What's in the bundle

```
careleap/
├── plugin.json                       # power manifest (name, mcp entry, skills, tags)
├── mcp.json                          # launches gtfs-mcp + reach-mcp via ${CARELEAP_HOME}
├── README.md                         # this file
└── skills/
    ├── clinic-access-audit.md        # audit a weekly schedule for car-less access
    └── gtfs-debugging.md             # diagnose an unreachable round trip
```

The MCP **server code** itself lives in the CareLeap engine checkout
(`mcp/gtfs-mcp/server.py`, `mcp/reach-mcp/server.py` and the `engine/` package); the
power references it by the `CARELEAP_HOME` env var so the same bundle works from
any workspace.

## Install (from a fresh workspace)

1. **Check out the CareLeap engine repo** somewhere on disk and build its venv
   (the repo ships `pyproject.toml`; the `mcp` package and `engine` must import):

   ```bash
   # in the engine repo checkout:
   python3 -m venv .venv
   .venv/bin/pip install -e .          # installs engine + the mcp package
   ```

2. **Copy this power bundle into your workspace** and register its MCP config. Kiro
   discovers MCP servers from `<workspace>/.kiro/settings/mcp.json`:

   ```bash
   cp -R /path/to/careleap  <workspace>/careleap
   mkdir -p <workspace>/.kiro/settings
   cp <workspace>/careleap/mcp.json  <workspace>/.kiro/settings/mcp.json
   ```

   (Or `kiro-cli mcp import` the file — see the test section. Skills are loaded by
   pointing your agent at `careleap/skills/*.md`.)

3. **Set the environment** (see below), then start Kiro in that workspace. Both
   servers appear under the `default` MCP scope.

## Required / optional environment

`mcp.json` references these **by name** (`${VAR}`) — never a literal value, never a
secret. None of these are secrets; there is nothing to redact.

| Var                 | Required | Purpose |
|---------------------|----------|---------|
| `CARELEAP_HOME` | **Yes**  | Absolute path to the CareLeap engine checkout. Used for both the python interpreter (`${CARELEAP_HOME}/.venv/bin/python`) and the server scripts (`${CARELEAP_HOME}/mcp/*/server.py`). This is what makes the power portable across workspaces. |
| `GTFS_DIR`          | No       | Absolute path to a real GTFS directory (e.g. `${CARELEAP_HOME}/data/cache/pvta`). When set, `gtfs-mcp` loads that feed. When **unset**, it falls back to a small **synthetic** feed and labels every result `synthetic GTFS (illustrative — not a finding)`. |
| `GTFS_DATE`         | No       | ISO `YYYY-MM-DD` service date to resolve the feed to (default `2026-11-12`). |

`reach-mcp` additionally needs the prebuilt reachability cube at
`${CARELEAP_HOME}/data/cache/cube.parquet` (+ `origins.parquet`). If it is
missing, `reachability`/`what_if` return a clear `{"error": "...cube cache not
found..."}` payload rather than crashing — build it with the engine's
`pipeline/build_cube.py` (slow: ~9 min/clinic).

## Tools provided

**`gtfs-mcp`** — per-trip router over the cached feed:

| Tool | Params | Returns |
|------|--------|---------|
| `round_trip` | `origin, clinic, date, start, minutes` | `{reachable, out_legs, ret_legs, last_bus_home, reason, sources}` |
| `plan_trip` | `origin, dest, date, depart_after?, arrive_by?` | `{reachable, legs, reason, sources}` |
| `validate_feed` | — | `{ok, service_date, n_stops, n_trips, crosses_midnight, ...}` |
| `service_changes` | `since` | `{since, service_date, changes, note, sources}` |

> **Name note:** the tool is registered as `round_trip` (contracts.md §2) via
> `@server.tool(name="round_trip")`.

**`reach-mcp`** — aggregation path over the cached reachability cube:

| Tool | Params | Returns |
|------|--------|---------|
| `reachability` | `clinic, community, day` | `{cells, equity, sources, server}` (same shape as `GET /audit`) |
| `what_if` | `clinic, block, to, community="all"` | same shape as `reachability`, after moving a block (`block="mon-08", to=10`) |
| `suggest_schedule` | `clinic, k=3, day="mon"` | up to `k` ranked `{change, gain_visit_hours, gain_people, sources}` |

`start`/`minutes`/`to` are integers; `start` is **seconds since local midnight and
may exceed 86400** (a 24:30 departure is `88200`, never wrapped).

## Skills provided

- **`skills/clinic-access-audit.md`** — audit a clinic's weekly schedule for car-less
  reach-and-return access, produce a CHNA-ready, source-cited report, and test fixes
  with `what_if` / `suggest_schedule`.
- **`skills/gtfs-debugging.md`** — diagnose why a round trip is unreachable, with a
  checklist of the classic GTFS traps (>24:00 times, calendar exceptions, transfer
  minimums, trip limits, missing access links).

## The test I ran (fresh-workspace, real output)

I created an empty workspace, copied this bundle in exactly as the Install steps
above describe, set `CARELEAP_HOME` to the engine checkout, then launched each
server over stdio using **this power's `mcp.json` command/args** and performed a real
MCP `initialize` + `tools/list` (and `tools/call`). The clients are tiny stdio MCP
clients using the installed `mcp` package.

### 1. `initialize` + `tools/list` (PVTA feed: `GTFS_DIR` set) — **PASS**

Both servers started and listed their tools (exit 0):

```
gtfs-mcp (v0.1.0): round_trip, plan_trip, service_changes, validate_feed
reach-mcp (v0.1.0): reachability, what_if, suggest_schedule
```

Resolved launch command (from `${CARELEAP_HOME}`):

```
<engine>/.venv/bin/python  <engine>/mcp/gtfs-mcp/server.py
<engine>/.venv/bin/python  <engine>/mcp/reach-mcp/server.py
```

### 2. `tools/call` (synthetic fallback: `GTFS_DIR` unset) — **PASS**

Proves the tools actually execute, not just list:

```json
{
  "validate_feed": { "ok": true, "service_date": "2026-11-12",
                     "n_stops": 4, "n_trips": 58,
                     "sources": [{"name": "synthetic GTFS (illustrative — not a finding)",
                                  "synthetic": true, "vintage": "2026-11-12"}] },
  "round_trip(S0->S3, 08:00, 45min)": {
     "reachable": true,
     "reason": "arrive 06:30:00 ok (<= 07:50:00); return after visit ends 08:45:00; last useful bus 09:00:00",
     "last_bus_home_hms": "09:00:00", "n_out_legs": 2, "n_ret_legs": 2,
     "sources": [{"name": "synthetic GTFS (illustrative — not a finding)", "synthetic": true}] }
}
```

The synthetic feed correctly self-labels `illustrative — not a finding`, satisfying
the "every number carries source + vintage" guardrail.

### 3. kiro-cli non-interactive load — **PASS**

`kiro-cli 2.34.0` discovered the config from the fresh workspace's
`.kiro/settings/mcp.json`:

```
$ kiro-cli mcp list
🤖 default:
  kiro_default
    • gtfs-mcp     ${CARELEAP_HOME}/.venv/bin/python
    • reach-mcp    ${CARELEAP_HOME}/.venv/bin/python

$ kiro-cli mcp status --name gtfs-mcp
Scope   : 🤖 default
Command : ${CARELEAP_HOME}/.venv/bin/python
Env Vars: GTFS_DATE=${GTFS_DATE}, GTFS_DIR=${GTFS_DIR}
Disabled: false
```

A full `kiro-cli chat` tool invocation needs interactive auth, so the
non-interactive check stops at `list`/`status`, both of which resolve this power's
servers correctly.

### Reproduce

```bash
export CARELEAP_HOME=/path/to/engine-checkout
export GTFS_DIR="$CARELEAP_HOME/data/cache/pvta" GTFS_DATE=2026-11-12   # optional
"$CARELEAP_HOME/.venv/bin/python" mcp_test_client.py .kiro/settings/mcp.json  # tools/list
unset GTFS_DIR GTFS_DATE
"$CARELEAP_HOME/.venv/bin/python" mcp_call_test.py  .kiro/settings/mcp.json   # tools/call
```

(The two test clients live under the scratch power-test dir used for this run.)

## Published

Public repo: [SSJ-07/slot-to-stop-power](https://github.com/SSJ-07/slot-to-stop-power) (published under the old name; rename it to `careleap-power` on GitHub and the old URL redirects)
(release `v0.1.0`). It contains only this bundle — `plugin.json`, `mcp.json`,
`README.md`, `skills/*.md`. No `.venv`, GTFS cache, or `.env`; `mcp.json` references
env vars by name only.

**Engine dependency:** tool shapes verified against CareLeap engine commit
`f7fc0c2` (2026-10-24). Re-verified in a fresh workspace on 2026-10-24: both servers
`initialize` + `tools/list`, `validate_feed` on PVTA returns `ok: true`, and
`reachability(BAY_GI_SPRINGFIELD, thu)` returns hourly cells from the cube.

Owner: M1.
