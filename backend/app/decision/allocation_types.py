"""Shared result types + scoring, used by every allocation strategy
(baselines and the trained policy) so the benchmark comparison is apples-to-apples."""
from __future__ import annotations

from dataclasses import dataclass

from .scenario import Scenario

TRAVEL_TIME_PENALTY_WEIGHT = 0.5
EQUITY_VIOLATION_PENALTY_WEIGHT = 20.0


@dataclass
class Allocation:
    depot_id: str
    zone_id: str
    resource: str
    amount: float


@dataclass
class AllocationResult:
    strategy: str
    allocations: list[Allocation]
    scenario: Scenario

    def served_demand_pct(self) -> float:
        total_demand = sum(d.amount for d in self.scenario.demands)
        if total_demand == 0:
            return 100.0
        served_by_zone_resource: dict[tuple[str, str], float] = {}
        for a in self.allocations:
            key = (a.zone_id, a.resource)
            served_by_zone_resource[key] = served_by_zone_resource.get(key, 0.0) + a.amount
        total_served = 0.0
        for d in self.scenario.demands:
            served = served_by_zone_resource.get((d.zone_id, d.resource), 0.0)
            total_served += min(served, d.amount)
        return 100.0 * total_served / total_demand

    def total_travel_time(self) -> float:
        return sum(
            self.scenario.travel_time.get((a.depot_id, a.zone_id), 0.0) * (a.amount > 0)
            for a in self.allocations
        )

    def is_capacity_valid(self) -> bool:
        """Confirms no depot ships more of a resource than it had in stock."""
        used: dict[tuple[str, str], float] = {}
        for a in self.allocations:
            key = (a.depot_id, a.resource)
            used[key] = used.get(key, 0.0) + a.amount
        for ds in self.scenario.depot_stocks:
            if used.get((ds.depot_id, ds.resource), 0.0) > ds.stock + 1e-6:
                return False
        return True

    def reward(self) -> float:
        """served-demand - travel-time penalty, matching the GNN training objective."""
        return self.served_demand_pct() - TRAVEL_TIME_PENALTY_WEIGHT * self.total_travel_time() / max(1, len(self.allocations))
