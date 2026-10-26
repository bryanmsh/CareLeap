"""Where the built caches live.

Default: data/cache/ under the repo root. `CARELEAP_CACHE_DIR` points the API and
engine at another directory — `make demo` uses it to serve the frozen snapshot in
data/snapshots/demo-v1/ without copying anything back into data/cache/.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def cache_dir() -> Path:
    override = os.environ.get("CARELEAP_CACHE_DIR", "").strip()
    if override:
        p = Path(override).expanduser()
        return p if p.is_absolute() else ROOT / p
    return ROOT / "data" / "cache"
