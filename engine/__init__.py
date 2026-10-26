"""CareLeap routing engine.

Public surface used across the team (see docs/contracts.md §2):
    - types:  Leg, RoundTripResult, OriginRef, ClinicRef, Limits
    - gtfs:   Timetable (in-memory feed), load_gtfs_dir
    - raptor: round_trip(...)  (RAPTOR, the authoritative implementation)
"""

from engine.raptor import earliest_arrival, latest_departure, one_way, round_trip
from engine.types import (
    ClinicRef,
    Leg,
    Limits,
    OriginRef,
    RoundTripResult,
)

__all__ = [
    "ClinicRef",
    "Leg",
    "Limits",
    "OriginRef",
    "RoundTripResult",
    "earliest_arrival",
    "latest_departure",
    "one_way",
    "round_trip",
]
