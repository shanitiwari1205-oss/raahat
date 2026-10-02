"""Road/zone/hospital/depot graph for the RAAHAT disaster simulation.

Coordinates are real approximate locations around Mumbai so the frontend map
looks geographically honest instead of abstract.
"""
from __future__ import annotations

import networkx as nx

# (lat, lon) — real approximate Mumbai-area locations
ZONE_COORDS = {
    "zone-1": (19.0760, 72.8777),  # Mumbai city center (Fort)
    "zone-2": (19.1197, 72.8468),  # Bandra
    "zone-3": (19.0330, 72.8570),  # Worli
    "zone-4": (19.1663, 72.8526),  # Andheri
    "zone-5": (19.2183, 72.9781),  # Mulund
}

HOSPITAL_COORDS = {
    "hospital-1": (19.0896, 72.8656),  # near Lower Parel
    "hospital-2": (19.1500, 72.8400),  # near Khar
}

DEPOT_COORDS = {
    "depot-1": (19.0728, 72.8826),  # near Byculla
    "depot-2": (19.1868, 72.8587),  # near Jogeshwari
}


def build_road_graph() -> nx.DiGraph:
    """Builds the weighted directed road graph.

    Nodes: zones, hospitals, depots (all share one graph so routing can
    cross entity types). Edges carry travel_time (minutes), capacity
    (vehicles/hour), and a blocked flag toggled by disaster events.
    """
    g = nx.DiGraph()

    for node_id, (lat, lon) in {**ZONE_COORDS, **HOSPITAL_COORDS, **DEPOT_COORDS}.items():
        kind = "zone" if node_id in ZONE_COORDS else ("hospital" if node_id in HOSPITAL_COORDS else "depot")
        g.add_node(node_id, kind=kind, lat=lat, lon=lon)

    # Hand-authored road edges connecting depots -> zones -> hospitals,
    # plus some zone-zone links so blocking one road still leaves a reroute path.
    edges = [
        ("depot-1", "zone-1", 8, 40),
        ("depot-1", "zone-3", 12, 30),
        ("depot-1", "zone-2", 18, 25),
        ("depot-2", "zone-4", 7, 40),
        ("depot-2", "zone-5", 10, 30),
        ("depot-2", "zone-2", 15, 25),
        ("zone-1", "zone-3", 9, 35),
        ("zone-1", "zone-2", 14, 30),
        ("zone-2", "zone-4", 11, 30),
        ("zone-4", "zone-5", 13, 25),
        ("zone-1", "hospital-1", 6, 20),
        ("zone-3", "hospital-1", 5, 20),
        ("zone-2", "hospital-2", 7, 20),
        ("zone-4", "hospital-2", 6, 20),
        ("zone-5", "hospital-2", 14, 15),
    ]

    for u, v, travel_time, capacity in edges:
        g.add_edge(u, v, travel_time=travel_time, capacity=capacity, blocked=False)
        g.add_edge(v, u, travel_time=travel_time, capacity=capacity, blocked=False)

    return g


def build_stress_graph(n_zones: int = 15) -> nx.DiGraph:
    """A synthetic, larger road graph for Phase 6.4's stress test -- real
    DEPOT_COORDS/HOSPITAL_COORDS reused, zones generated on a jittered ring
    around Mumbai and chained to their neighbors plus the nearer depot, so
    the graph stays fully connected (every zone reachable from both depots)
    at any n_zones."""
    import math

    g = nx.DiGraph()
    for node_id, (lat, lon) in {**DEPOT_COORDS, **HOSPITAL_COORDS}.items():
        kind = "depot" if node_id in DEPOT_COORDS else "hospital"
        g.add_node(node_id, kind=kind, lat=lat, lon=lon)

    center_lat, center_lon = 19.12, 72.90
    zone_ids = [f"zone-{i}" for i in range(1, n_zones + 1)]
    for i, zid in enumerate(zone_ids):
        angle = 2 * math.pi * i / n_zones
        radius = 0.08 + 0.015 * (i % 3)
        lat = center_lat + radius * math.sin(angle)
        lon = center_lon + radius * math.cos(angle)
        g.add_node(zid, kind="zone", lat=lat, lon=lon)

    depot_ids = list(DEPOT_COORDS)
    for i, zid in enumerate(zone_ids):
        depot = depot_ids[i % len(depot_ids)]
        g.add_edge(depot, zid, travel_time=8 + (i % 7), capacity=30, blocked=False)
        g.add_edge(zid, depot, travel_time=8 + (i % 7), capacity=30, blocked=False)
        nxt = zone_ids[(i + 1) % n_zones]
        if nxt != zid:
            g.add_edge(zid, nxt, travel_time=6 + (i % 5), capacity=25, blocked=False)
            g.add_edge(nxt, zid, travel_time=6 + (i % 5), capacity=25, blocked=False)

    return g


def shortest_travel_time(g: nx.DiGraph, source: str, target: str) -> float | None:
    """Dijkstra over travel_time, skipping blocked edges. None if unreachable."""
    def weight(u, v, data):
        if data.get("blocked"):
            return None
        return data["travel_time"]

    try:
        return nx.shortest_path_length(g, source, target, weight=weight)
    except nx.NetworkXNoPath:
        return None
