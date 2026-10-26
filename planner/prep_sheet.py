"""Prep sheet text from the human-reviewed template only (45 CFR 92.201(c)(3)).

planner/templates/<lang>/prep_sheet.md is used ONLY when planner/templates/signoff.json
marks it reviewed=true with a named reviewer (same rule as plan_b). Never machine-
translated at runtime, never falls back to another language. Tokens the planner has data
for are filled; every other token becomes a blank line for the navigator to complete, so
no planner-written words reach the patient.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path

from planner.plan_b import SIGNOFF, TEMPLATES, _reviewed

_TOKEN = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
BLANK = "______"


def template_status(lang: str, signoff_path: Path = SIGNOFF) -> str:
    """'reviewed' when the prep sheet for `lang` is signed off, else 'pending_review'."""
    if lang not in ("en", "es") or not signoff_path.is_file():
        return "pending_review"
    signoff = json.loads(signoff_path.read_text(encoding="utf-8"))
    rel = f"planner/templates/{lang}/prep_sheet.md"
    return "reviewed" if _reviewed(signoff, rel) else "pending_review"


def render_prep_sheet(
    lang: str,
    values: Mapping[str, str],
    templates_dir: Path = TEMPLATES,
    signoff_path: Path = SIGNOFF,
) -> str | None:
    """The filled prep sheet (markdown) for `lang`, or None if it is not signed off."""
    if template_status(lang, signoff_path) != "reviewed":
        return None
    path = templates_dir / lang / "prep_sheet.md"
    if not path.is_file():
        return None
    body = _COMMENT.sub("", path.read_text(encoding="utf-8")).strip()
    return _TOKEN.sub(lambda m: str(values.get(m.group(1)) or BLANK), body)
