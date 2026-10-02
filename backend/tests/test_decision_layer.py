import torch

from app.decision.allocation_types import AllocationResult, Allocation
from app.decision.baselines import greedy_nearest, hungarian, min_cost_flow
from app.decision.equity import apply_equity_floor
from app.decision.gnn_policy import GNNEncoder, allocate_with_policy, equity_violation_penalty
from app.decision.scenario import Demand, DepotStock, Scenario, generate_scenario
import networkx as nx


def test_all_baselines_produce_capacity_valid_allocations():
    s = generate_scenario(seed=42)
    for fn in (greedy_nearest, hungarian, min_cost_flow):
        result = fn(s)
        assert result.is_capacity_valid(), f"{result.strategy} oversent a depot's stock"
        assert result.served_demand_pct() >= 0


def test_greedy_prioritizes_higher_urgency_zone_under_scarcity():
    g = nx.DiGraph()
    demands = [
        Demand(zone_id="low-urgency", resource="water", amount=50, urgency=0.1),
        Demand(zone_id="high-urgency", resource="water", amount=50, urgency=0.9),
    ]
    stocks = [DepotStock(depot_id="d1", resource="water", stock=50)]  # only enough for one
    travel = {("d1", "low-urgency"): 10, ("d1", "high-urgency"): 10}
    s = Scenario(demands=demands, depot_stocks=stocks, travel_time=travel, graph=g)

    result = greedy_nearest(s)
    served = {a.zone_id: a.amount for a in result.allocations}
    assert served.get("high-urgency", 0) == 50
    assert served.get("low-urgency", 0) == 0


def test_equity_floor_protects_vulnerable_zone_under_scarcity():
    g = nx.DiGraph()
    demands = [
        Demand(zone_id="zone-vuln", resource="water", amount=80, urgency=0.3, vulnerability_index=0.9),
        Demand(zone_id="zone-urgent", resource="water", amount=80, urgency=0.95, vulnerability_index=0.2),
    ]
    stocks = [DepotStock(depot_id="depot-1", resource="water", stock=90)]
    travel = {("depot-1", "zone-vuln"): 10, ("depot-1", "zone-urgent"): 5}
    s = Scenario(demands=demands, depot_stocks=stocks, travel_time=travel, graph=g)

    floor_off = greedy_nearest(s)
    floor_on = apply_equity_floor(s, greedy_nearest, floor=0.3)

    served_off = {a.zone_id: a.amount for a in floor_off.allocations}
    served_on: dict[str, float] = {}
    for a in floor_on.allocations:
        served_on[a.zone_id] = served_on.get(a.zone_id, 0.0) + a.amount

    assert served_off.get("zone-vuln", 0) < 80 * 0.3, "sanity check: baseline really does starve the vulnerable zone"
    assert served_on["zone-vuln"] >= 80 * 0.3 - 1e-6, "equity floor must guarantee the protected minimum"
    assert equity_violation_penalty(floor_on) == 0.0
    assert equity_violation_penalty(floor_off) > 0.0
    # total served stays bounded by total stock either way
    assert abs(floor_off.served_demand_pct() - floor_on.served_demand_pct()) < 1e-6


def test_gnn_policy_produces_valid_allocation():
    encoder = GNNEncoder()
    s = generate_scenario(seed=123)
    result, log_probs, value = allocate_with_policy(encoder, s, sample=False)
    assert result.is_capacity_valid()
    assert isinstance(value, torch.Tensor)
    assert len(log_probs) > 0


def test_gnn_training_runs_and_produces_finite_reward_curve():
    from app.decision.gnn_policy import train_gnn_policy

    encoder, curve = train_gnn_policy(iterations=5, episodes_per_iter=4)
    assert len(curve) == 5
    assert all(c == c for c in curve)  # no NaNs
