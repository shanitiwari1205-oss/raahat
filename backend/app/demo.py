"""Scripted, repeatable demo scenarios (Phase 6.1) -- deterministic sequences
a judge can trigger with one click instead of the operator manually chaining
several Scenario Injector actions.

Reuses the exact same Supervisor/World code paths as a manual click -- no
parallel allocation logic:
  - road-block / hospital-capacity steps go through World.inject_* (queued,
    identical to a manual Scenario Injector click).
  - demand-spike steps bump zone demand directly and call
    Supervisor.handle_demand_spike(...) synchronously, to get the structured
    result (served_pct, elapsed_ms, flows) back immediately instead of only a
    feed string. Calling World.inject_demand_spike() here too would double-
    process the same spike, since the background Supervisor.run() loop also
    drains the event queue and would process it a second time.
"""
from __future__ import annotations

from .sim.world import World
from .supervisor import Supervisor


async def _demand_spike_step(world: World, supervisor: Supervisor, zone_id: str, resource: str, amount: float) -> dict:
    zone = world.zones[zone_id]
    zone.demand[resource] = zone.demand.get(resource, 0.0) + amount
    return await supervisor.handle_demand_spike(zone_id, resource, amount)


async def run_demand_spike_scenario(world: World, supervisor: Supervisor) -> dict:
    """A — Demand spike: the most vulnerable zone's medicine demand spikes,
    watch the allocation engine reroute supply from nearby depots."""
    zone = max(world.zones.values(), key=lambda z: z.vulnerability_index)
    result = await _demand_spike_step(world, supervisor, zone.id, "medicine", 60.0)
    return {"scenario": "demand_spike", "label": "Demand Spike", **result}


async def run_road_block_reroute_scenario(world: World, supervisor: Supervisor) -> dict:
    """B — Road block + reroute: block depot-2's direct road to zone-4, then
    spike zone-4's demand so the allocator must route around the block."""
    u, v = "depot-2", "zone-4"
    block_evt = world.inject_road_block(u, v)
    result = await _demand_spike_step(world, supervisor, "zone-4", "water", 50.0)
    return {
        "scenario": "road_block_reroute", "label": "Road Block + Reroute",
        "blocked_edge": f"{u} -> {v}", "block_event": block_evt.to_dict(), **result,
    }


async def run_hospital_cascade_scenario(world: World, supervisor: Supervisor) -> dict:
    """C — Hospital capacity cascade: push a hospital near capacity, then
    demonstrate the equity floor's real guarantee under genuine scarcity --
    floor OFF vs floor ON, same depleted starting stock both times.

    An earlier version of this scenario tried to create starvation by having
    a second zone spike first and consume most of the stock -- that didn't
    actually work, because every single-zone demand-spike scenario considers
    BOTH depots as candidates (see Supervisor._scenario_from_world_state),
    and the "competitor" zone geographically routes to a different depot
    than the vulnerable zone, so they never contended for the same stock at
    all. Verified by running it: both came back at 100% served, which
    revealed the flaw rather than proving the floor does anything.

    The version below sidesteps the routing question entirely: it drives
    BOTH depots' stock of the resource down below what the vulnerable zone
    needs, so there just isn't enough to go around regardless of which depot
    serves it. That's the real condition the equity floor is meant to
    guarantee something under -- floor ON must deliver at least its
    guaranteed fraction up front, before the main strategy's own (sometimes
    conservative -- see report) allocation runs on what's left.
    """
    hospital = next(iter(world.hospitals.values()))
    remaining = hospital.bed_capacity - hospital.beds_used
    drop = max(1, int(remaining * 0.95))
    cap_evt = world.inject_hospital_capacity_drop(hospital.id, drop)

    vulnerable_zone = max(world.zones.values(), key=lambda z: z.vulnerability_index)
    resource = "blood"
    demand_amount = 50.0
    pre_floor = supervisor.equity_floor
    real_stock = {d.id: d.stock.get(resource, 0.0) for d in world.depots.values()}
    scarce_stock_per_depot = 10.0  # well below demand_amount, split across 2 depots

    def _reset_scarce() -> None:
        for d in world.depots.values():
            d.stock[resource] = scarce_stock_per_depot
        vulnerable_zone.demand[resource] = 0.0

    async def _run(floor: float) -> dict:
        _reset_scarce()
        supervisor.equity_floor = floor
        return await _demand_spike_step(world, supervisor, vulnerable_zone.id, resource, demand_amount)

    off_result = await _run(0.0)
    on_result = await _run(0.3)

    for d in world.depots.values():
        d.stock[resource] = real_stock[d.id]  # restore -- this was an artificial scarcity test, not a real event
    supervisor.equity_floor = pre_floor

    return {
        "scenario": "hospital_cascade", "label": "Hospital Capacity Cascade",
        "hospital_id": hospital.id, "vulnerable_zone_id": vulnerable_zone.id,
        "scarce_total_stock": scarce_stock_per_depot * len(real_stock), "demand_amount": demand_amount,
        "hospital_capacity_event": cap_evt.to_dict() if cap_evt else None,
        "equity_floor_off": off_result, "equity_floor_on": on_result,
    }


DEMO_SCENARIOS = {
    "demand_spike": run_demand_spike_scenario,
    "road_block_reroute": run_road_block_reroute_scenario,
    "hospital_cascade": run_hospital_cascade_scenario,
}
