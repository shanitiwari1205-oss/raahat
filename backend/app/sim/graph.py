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
