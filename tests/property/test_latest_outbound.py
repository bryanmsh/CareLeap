"""round_trip returns the LATEST-departing outbound that still makes the check-in.

Before 2026-10-24 the outbound itinerary was the earliest-arriving journey of the day
(first bus at 06:xx for a 16:30 appointment). Reachability was right, but the planner's
door-to-door window then overlapped every work shift, so an escort ride could never be
offered, and the itinerary shown to a navigator was absurd. Reachability still comes
from the forward search; only the returned legs changed.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from engine import round_trip
from engine.raptor import one_way
from engine.synth import access_links, random_feed
from engine.types import DEFAULT_LIMITS

DATE = "2026-11-12"


def _chained(legs) -> bool:
    return all(b.dep >= a.arr for a, b in zip(legs, legs[1:]))


@settings(max_examples=150, deadline=None)
@given(seed=st.integers(min_value=0, max_value=3000),
       start_h=st.integers(min_value=7, max_value=20), minutes=st.sampled_from([30, 60, 180]))
def test_outbound_is_latest_feasible(seed: int, start_h: int, minutes: int) -> None:
    tt = random_feed(seed)
    stops = sorted(tt.stops)
    origin, clinic = stops[0], stops[-1]
    start = start_h * 3600
    r = round_trip(tt, origin, clinic, DATE, start, minutes)
    if not r.reachable:
        return
    deadline = start - DEFAULT_LIMITS.checkin_buffer
    out = r.out_legs
    assert out and _chained(out), "outbound legs must chain in time"
    assert out[-1].arr <= deadline, "outbound must still make the check-in"
    # Never earlier than the earliest-arriving journey's departure: we only ever
    # push the departure LATER.
    earliest = one_way(tt, access_links(tt, origin), access_links(tt, clinic), DATE,
                       arrive_by=deadline, origin_label="origin", dest_label="clinic")
    assert earliest is not None
    assert out[0].dep >= earliest[1][0].dep
    # Same bus-count cap as every other journey.
    assert sum(1 for leg in out if leg.kind == "bus") <= DEFAULT_LIMITS.max_transfers + 1
