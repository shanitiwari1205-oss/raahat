"""Benchmarks all four allocation strategies on the same fixed scenarios with
one shared scoring function, so served-demand/reward numbers are directly
comparable -- this is the Innovation/Feasibility slide evidence."""
from __future__ import annotations

from .allocation_types import AllocationResult
from .baselines import greedy_nearest, hungarian, min_cost_flow
from .gnn_policy import GNNEncoder, allocate_with_policy, compute_reward, equity_violation_penalty
from .scenario import generate_scenario

FIXED_TEST_SEEDS = list(range(5000, 5020))  # 20 held-out scenarios, untouched during training


def _row(result: AllocationResult) -> dict:
    return {
        "strategy": result.strategy,
        "served_demand_pct": round(result.served_demand_pct(), 2),
        "total_travel_time": round(result.total_travel_time(), 1),
        "equity_violation": round(equity_violation_penalty(result), 3),
        "reward": round(compute_reward(result), 2),
        "capacity_valid": result.is_capacity_valid(),
    }


def run_benchmark(encoder: GNNEncoder, seeds: list[int] = FIXED_TEST_SEEDS) -> dict:
    rows_by_strategy: dict[str, list[dict]] = {"greedy": [], "hungarian": [], "min_cost_flow": [], "gnn_trained": []}

    for seed in seeds:
        scenario = generate_scenario(seed=seed)
        rows_by_strategy["greedy"].append(_row(greedy_nearest(scenario)))
        rows_by_strategy["hungarian"].append(_row(hungarian(scenario)))
        rows_by_strategy["min_cost_flow"].append(_row(min_cost_flow(scenario)))
        gnn_result, _, _ = allocate_with_policy(encoder, scenario, sample=False)
        gnn_result.strategy = "gnn_trained"
        rows_by_strategy["gnn_trained"].append(_row(gnn_result))

    summary = {}
    for strategy, rows in rows_by_strategy.items():
        n = len(rows)
        summary[strategy] = {
            "avg_served_demand_pct": round(sum(r["served_demand_pct"] for r in rows) / n, 2),
            "avg_reward": round(sum(r["reward"] for r in rows) / n, 2),
            "avg_travel_time": round(sum(r["total_travel_time"] for r in rows) / n, 2),
            "avg_equity_violation": round(sum(r["equity_violation"] for r in rows) / n, 3),
            "all_capacity_valid": all(r["capacity_valid"] for r in rows),
        }
    return {"per_scenario": rows_by_strategy, "summary": summary, "n_scenarios": len(seeds)}
