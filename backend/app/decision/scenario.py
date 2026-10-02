"""Synthetic allocation scenarios: a batch of pending zone demands against
depot stock, with real travel times pulled from the road graph. Used by
baselines, GNN training, and the benchmark comparison -- one shared
representation, no duplicated logic across them.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

import networkx as nx

from ..sim.entities import RESOURCE_TYPES
from ..sim.graph import build_road_graph


@dataclass
class Demand:
    zone_id: str
    resource: str
    amount: float
    urgency: float  # 0-1
    vulnerability_index: float = 0.5


@dataclass
class DepotStock:
    depot_id: str
    resource: str
    stock: float


@dataclass
class Scenario:
    demands: list[Demand]
    depot_stocks: list[DepotStock]
    travel_time: dict[tuple[str, str], float]  # (depot_id, zone_id) -> minutes, inf if unreachable
    graph: nx.DiGraph


def _travel_time_matrix(g: nx.DiGraph, depots: list[str], zones: list[str]) -> dict[tuple[str, str], float]:
    out = {}
    for d in depots:
        lengths = nx.single_source_dijkstra_path_length(
            g, d, weight=lambda u, v, data: None if data.get("blocked") else data["travel_time"]
        )
        for z in zones:
            out[(d, z)] = lengths.get(z, float("inf"))
    return out


def generate_scenario(
    seed: int | None = None,
    n_zones: int = 5,
    depots: tuple[str, ...] = ("depot-1", "depot-2"),
    blocked_edges: list[tuple[str, str]] | None = None,
    resource: str | None = None,
) -> Scenario:
    """Generates a reproducible synthetic scenario. Pass `seed` for
    deterministic test/benchmark scenarios."""
    rng = random.Random(seed)
    g = build_road_graph()
    for u, v in blocked_edges or []:
        if g.has_edge(u, v):
            g[u][v]["blocked"] = True
        if g.has_edge(v, u):
            g[v][u]["blocked"] = True

    zone_ids = [f"zone-{i}" for i in range(1, n_zones + 1)]
    resources = [resource] if resource else RESOURCE_TYPES

    demands = []
    for z in zone_ids:
        r = rng.choice(resources)
        demands.append(Demand(
            zone_id=z,
            resource=r,
            amount=rng.uniform(10, 60),
            urgency=rng.uniform(0.2, 1.0),
            vulnerability_index=rng.uniform(0.2, 0.9),
        ))

    depot_stocks = []
    for d in depots:
        for r in resources:
            depot_stocks.append(DepotStock(depot_id=d, resource=r, stock=rng.uniform(80, 250)))

    travel = _travel_time_matrix(g, list(depots), zone_ids)

    return Scenario(demands=demands, depot_stocks=depot_stocks, travel_time=travel, graph=g)
