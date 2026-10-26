"""RAPTOR round-trip router — the authoritative engine (docs/contracts.md §2).

RAPTOR (Round-bAsed Public Transit Optimized Router) computes earliest arrival
by rounds, where round k is "reachable using at most k vehicle trips". We run
it over the in-memory `Timetable`, resolve origin/clinic to boarding stops via
walk links, and answer the round-trip reachability question the whole project
is built on. This is the one thing the plan says never to cut: the cube, the
planner and the audit all call round_trip(...).

Reachability (authoritative, contracts.md §2): a slot is reachable iff an
outbound journey arrives <= start - checkin_buffer AND a return journey departs
>= start + minutes*60, both on the same service date, within limits
(<= 2 transfers, <= 2h each way, walk <= 800 m, earliest home departure >= 05:30).

All times are seconds since local midnight; GTFS times >= 86400 are preserved
(midnight safety — steering/gtfs-domain.md).
"""

from __future__ import annotations

from engine.gtfs import Timetable, fmt_gtfs_time
from engine.synth import access_links
from engine.types import (
    DEFAULT_LIMITS,
    ClinicRef,
    Leg,
    Limits,
    OriginRef,
    RoundTripResult,
)

# A label is the best-known way to reach a stop: arrival time + the legs taken.
Label = tuple[int, list[Leg]]


def _run_raptor(
    tt: Timetable,
    sources: dict[str, int],  # stop_id -> arrival time there (after the access walk)
    source_legs: dict[str, list[Leg]],  # the walk legs that reached each source stop
    limits: Limits,
) -> dict[str, Label]:
    """Earliest-arrival RAPTOR from a set of already-reached source stops.

    `sources[stop] = t` means we are standing at `stop` at time `t`. Returns the
    best (arrival, legs) per reachable stop, using <= limits.max_transfers trips.
    """
    best: dict[str, Label] = {s: (t, list(source_legs.get(s, []))) for s, t in sources.items()}

    # Round 0: foot-transfer closure from the source stops, so a walk-only path
    # (e.g. a transfer edge origin->dest) is found even with no bus ride.
    _relax_transfers(tt, best, set(sources))

    # Stops reachable using STRICTLY FEWER than k buses, as of the start of round k.
    # A round may only board trips from these, so round k adds the k-th bus and no
    # more — this is what bounds the journey to <= max_transfers transfers. Reading
    # a frozen snapshot (not the live `best`) stops one round from chaining several
    # buses in a single pass.
    reachable_prev: dict[str, Label] = dict(best)

    for _round in range(limits.max_transfers + 1):
        if not reachable_prev:
            break
        improved: set[str] = set()
        # Ride every trip we can board from a stop reached in the PREVIOUS round.
        for trip_id, sts in tt.trip_stop_times.items():
            board_st = None  # the stop_time at which we boarded this trip
            board_label: Label | None = None
            for st in sts:  # sorted by seq
                if board_st is None:
                    cur = reachable_prev.get(st.stop_id)
                    if cur is None:
                        continue
                    ready = cur[0]
                    # transfer buffer applies if we arrived here by a previous bus
                    if cur[1] and cur[1][-1].kind == "bus":
                        ready += tt.min_transfer_time(st.stop_id, st.stop_id)
                    if ready <= st.dep:
                        board_st = st
                        board_label = cur
                    continue
                # riding: try to alight at st
                assert board_label is not None and board_st is not None
                if st.arr - board_st.dep > limits.max_leg_seconds:
                    continue  # exceeds the 2h-per-leg limit
                prev = best.get(st.stop_id)
                if prev is None or st.arr < prev[0]:
                    legs = list(board_label[1])
                    legs.append(
                        Leg(
                            kind="bus",
                            from_stop=board_st.stop_id,
                            to_stop=st.stop_id,
                            route_id=tt.trips[trip_id].route_id if trip_id in tt.trips else None,
                            dep=board_st.dep,
                            arr=st.arr,
                        )
                    )
                    best[st.stop_id] = (st.arr, legs)
                    improved.add(st.stop_id)
        # foot transfers from stops improved this round (walks don't count as transfers)
        _relax_transfers(tt, best, improved)
        # next round boards only from what THIS round newly reached
        reachable_prev = {s: best[s] for s in improved}
    return best


