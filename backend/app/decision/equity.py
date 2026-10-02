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

from .allocation_types import Allocation, AllocationResult
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
