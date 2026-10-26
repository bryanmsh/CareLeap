# Kiro Crew jobs (feed watch)

`careleap_feed.py` is a no-LLM Kiro Crew script cron. Install it by copying it to
`~/.kiro/crew/crons/` and registering two jobs (done on M1's machine, 2026-10-24):

| Job | Schedule | Function | What it does |
|---|---|---|---|
| PVTA feed heartbeat | every 6 h | `heartbeat` | HEADs the PVTA GTFS zip; on an ETag / Last-Modified / size change, posts the diff + re-audit steps to Slack |
| Feed expiry alarm | daily 09:00 America/New_York | `expiry` | reads `data/cache/pvta/feed_info.txt`; alerts when the feed ends within 14 days |

Verified with `kirocrew cron preview`: both skipped (first heartbeat stored the baseline
ETag `"889a736e47dd1:0"`, Last-Modified 18 Sep 2026; feed ends 2026-12-19, 56 days out).

It does not rebuild the cube itself: that takes ~9 min per clinic, past a script timeout.
Slack delivery falls back to a dashboard notification until Slack is connected in Kiro Crew.