def _relax_transfers(tt: Timetable, best: dict[str, Label], from_stops: set[str]) -> None:
    """Relax foot transfers out of `from_stops`, mutating `best` and `from_stops`
    in place until no further improvement (transitive within this call)."""
    queue = list(from_stops)
    while queue:
        from_stop = queue.pop()
        cur = best.get(from_stop)
        if cur is None:
            continue
        arr_from, legs_from = cur
        for tr in tt.transfers_from.get(from_stop, ()):
            arr_to = arr_from + tr.min_transfer_time
            prev = best.get(tr.to_stop)
            if prev is None or arr_to < prev[0]:
                legs = list(legs_from) + [
                    Leg(kind="walk", from_stop=from_stop, to_stop=tr.to_stop,
                        route_id=None, dep=arr_from, arr=arr_to)
                ]
                best[tr.to_stop] = (arr_to, legs)
                from_stops.add(tr.to_stop)
                queue.append(tr.to_stop)


def earliest_arrival(
    tt: Timetable,
    from_stops: dict[str, int],
    date: str,
    depart_after: int | None = None,
    limits: Limits = DEFAULT_LIMITS,
) -> dict[str, Label]:
    """Best (arrival, legs) per stop, from `from_stops` (stop_id -> ready time).

    Exposed so CSA / brute force compare against the same interface.
    """
    srcs = {s: (max(t, depart_after) if depart_after is not None else t) for s, t in from_stops.items()}
    return _run_raptor(tt, srcs, {}, limits)


# --------------------------------------------------------------------------
# Backward RAPTOR: latest departure that still arrives by a deadline.
# Symmetric to the forward search — ride trips from alight back to board,
# maximising the departure time at each stop. One-to-many from the TARGET
# stops (e.g. a clinic) to every origin, in a single scan: exactly the
# "reverse profile" search M2 needs to build the reachability cube.
# --------------------------------------------------------------------------
# A backward label: the LATEST time you can leave this stop and still make it,
# plus the legs (recorded forward: earliest leg first).
BLabel = tuple[int, list[Leg]]


def _run_raptor_backward(
    tt: Timetable,
    targets: dict[str, int],  # stop_id -> latest time you may ARRIVE there (the deadline)
    limits: Limits,
) -> dict[str, BLabel]:
    """Latest-departure RAPTOR toward a set of target stops.

    `targets[stop] = t` means "arriving at `stop` by `t` is success". Returns,
    per stop, the LATEST departure time (and legs) from which you can still
    reach a target within <= limits.max_transfers trips.
    """
    # best[stop] = (latest_departure_from_stop, legs_from_here_to_a_target)
    best: dict[str, BLabel] = {s: (t, []) for s, t in targets.items()}
    _relax_transfers_backward(tt, best, set(targets))
    # Same invariant as the forward search (bug-transfer-limit): round k may only
    # alight at stops reached in round k-1, read from a frozen snapshot, so one
    # round cannot chain several buses.
    reachable_prev: dict[str, BLabel] = dict(best)

    for _round in range(limits.max_transfers + 1):
        if not reachable_prev:
            break
        improved: set[str] = set()
        for trip_id, sts in tt.trip_stop_times.items():
            # scan the trip in REVERSE: pick an alighting stop we can use, then
            # ride backward to every earlier stop, maximising its departure.
            alight_st = None
            alight_label: BLabel | None = None
            for st in reversed(sts):  # from last seq to first
                if alight_st is None:
                    cur = reachable_prev.get(st.stop_id)
                    if cur is None:
                        continue
                    latest_ok = cur[0]
                    # transfer buffer if the onward leg from here is a bus
                    if cur[1] and cur[1][0].kind == "bus":
                        latest_ok -= tt.min_transfer_time(st.stop_id, st.stop_id)
                    # we may alight here if the bus ARRIVES by latest_ok
                    if st.arr <= latest_ok:
                        alight_st = st
                        alight_label = cur
                    continue
                # riding backward: board at st (earlier seq), departing st.dep
                assert alight_label is not None and alight_st is not None
                if alight_st.arr - st.dep > limits.max_leg_seconds:
                    continue
                prev = best.get(st.stop_id)
                if prev is None or st.dep > prev[0]:
                    leg = Leg(
                        kind="bus",
                        from_stop=st.stop_id,
                        to_stop=alight_st.stop_id,
                        route_id=tt.trips[trip_id].route_id if trip_id in tt.trips else None,
                        dep=st.dep,
                        arr=alight_st.arr,
                    )
                    best[st.stop_id] = (st.dep, [leg] + list(alight_label[1]))
                    improved.add(st.stop_id)
        _relax_transfers_backward(tt, best, improved)
        reachable_prev = {s: best[s] for s in improved}
    return best


