"""Typed disaster events."""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
import time


@dataclass
class SimEvent:
    kind: str = "SimEvent"
    t: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DemandSpike(SimEvent):
    zone_id: str = ""
    resource: str = ""
    amount: float = 0.0
    kind: str = "DemandSpike"


@dataclass
class HospitalFull(SimEvent):
    hospital_id: str = ""
    kind: str = "HospitalFull"


@dataclass
class RoadBlocked(SimEvent):
    u: str = ""
    v: str = ""
    kind: str = "RoadBlocked"


@dataclass
class SupplyLow(SimEvent):
    depot_id: str = ""
    resource: str = ""
    kind: str = "SupplyLow"


@dataclass
class AmbulanceDown(SimEvent):
    vehicle_id: str = ""
    kind: str = "AmbulanceDown"


def now() -> float:
    return time.time()
