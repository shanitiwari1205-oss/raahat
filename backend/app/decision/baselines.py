"""Classical dispatch baselines: Greedy nearest-available, Hungarian-optimal
assignment, and min-cost-flow. Built BEFORE the trained policy -- these are
the evidence a trained policy is measurably better, not just presentational.
"""
from __future__ import annotations

import networkx as nx
import numpy as np
from scipy.optimize import linear_sum_assignment

from .allocation_types import Allocation, AllocationResult
from .scenario import Scenario

INF_COST = 1e6


def greedy_nearest(scenario: Scenario) -> AllocationResult:
    """Sorts demands by urgency (most urgent first -- the PRD's required
    'different urgency levels' behavior), assigns each to the nearest depot
    with remaining stock of that resource."""
    stock = {(ds.depot_id, ds.resource): ds.stock for ds in scenario.depot_stocks}
    allocations: list[Allocation] = []

    for d in sorted(scenario.demands, key=lambda x: -x.urgency):
        candidates = sorted(
            {ds.depot_id for ds in scenario.depot_stocks if ds.resource == d.resource},
            key=lambda depot_id: scenario.travel_time.get((depot_id, d.zone_id), float("inf")),
        )
        remaining = d.amount
        for depot_id in candidates:
            if remaining <= 0:
                break
            available = stock.get((depot_id, d.resource), 0.0)
            if available <= 0:
                continue
            send = min(available, remaining)
            stock[(depot_id, d.resource)] = available - send
            remaining -= send
            allocations.append(Allocation(depot_id, d.zone_id, d.resource, send))

    return AllocationResult(strategy="greedy", allocations=allocations, scenario=scenario)


def hungarian(scenario: Scenario) -> AllocationResult:
    """One depot-slot per unit of demand, optimal bipartite assignment
    minimizing travel time. Demand is split across multiple depot "slots"
    if a single depot can't fully satisfy it, by running assignment
    resource-by-resource."""
    allocations: list[Allocation] = []
    by_resource: dict[str, list] = {}
    for d in scenario.demands:
        by_resource.setdefault(d.resource, []).append(d)

    for resource, demands in by_resource.items():
        depots = [ds for ds in scenario.depot_stocks if ds.resource == resource]
        if not depots:
            continue
        n, m = len(demands), len(depots)
        cost = np.full((n, m), INF_COST)
        for i, dem in enumerate(demands):
            for j, dep in enumerate(depots):
                tt = scenario.travel_time.get((dep.depot_id, dem.zone_id), float("inf"))
                if tt != float("inf") and dep.stock > 0:
                    cost[i, j] = tt
        row_ind, col_ind = linear_sum_assignment(cost)
        remaining_stock = {dep.depot_id: dep.stock for dep in depots}
        for i, j in zip(row_ind, col_ind):
            if cost[i, j] >= INF_COST:
                continue
            dem = demands[i]
            dep = depots[j]
            send = min(dem.amount, remaining_stock[dep.depot_id])
            if send > 0:
                remaining_stock[dep.depot_id] -= send
                allocations.append(Allocation(dep.depot_id, dem.zone_id, resource, send))

    return AllocationResult(strategy="hungarian", allocations=allocations, scenario=scenario)


def min_cost_flow(scenario: Scenario) -> AllocationResult:
    """networkx min-cost-flow over a source -> depots -> zones -> sink graph,
    one flow network per resource type. Costs are travel_time (scaled to
    integers, as networkx's flow solver requires integer weights)."""
    allocations: list[Allocation] = []
    by_resource: dict[str, list] = {}
    for d in scenario.demands:
        by_resource.setdefault(d.resource, []).append(d)

    for resource, demands in by_resource.items():
        depots = [ds for ds in scenario.depot_stocks if ds.resource == resource]
        if not depots:
            continue

        # Round once per item, then sum the rounded values -- rounding the
        # total separately from the per-edge capacities can make SOURCE/SINK
        # demand and edge capacities disagree by a unit and falsely report
        # infeasibility.
        demand_units = {dem.zone_id: int(dem.amount) for dem in demands}
        stock_units = {dep.depot_id: int(dep.stock) for dep in depots}
        total_demand_units = sum(demand_units.values())

        fg = nx.DiGraph()
        fg.add_node("SOURCE", demand=-total_demand_units)
        fg.add_node("SINK", demand=total_demand_units)

        for dep in depots:
            fg.add_edge("SOURCE", f"d:{dep.depot_id}", capacity=stock_units[dep.depot_id], weight=0)
        for dem in demands:
            fg.add_edge(f"z:{dem.zone_id}", "SINK", capacity=demand_units[dem.zone_id], weight=0)
        for dep in depots:
            for dem in demands:
                tt = scenario.travel_time.get((dep.depot_id, dem.zone_id), float("inf"))
                if tt == float("inf"):
                    continue
                fg.add_edge(f"d:{dep.depot_id}", f"z:{dem.zone_id}", capacity=10**6, weight=int(round(tt)))

        try:
            flow_dict = nx.min_cost_flow(fg)
        except (nx.NetworkXUnfeasible, nx.NetworkXError):
            # demand exceeds total reachable stock -- fall back to max partial flow,
            # capped by whichever is smaller (so SOURCE/SINK stay balanced).
            total_cap = min(sum(stock_units.values()), total_demand_units)
            fg.nodes["SOURCE"]["demand"] = -total_cap
            fg.nodes["SINK"]["demand"] = total_cap
            try:
                flow_dict = nx.min_cost_flow(fg)
            except (nx.NetworkXUnfeasible, nx.NetworkXError):
                continue

        for dep in depots:
            node = f"d:{dep.depot_id}"
            if node not in flow_dict:
                continue
            for target, amount in flow_dict[node].items():
                if amount > 0 and target.startswith("z:"):
                    zone_id = target[2:]
                    allocations.append(Allocation(dep.depot_id, zone_id, resource, float(amount)))

    return AllocationResult(strategy="min_cost_flow", allocations=allocations, scenario=scenario)