def _relax_transfers_backward(tt: Timetable, best: dict[str, BLabel], to_stops: set[str]) -> None:
    """Relax foot transfers INTO `to_stops` (backward): if you can be at B by
    `best[B]`, then you can leave A by `best[B] - transfer` and walk to B."""
    queue = list(to_stops)
    while queue:
        b = queue.pop()
        cur = best.get(b)
        if cur is None:
            continue
        latest_b, legs_b = cur
        # a transfer A->B lets us start at A at (latest_b - transfer_time)
        for a, tlist in tt.transfers_from.items():
            for tr in tlist:
                if tr.to_stop != b:
                    continue
                latest_a = latest_b - tr.min_transfer_time
                prev = best.get(a)
                if prev is None or latest_a > prev[0]:
                    leg = Leg(kind="walk", from_stop=a, to_stop=b, route_id=None,
                              dep=latest_a, arr=latest_b)
                    best[a] = (latest_a, [leg] + list(legs_b))
                    to_stops.add(a)
                    queue.append(a)


def latest_departure(
    tt: Timetable,
    to_stops: dict[str, int],
    date: str,
    arrive_by: int | None = None,
    limits: Limits = DEFAULT_LIMITS,
) -> dict[str, BLabel]:
    """One-to-many REVERSE profile search.

    Given target stops and the time by which you must arrive (`arrive_by`, or a
    per-stop deadline in `to_stops`), return the LATEST departure (and legs) from
    every stop that still reaches a target within the limits. This is the reverse
    half of the cube: the latest a patient may leave home and still check in on
    time. Pair it with `earliest_arrival` from the clinic for the return home.
    """
    targets = {s: (min(t, arrive_by) if arrive_by is not None else t) for s, t in to_stops.items()}
    return _run_raptor_backward(tt, targets, limits)


def one_way(
    tt: Timetable,
    origin_stops: list[tuple[str, int]],  # (stop_id, walk_seconds) at the origin
    dest_stops: list[tuple[str, int]],  # (stop_id, walk_seconds) at the destination
    date: str,
    depart_after: int | None = None,
    arrive_by: int | None = None,
    limits: Limits = DEFAULT_LIMITS,
    origin_label: str = "origin",
    dest_label: str = "clinic",
) -> tuple[int, list[Leg]] | None:
    """Earliest-arriving one-way journey from any origin stop to any dest stop.

    Returns (arrival_at_destination_including_egress_walk, legs) or None. If
    `arrive_by` is set, only journeys arriving <= arrive_by are accepted.
    """
    if not origin_stops or not dest_stops:
        return None
    base = depart_after if depart_after is not None else min(
        (st.dep for sts in tt.trip_stop_times.values() for st in sts), default=0
    )
    sources: dict[str, int] = {}
    source_legs: dict[str, list[Leg]] = {}
    for stop_id, walk_sec in origin_stops:
        ready = base + walk_sec
        if stop_id not in sources or ready < sources[stop_id]:
            sources[stop_id] = ready
            source_legs[stop_id] = [
                Leg(kind="walk", from_stop=origin_label, to_stop=stop_id, route_id=None, dep=base, arr=ready)
            ]
    best = _run_raptor(tt, sources, source_legs, limits)

    chosen: tuple[int, list[Leg]] | None = None
    for stop_id, walk_sec in dest_stops:
        lab = best.get(stop_id)
        if lab is None:
            continue
        arr = lab[0] + walk_sec
        if arrive_by is not None and arr > arrive_by:
            continue
        legs = list(lab[1])
        if walk_sec > 0:
            legs = legs + [
                Leg(kind="walk", from_stop=stop_id, to_stop=dest_label, route_id=None,
                    dep=arr - walk_sec, arr=arr)
            ]
        if chosen is None or arr < chosen[0]:
            chosen = (arr, legs)
    return chosen


