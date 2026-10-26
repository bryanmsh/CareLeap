# Kiro hooks — CareLeap

This repo uses two kinds of Kiro hook:

- **IDE file hooks** — `*.kiro.hook` JSON files in this directory. They fire in the
  **Kiro IDE** on editor events (a file saved, a spec task finishing). They do
  **not** fire in Kiro Web or Kiro Crew.
- **CLI agent hooks** — declared under the `"hooks"` key of a CLI agent config in
  `.kiro/agents/<agent>.json`. They fire when that agent runs under `kiro-cli`,
  keyed on agent lifecycle / tool-use events. The guardrail hooks below live on
  **`.kiro/agents/careleap-dev.json`**.

> **File hooks fire only on agent/IDE edits.** A change made outside the IDE
> (a merge, a teammate's push, a script run in CI) does **not** trigger a file
> hook. So every check a file hook performs is **also run in CI** — the hook is
> an early, local signal, never the only gate.

## Verified vs unverified triggers

Only two IDE trigger names are **confirmed** present in this repo (the existing
journal hooks use them): **`fileEdited`** and **`postTaskExecution`**. Any other
IDE trigger name is **UNVERIFIED** and is flagged in the table below and in the
hook file's own `description`. If the IDE build in use does not support an
unverified trigger, run that hook's script manually or rely on CI.

CLI agent triggers are documented by the Kiro CLI and are **verified**:
`agentSpawn | userPromptSubmit | preToolUse | postToolUse | stop`. A `preToolUse`
hook that exits `2` blocks the tool call and its stderr is returned to the model.
The hook receives a JSON event on stdin (`hook_event_name`, `cwd`, `tool_name`,
`tool_input`, `tool_response`). A matcher is a tool name, a group tag
(`read` / `write` / `shell` / `web`), or `@server` / `@server/tool`.

## All 11 planned hooks

| # | Hook | Trigger | Trigger verified? | Lives in | Owner | Action |
|---|------|---------|-------------------|----------|-------|--------|
| 1 | feed-expiry-on-session-start | `sessionStart` (IDE) + `agentSpawn` (CLI, on `careleap-dev`) | ⚠️ IDE trigger **UNVERIFIED**; CLI ✅ verified | IDE `.kiro.hook` + CLI agent | M1 | `scripts/hooks/check_data_fresh.py` — warn (never block) if the manifest is >7 days old or the PVTA feed ends within 14 days |
| 2 | remind-templates | `userPromptSubmit` | ✅ verified (CLI) | CLI agent `careleap-dev` | this task (W2) | `scripts/hooks/remind_templates.py` — remind: patient-facing text only from reviewed templates |
| 3 | guard-templates | `preToolUse` (matcher `write`) | ✅ verified (CLI) | CLI agent `careleap-dev` | this task (W2) | `scripts/hooks/guard_templates.py` — **exit 2** if a `planner/templates/**` write does not also move `planner/templates/signoff.json` |
| 4 | block-live-routing | `preToolUse` (matchers `shell`, `web`) | ✅ verified (CLI) | CLI agent `careleap-dev` | this task (W2) | `scripts/hooks/block_live_routing.py` — **exit 2** on `maps.googleapis.com`, OSRM, or Mapbox Directions; message `use gtfs-mcp` |
| 5 | log-provenance | `postToolUse` (matcher `@gtfs-mcp`) | ✅ verified (CLI) | CLI agent `careleap-dev` | this task (W2) | `scripts/hooks/log_provenance.py` — append one JSON line `{ts, tool, input, sources?, session}` to `docs/provenance-log.jsonl` |
| 6 | engine-fast-tests-on-save | `fileEdited` (matcher `engine/**`) | ✅ verified | IDE `.kiro.hook` | M1 | `pytest tests/property tests/golden tests/differential -q -x -m "not slow"` — fast router suite on every engine save; CI repeats it (`make test`) |
| 7 | a11y-on-web-save | `fileEdited` (matcher `web/**`) | ✅ verified | IDE `.kiro.hook` | this task (W2) | `cd web && npm run a11y` |
| 8 | validate-gtfs-on-create | `fileCreated` | ⚠️ **UNVERIFIED** | IDE `.kiro.hook` | this task (W2) | `scripts/hooks/validate_gtfs.py <path>` — structural GTFS check |
| 9 | data-freshness-pre-task | `preTaskExecution` | ⚠️ **UNVERIFIED** | IDE `.kiro.hook` | this task (W2) | `scripts/hooks/check_data_fresh.py` — warn only, exit 0 always |
| 10 | traceability-post-task | `postTaskExecution` | ✅ verified | IDE `.kiro.hook` | this task (W2) | `scripts/hooks/update_traceability.py` — regenerate `docs/traceability-matrix.md` |
| 11 | (journal hooks, existing) | `fileEdited` + `postTaskExecution` | ✅ verified | IDE `.kiro.hook` × 2 | existing | `journal-on-spec-steering-save` + `journal-on-task-finish` → `scripts/log_kiro.py` |

Notes:

- **#1 / #6** were reassigned from Prince (M2) to M1 and created on 2026-10-24.
- **#11** refers to the two pre-existing journal hooks
  (`journal-on-spec-steering-save.kiro.hook`, `journal-on-task-finish.kiro.hook`),
  which are the reference `.kiro.hook` JSON shape the new IDE hooks copy.
- The CLI guardrail hooks (#2–#5) only fire for an agent whose config declares
  them. They are on `careleap-dev`; add the same `"hooks"` block to another
  CLI agent config to carry the guardrails there too.

## Hook JSON shapes

### IDE `.kiro.hook`

```json
{
  "name": "a11y-on-web-save",
  "description": "…",
  "trigger": "fileEdited",
  "matcher": "web/**",
  "action": "cd web && npm run a11y",
  "timeout": 180,
  "enabled": true
}
```

### CLI agent `"hooks"` (in `.kiro/agents/<agent>.json`)

```json
"hooks": {
  "userPromptSubmit": [ { "command": "python scripts/hooks/remind_templates.py" } ],
  "preToolUse": [
    { "matcher": "write", "command": "python scripts/hooks/guard_templates.py" },
    { "matcher": "shell", "command": "python scripts/hooks/block_live_routing.py" },
    { "matcher": "web",   "command": "python scripts/hooks/block_live_routing.py" }
  ],
  "postToolUse": [ { "matcher": "@gtfs-mcp", "command": "python scripts/hooks/log_provenance.py" } ]
}
```

Validate a CLI agent config (including its `hooks`) with:

```
kiro-cli agent validate --path .kiro/agents/careleap-dev.json
```

## The hook scripts

All under `scripts/hooks/` (unit-tested in `tests/unit/test_hook_scripts.py`):

| Script | Reads | Exit convention |
|--------|-------|-----------------|
| `remind_templates.py` | — (stdin drained) | prints reminder; exit 0 |
| `guard_templates.py` | preToolUse JSON on stdin + `git status` | **exit 2** to block; 0 to allow; fail-open on bad JSON |
| `block_live_routing.py` | preToolUse JSON on stdin | **exit 2** to block; 0 to allow |
| `log_provenance.py` | postToolUse JSON on stdin (`PROVENANCE_LOG` overrides path) | exit 0; appends one JSONL line |
| `validate_gtfs.py` | a feed path (`.zip` or dir) as `argv[1]` | 0 valid, 1 invalid |
| `check_data_fresh.py` | `data/raw/manifest.json` (`DATA_ROOT` overrides root) | **always exit 0**; warns on stderr |
| `update_traceability.py` | `.kiro/specs/*/requirements.md` + tests (`TRACE_ROOT` overrides root) | 0; writes `docs/traceability-matrix.md` |
