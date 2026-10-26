"""`python -m api` — production entry point (Railway / Docker).

Reads the port from $PORT in Python, so the start command needs no shell expansion:
Railway runs custom start commands without a shell, and a literal "${PORT}" reaches
uvicorn as the port. Local dev keeps using `make api` (uvicorn --reload).
"""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    port = int(os.environ.get("PORT") or 8000)
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, proxy_headers=True, forwarded_allow_ips="*")


if __name__ == "__main__":
    main()
