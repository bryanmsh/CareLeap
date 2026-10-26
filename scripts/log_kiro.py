"""Append one entry to a per-person Kiro-usage journal (docs/kiro-journal/<member>.md).

Each teammate gets their OWN file so appends never collide on merge. Assemble the
whole team's log (sorted by timestamp, groupable by topic) on demand.

Used four ways:
  1. Directly, for Crew / CLI / Web work:
       python scripts/log_kiro.py --member sumedh --tool Crew --topic mcp \
         --what "wired gtfs-mcp round_trip to the engine" --outcome "verified, 252 tests green"
  2. By the Kiro IDE hooks in .kiro/hooks/ (they pass the fields the event gives them).
  3. With --stdin, reading a ready-made markdown entry on stdin (what an agent hook does).
  4. --assemble: concatenate every per-person file into one timestamp-sorted document
     on stdout (the raw material for the "How Kiro was used" write-up).

A member's file is created from a template on first write. Stdlib only; append-only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOURNAL_DIR = ROOT / "docs" / "kiro-journal"
MARKER = "<!-- LOG ENTRIES BELOW — newest at the bottom -->"

TOPICS = {"spec", "pbt", "steering", "mcp", "hooks", "power", "other"}
TOOLS = {"IDE", "CLI", "Web", "Crew"}


def _slug(member: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", member.strip().lower()).strip("-") or "unknown"


def _member_file(member: str) -> Path:
    return JOURNAL_DIR / f"{_slug(member)}.md"


def _ensure_file(member: str) -> Path:
    path = _member_file(member)
    if not path.exists():
        JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"# Kiro Journal — {member}\n\n"
            "Per-person Kiro-usage log for CareLeap. Append only, newest at the bottom.\n"
            f"Write entries with: `python scripts/log_kiro.py --member {_slug(member)} "
            "--tool <IDE|CLI|Web|Crew> --topic <t> --what \"...\" [--kiro \"...\"] [--outcome \"...\"]`\n"
            "Assemble the whole team's log with: `python scripts/log_kiro.py --assemble`\n\n"
            f"{MARKER}\n",
            encoding="utf-8",
        )
    return path


def format_entry(member: str, tool: str, topic: str, what: str, kiro: str, outcome: str) -> str:
    ts = dt.datetime.now().isoformat(timespec="minutes").replace("T", " ")
    lines = [f"\n## {ts} · {member} · {tool} · topic: {topic}", f"what: {what}"]
    if kiro:
        lines.append(f"kiro: {kiro}")
    if outcome:
        lines.append(f"outcome: {outcome}")
    return "\n".join(lines) + "\n"


def append(member: str, entry: str) -> Path:
    path = _ensure_file(member)
    with path.open("a", encoding="utf-8") as f:
        f.write(entry)
    return path


def assemble() -> str:
    """Concatenate every per-person file's entries, sorted by the leading timestamp."""
    entries: list[tuple[str, str]] = []
    for path in sorted(JOURNAL_DIR.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        text = path.read_text(encoding="utf-8")
        body = text.split(MARKER, 1)[1] if MARKER in text else text
        for block in re.split(r"(?=^## )", body, flags=re.MULTILINE):
            block = block.strip()
            if not block.startswith("## "):
                continue
            m = re.match(r"## (\d{4}-\d{2}-\d{2} \d{2}:\d{2})", block)
            entries.append((m.group(1) if m else "", block))
    entries.sort(key=lambda e: e[0])
    out = ["# Kiro Journal — assembled (all members, by time)\n"]
    out += [b for _, b in entries]
    return "\n\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--member", default="unknown", help="who did the work, e.g. sumedh")
    ap.add_argument("--tool", default="Crew", help="IDE | CLI | Web | Crew")
    ap.add_argument("--topic", default="other", help="spec | pbt | steering | mcp | hooks | power | other")
    ap.add_argument("--what", default="", help="one line: what happened")
    ap.add_argument("--kiro", default="", help="what Kiro did")
    ap.add_argument("--outcome", default="", help="result, commit sha if any")
    ap.add_argument("--stdin", action="store_true", help="read a full markdown entry from stdin instead")
    ap.add_argument("--assemble", action="store_true", help="print the whole team's log, time-sorted, to stdout")
    args = ap.parse_args()

    if args.assemble:
        sys.stdout.write(assemble())
        return

    if args.stdin:
        entry = sys.stdin.read().strip()
        if not entry:
            return  # nothing notable; stay quiet (lets Stop/Save hooks no-op cleanly)
        path = append(args.member, "\n" + entry + "\n")
        print(f"[ok] logged to {path.relative_to(ROOT)}")
        return

    if not args.what.strip():
        sys.exit("ERROR: --what is required (one line describing what happened).")
    if args.tool not in TOOLS:
        print(f"[warn] unusual --tool '{args.tool}' (expected one of {sorted(TOOLS)})", file=sys.stderr)
    if args.topic not in TOPICS:
        print(f"[warn] unusual --topic '{args.topic}' (expected one of {sorted(TOPICS)})", file=sys.stderr)

    path = append(args.member, format_entry(args.member, args.tool, args.topic, args.what, args.kiro, args.outcome))
    print(f"[ok] logged to {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
