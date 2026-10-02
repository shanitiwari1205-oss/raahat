"""Equity Optimizer: a configurable protected-demand floor applied BEFORE
the efficiency-maximizing allocation pass runs, not a penalty bolted on
after the fact -- this matches the architecture doc's framing ("guarantees
a minimum protected demand allocation to every zone before remaining supply
is allocated by the trained policy's efficiency-maximizing pass") and makes
the floor's effect demonstrable: toggle it and the reserved units visibly
change which zones get served first.
"""
from __future__ import annotations

import copy

from .allocation_types import (
    EQUITY_VIOLATION_PENALTY_WEIGHT,
    TRAVEL_TIME_PENALTY_WEIGHT,
    Allocation,
    AllocationResult,
)
from .scenario import Scenario

DEFAULT_EQUITY_FLOOR = 0.3
VULNERABILITY_THRESHOLD = 0.6  # zones at/above this are "protected"


def reserve_equity_floor(scenario: Scenario, floor: float = DEFAULT_EQUITY_FLOOR) -> tuple[list[Allocation], Scenario]:
    """Reserves `floor` fraction of each protected (high-vulnerability)
    zone's demand from the nearest depot with stock, before the main
    allocation strategy runs. Returns (reserved_allocations, reduced_scenario)
    where reduced_scenario's demands/stocks reflect what's left to allocate.
    """
    reduced = copy.deepcopy(scenario)
    stock_by_key = {(ds.depot_id, ds.resource): ds for ds in reduced.depot_stocks}
    reserved: list[Allocation] = []

    protected_demands = [d for d in reduced.demands if d.vulnerability_index >= VULNERABILITY_THRESHOLD]

    for dem in protected_demands:
        floor_amount = dem.amount * floor
        candidates = sorted(
            (ds for ds in reduced.depot_stocks if ds.resource == dem.resource),
            key=lambda ds: reduced.travel_time.get((ds.depot_id, dem.zone_id), float("inf")),
        )
        remaining_floor = floor_amount
        for ds in candidates:
            if remaining_floor <= 0:
                break
            if ds.stock <= 0:
                continue
            send = min(ds.stock, remaining_floor)
            ds.stock -= send
            remaining_floor -= send
            dem.amount -= send
            reserved.append(Allocation(ds.depot_id, dem.zone_id, dem.resource, send))

    return reserved, reduced


def apply_equity_floor(
    scenario: Scenario, strategy_fn, floor: float = DEFAULT_EQUITY_FLOOR
) -> AllocationResult:
    """Runs the full pipeline: reserve the equity floor, then run
    `strategy_fn` (any of greedy_nearest/hungarian/min_cost_flow/a GNN
    wrapper) on what's left, then merges both into one result scored
    against the ORIGINAL scenario (so served_demand_pct reflects total
    original demand, not the reduced one)."""
    reserved, reduced_scenario = reserve_equity_floor(scenario, floor=floor)
    main_result = strategy_fn(reduced_scenario)
    combined_allocations = reserved + main_result.allocations
    return AllocationResult(
        strategy=f"{main_result.strategy}+equity_floor({floor})",
        allocations=combined_allocations,
        scenario=scenario,  # original, for correct served_demand_pct denominator
    )


def equity_violation_penalty(result: AllocationResult, floor: float = DEFAULT_EQUITY_FLOOR) -> float:
    """Penalizes shortfall against a protected-demand floor for vulnerable zones."""
    served: dict[str, float] = {}
    for a in result.allocations:
        served[a.zone_id] = served.get(a.zone_id, 0.0) + a.amount
    penalty = 0.0
    seen_zone_demand: dict[str, tuple[float, float]] = {}
    for d in result.scenario.demands:
        total, vuln = seen_zone_demand.get(d.zone_id, (0.0, d.vulnerability_index))
        seen_zone_demand[d.zone_id] = (total + d.amount, max(vuln, d.vulnerability_index))
    for zone_id, (total_demand, vuln) in seen_zone_demand.items():
        if vuln < VULNERABILITY_THRESHOLD or total_demand == 0:
            continue
        served_frac = served.get(zone_id, 0.0) / total_demand
        shortfall = max(0.0, floor - served_frac)
        penalty += shortfall
    return penalty


def compute_reward(result: AllocationResult) -> float:
    served_pct = result.served_demand_pct()
    travel_penalty = TRAVEL_TIME_PENALTY_WEIGHT * result.total_travel_time() / max(1, len(result.allocations))
    equity_penalty = EQUITY_VIOLATION_PENALTY_WEIGHT * equity_violation_penalty(result)
    return served_pct - travel_penalty - equity_penalty
