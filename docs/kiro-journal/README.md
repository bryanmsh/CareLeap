# docs/kiro-journal/ — per-person Kiro-usage log

The team's running record of **how Kiro was used** on CareLeap (formerly Slot-to-Stop). It is the raw
material for the required "How Kiro was used" write-up (judges read this).

## One file per person — no merge conflicts
Each teammate appends only to their own file, so two people logging at once never collide:

```
docs/kiro-journal/
├── README.md        (this file)
├── sumedh.md        (M1 — engine/router, .kiro, CI, power)
├── m2-prince.md     (M2 — data + audit engine + optimizer)
├── m3-bryan.md      (M3 — research + content + templates)
└── m4-kevin.md      (M4 — visit planner + API + UI)
```

## How entries land
1. **Kiro IDE hooks** (`.kiro/hooks/`) — fire automatically on file save / task finish (IDE + CLI only).
2. **`scripts/log_kiro.py`** — for Crew / CLI / Web work, where hooks don't fire:
   ```
   python scripts/log_kiro.py --member sumedh --tool Crew --topic mcp \
     --what "one line" [--kiro "what Kiro did"] [--outcome "result + sha"]
   ```
   The file is created from a template on first write.
3. **By hand** — paste an entry in the format below at the bottom of your own file.

## Assemble the whole log
```
python scripts/log_kiro.py --assemble > docs/kiro-journal-assembled.md
```
Concatenates every person's entries, sorted by timestamp. Group by the `topic`
field to map onto the seven write-up sections.

## Entry format
```
## <date time> · <member> · <tool> · topic: <spec|pbt|steering|mcp|hooks|power|other>
what: <one line — what happened>
kiro: <what Kiro did>
outcome: <result, commit sha if any>
```
Append only, never rewrite — git history shows who wrote what and when.
