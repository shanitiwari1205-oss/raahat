"""Phase 6.4 stress test -- run with: python -m scripts.stress_test (from backend/)

Measures, with real wall-clock timing, not estimates:
  1. Decision-layer latency (all 4 strategies) on a 15-zone synthetic graph,
     well above the 5-zone demo world -- proves the allocation engine scales.
  2. The live World.tick() cost, run for real over many iterations.
  3. Real end-to-end throughput of Supervisor.handle_demand_spike against a
     live World instance, run back-to-back -- the actual bottleneck an
     operator rapid-clicking the Scenario Injector would hit.
"""
from __future__ import annotations

import asyncio
import statistics
import time

from app.decision.baselines import greedy_nearest, hungarian, min_cost_flow
from app.decision.gnn_policy import GNNEncoder, allocate_with_policy
from app.decision.scenario import generate_scenario
from app.decision.triage import train_triage_scorer
from app.ledger.store import Ledger
from app.sim.graph import build_stress_graph
from app.sim.world import World
from app.supervisor import Supervisor


def _time_decision_layer(n_zones: int, n_trials: int = 15) -> dict:
    graph = build_stress_graph(n_zones)
    encoder = GNNEncoder()
    results: dict[str, list[float]] = {"greedy": [], "hungarian": [], "min_cost_flow": [], "gnn_trained": []}

    for trial in range(n_trials):
        scenario = generate_scenario(seed=9000 + trial, n_zones=n_zones, graph=graph)

        t0 = time.perf_counter()
        greedy_nearest(scenario)
        results["greedy"].append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        hungarian(scenario)
        results["hungarian"].append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        min_cost_flow(scenario)
        results["min_cost_flow"].append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        allocate_with_policy(encoder, scenario, sample=False)
        results["gnn_trained"].append((time.perf_counter() - t0) * 1000)

    return {k: {"mean_ms": round(statistics.mean(v), 3), "max_ms": round(max(v), 3)} for k, v in results.items()}


def _time_tick_loop(n_ticks: int = 300) -> dict:
    world = World()
    durations = []
    for _ in range(n_ticks):
        t0 = time.perf_counter()
        world.tick(dt=1.0)
        durations.append((time.perf_counter() - t0) * 1000)
    return {"n_ticks": n_ticks, "mean_ms": round(statistics.mean(durations), 4), "max_ms": round(max(durations), 4)}


async def _time_supervisor_throughput(n_spikes: int = 20) -> dict:
    world = World()
    ledger = Ledger(db_path=":memory:")
    encoder = GNNEncoder()
    triage_model, _ = train_triage_scorer(epochs=50)
    supervisor = Supervisor(world, ledger, encoder, triage_model)

    zone_ids = list(world.zones)
    t_start = time.perf_counter()
    per_call = []
    for i in range(n_spikes):
        zid = zone_ids[i % len(zone_ids)]
        world.zones[zid].demand["water"] = world.zones[zid].demand.get("water", 0.0) + 10.0
        t0 = time.perf_counter()
        await supervisor.handle_demand_spike(zid, "water", 10.0)
        per_call.append((time.perf_counter() - t0) * 1000)
    total_s = time.perf_counter() - t_start
    ledger.close()
    return {
        "n_spikes": n_spikes,
        "total_s": round(total_s, 3),
        "events_per_sec": round(n_spikes / total_s, 2),
        "mean_ms_per_event": round(statistics.mean(per_call), 3),
        "max_ms_per_event": round(max(per_call), 3),
    }


def main():
    print("=== Phase 6.4 Stress Test ===\n")

    print("-- Decision layer @ 5 zones (demo scale) --")
    print(_time_decision_layer(n_zones=5))

    print("\n-- Decision layer @ 15 zones (stress scale) --")
    print(_time_decision_layer(n_zones=15))

    print("\n-- World.tick() over 300 iterations --")
    print(_time_tick_loop(300))

    print("\n-- Supervisor throughput: 20 consecutive demand-spike events --")
    print(asyncio.run(_time_supervisor_throughput(20)))


if __name__ == "__main__":
    main()
