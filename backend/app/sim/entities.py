"""Entity models for the disaster simulation world.

Resource types are a fixed small set to keep the demo legible:
  water, medicine, food, blood
"""
from __future__ import annotations

from dataclasses import dataclass, field

RESOURCE_TYPES = ["water", "medicine", "food", "blood"]

# ₹ cost per unit, used to translate resource movement into fund movement
# so the ledger can report both resources AND funds, per the PRD's wording.
UNIT_COST_INR = {
    "water": 20,
    "medicine": 150,
    "food": 40,
    "blood": 500,
}


@dataclass
class Zone:
    id: str
    population: int
    demand: dict[str, float] = field(default_factory=lambda: {r: 0.0 for r in RESOURCE_TYPES})
    unmet_since: dict[str, float] = field(default_factory=lambda: {r: 0.0 for r in RESOURCE_TYPES})
    urgency: float = 0.0
    vulnerability_index: float = 0.5  # 0-1, static per-zone factor (e.g. remoteness, pre-existing needs)

    def total_demand(self) -> float:
        return sum(self.demand.values())


@dataclass
class Hospital:
    id: str
    bed_capacity: int
    icu_capacity: int
    beds_used: int = 0
    icu_used: int = 0

    def bed_free_pct(self) -> float:
        return 1.0 - (self.beds_used / self.bed_capacity if self.bed_capacity else 0)


@dataclass
class Depot:
    id: str
    stock: dict[str, float] = field(default_factory=lambda: {r: 0.0 for r in RESOURCE_TYPES})
    budget_inr: float = 0.0  # funds on hand, separate from physical stock

    def can_afford(self, resource: str, amount: float) -> bool:
        return self.stock.get(resource, 0) >= amount


@dataclass
class Vehicle:
    id: str
    kind: str  # "ambulance" | "relief_truck"
    capacity: float
    speed_factor: float  # multiplies travel_time (lower is faster)
    home_depot: str
    assignment: str | None = None


@dataclass
class Donor:
    """A funding stakeholder that periodically injects budget into depots.

    Modeling this explicitly is what lets the ledger demonstrate fund
    movement ACROSS stakeholders (donor -> depot -> zone), not just
    physical-unit movement from a single depot.
    """
    id: str
    name: str
    replenish_interval_s: float
    replenish_amount_inr: float
    last_replenish_t: float = 0.0


def make_default_world_entities() -> dict:
    from .graph import DEPOT_COORDS, HOSPITAL_COORDS, ZONE_COORDS

    zones = {
        zid: Zone(id=zid, population=pop, vulnerability_index=vuln)
        for zid, pop, vuln in [
            ("zone-1", 42000, 0.3),
            ("zone-2", 28000, 0.4),
            ("zone-3", 51000, 0.6),
            ("zone-4", 35000, 0.5),
            ("zone-5", 19000, 0.75),  # smaller, more vulnerable zone -> equity floor target
        ]
    }

    hospitals = {
        "hospital-1": Hospital(id="hospital-1", bed_capacity=120, icu_capacity=20),
        "hospital-2": Hospital(id="hospital-2", bed_capacity=90, icu_capacity=15),
    }

    depots = {
        "depot-1": Depot(
            id="depot-1",
            stock={"water": 2000, "medicine": 500, "food": 1500, "blood": 100},
            budget_inr=500_000,
        ),
        "depot-2": Depot(
            id="depot-2",
            stock={"water": 1800, "medicine": 400, "food": 1200, "blood": 80},
            budget_inr=400_000,
        ),
    }

    vehicles = {
        "amb-1": Vehicle(id="amb-1", kind="ambulance", capacity=4, speed_factor=0.7, home_depot="depot-1"),
        "amb-2": Vehicle(id="amb-2", kind="ambulance", capacity=4, speed_factor=0.7, home_depot="depot-2"),
        "truck-1": Vehicle(id="truck-1", kind="relief_truck", capacity=200, speed_factor=1.3, home_depot="depot-1"),
        "truck-2": Vehicle(id="truck-2", kind="relief_truck", capacity=200, speed_factor=1.3, home_depot="depot-2"),
    }

    donors = {
        "donor-1": Donor(
            id="donor-1", name="State Disaster Relief Fund",
            replenish_interval_s=30.0, replenish_amount_inr=150_000,
        ),
        "donor-2": Donor(
            id="donor-2", name="Red Cross India (simulated)",
            replenish_interval_s=45.0, replenish_amount_inr=100_000,
        ),
    }

    assert set(zones) == set(ZONE_COORDS)
    assert set(hospitals) == set(HOSPITAL_COORDS)
    assert set(depots) == set(DEPOT_COORDS)

    return {"zones": zones, "hospitals": hospitals, "depots": depots, "vehicles": vehicles, "donors": donors}