def _latest_outbound(
    tt: Timetable,
    origin_links: list[tuple[str, int]],
    clinic_links: list[tuple[str, int]],
    date: str,
    must_arrive_by: int,
    limits: Limits,
) -> tuple[int, list[Leg]] | None:
    """The latest-departing origin -> clinic journey that still arrives by the deadline.

    Backward RAPTOR from every clinic stop (deadline minus its egress walk), then pick
    the origin stop whose latest departure, minus the access walk, is latest. Legs are
    returned forward, with the access and egress walks attached, in the same shape as
    `one_way`. Returns None when the reverse search finds nothing (the caller keeps the
    forward journey, so reachability never depends on this helper).
    """
    egress = {stop: walk for stop, walk in clinic_links}
    targets: dict[str, int] = {}
    for stop, walk in clinic_links:
        deadline = must_arrive_by - walk
        if stop not in targets or deadline > targets[stop]:
            targets[stop] = deadline
    labels = latest_departure(tt, targets, date, limits=limits)
    best: tuple[int, str, int, BLabel] | None = None
    for stop, walk in origin_links:
        lab = labels.get(stop)
        if lab is None:
            continue
        leave_home = lab[0] - walk
        if best is None or leave_home > best[0]:
            best = (leave_home, stop, walk, lab)
    if best is None:
        return None
    leave_home, stop, walk, (dep_at_stop, legs) = best
    legs = list(legs)
    out: list[Leg] = []
    if walk > 0:
        out.append(Leg(kind="walk", from_stop="origin", to_stop=stop, route_id=None, dep=leave_home, arr=dep_at_stop))
    out.extend(legs)
    last_stop = legs[-1].to_stop if legs else stop
    at_stop = legs[-1].arr if legs else dep_at_stop
    egress_walk = egress.get(last_stop, 0)
    if egress_walk > 0:
        out.append(Leg(kind="walk", from_stop=last_stop, to_stop="clinic", route_id=None, dep=at_stop, arr=at_stop + egress_walk))
    arrival = at_stop + egress_walk
    if arrival > must_arrive_by:  # defensive: never return a journey that misses the deadline
        return None
    return (arrival, out)


def round_trip(
    tt: Timetable,
    origin: OriginRef,
    clinic: ClinicRef,
    date: str,
    start: int,
    minutes: int,
    limits: Limits = DEFAULT_LIMITS,
) -> RoundTripResult:
    """Authoritative round-trip reachability (docs/contracts.md §2)."""
    if tt.service_date and tt.service_date != date:
        return RoundTripResult(False, [], [], None, f"feed is for {tt.service_date}, not {date}")

    origin_links = access_links(tt, origin, limits)
    clinic_links = access_links(tt, clinic, limits)
    if not origin_links:
        return RoundTripResult(False, [], [], None, "origin resolves to no stop within walk limit")
    if not clinic_links:
        return RoundTripResult(False, [], [], None, "clinic resolves to no stop within walk limit")

    must_arrive_by = start - limits.checkin_buffer
    visit_end = start + minutes * 60

    # Outbound: origin -> clinic, arriving by must_arrive_by. Feasibility comes from the
    # forward search (earliest arrival <= deadline); the itinerary we RETURN is the
    # latest-departing journey that still makes the deadline (reverse profile), so a
    # 15:30 appointment is not shown with the 06:00 first bus and the planner's
    # door-to-door window (work-shift / childcare check) is the one a patient would use.
    out = one_way(tt, origin_links, clinic_links, date, arrive_by=must_arrive_by,
                  limits=limits, origin_label="origin", dest_label="clinic")
    out_legs = out[1] if out else []
    if out:
        latest = _latest_outbound(tt, origin_links, clinic_links, date, must_arrive_by, limits)
        if latest is not None:
            out = latest
            out_legs = latest[1]

    # Return: clinic -> home, departing >= visit_end.
    ret = one_way(tt, clinic_links, origin_links, date, depart_after=visit_end,
                  limits=limits, origin_label="clinic", dest_label="home")
    ret_legs = ret[1] if ret else []

    last_bus_home: int | None = None
    if ret_legs:
        bus_legs = [leg for leg in ret_legs if leg.kind == "bus"]
        last_bus_home = bus_legs[0].dep if bus_legs else None
        if last_bus_home is not None and last_bus_home < limits.earliest_home_dep:
            ret_legs = []
            last_bus_home = None

    reachable = bool(out_legs) and bool(ret_legs)

    if reachable:
        reason = (
            f"arrive {fmt_gtfs_time(out[0])} ok (<= {fmt_gtfs_time(must_arrive_by)}); "
            f"return after visit ends {fmt_gtfs_time(visit_end)}"
        )
        if last_bus_home is not None:
            reason += f"; last useful bus {fmt_gtfs_time(last_bus_home)}"
    elif not out_legs:
        reason = f"no outbound arriving by {fmt_gtfs_time(must_arrive_by)}"
    else:
        reason = f"no return departing after visit ends {fmt_gtfs_time(visit_end)}"

    return RoundTripResult(
        reachable=reachable,
        out_legs=out_legs,
        ret_legs=ret_legs,
        last_bus_home=last_bus_home,
        reason=reason,
    )
