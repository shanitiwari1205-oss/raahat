"""Supervisor Loop: consumes the world's event queue, routes each event
through Triage Scorer -> Allocation Engine -> Equity Optimizer, writes the
result to the Ledger, and pushes a human-readable line to the Allocation
Feed broadcast. This is the one place Phases 1+2+3 actually meet.
"""
from __future__ import annotations

import asyncio
import time

from .decision.baselines import greedy_nearest, hungarian, min_cost_flow
from .decision.equity import DEFAULT_EQUITY_FLOOR, apply_equity_floor
from .decision.np_policy import NumpyGNNEncoder, NumpyTriage, allocate_with_policy
from .decision.scenario import Demand, DepotStock, Scenario
from .ledger.store import Ledger
from .sim.entities import UNIT_COST_INR
from .sim.world import World

STRATEGIES = {
    "greedy": greedy_nearest,
    "hungarian": hungarian,
    "min_cost_flow": min_cost_flow,
}


class Supervisor:
    def __init__(self, world: World, ledger: Ledger, gnn_encoder: NumpyGNNEncoder, triage_model: NumpyTriage):
        self.world = world
        self.ledger = ledger
        self.gnn_encoder = gnn_encoder
        self.triage_model = triage_model
        self.equity_floor = DEFAULT_EQUITY_FLOOR
        self.active_strategy = "gnn_trained"  # operator-selectable, matches the comparison demo
        self.feed_subscribers: list[asyncio.Queue] = []
        self._max_unmet_seen = 200.0  # normalizer for triage features, matches training scale

    def subscribe_feed(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self.feed_subscribers.append(q)
        return q

    def unsubscribe_feed(self, q: asyncio.Queue) -> None:
        if q in self.feed_subscribers:
            self.feed_subscribers.remove(q)

    async def _publish_feed(self, message: str, flows: list[dict] | None = None) -> None:
        item: dict = {"t": time.time(), "message": message}
        if flows:
            item["flows"] = flows
        for q in self.feed_subscribers:
            await q.put(item)

    def _scenario_from_world_state(self, zone_id: str, resource: str, amount: float) -> Scenario:
        """Builds a one-event allocation scenario from live world state --
        this is what bridges the tick-driven simulation to the decision
        layer's Scenario representation (Phase 2) without duplicating it."""
        zone = self.world.zones[zone_id]
        demands = [Demand(
            zone_id=zone_id, resource=resource, amount=amount,
            urgency=zone.urgency, vulnerability_index=zone.vulnerability_index,
        )]
        depot_stocks = [
            DepotStock(depot_id=d.id, resource=resource, stock=d.stock.get(resource, 0.0))
            for d in self.world.depots.values()
        ]
        travel_time = {}
        for d in self.world.depots.values():
            from .sim.graph import shortest_travel_time
            tt = shortest_travel_time(self.world.graph, d.id, zone_id)
            travel_time[(d.id, zone_id)] = tt if tt is not None else float("inf")
        return Scenario(demands=demands, depot_stocks=depot_stocks, travel_time=travel_time, graph=self.world.graph)

    def _run_allocation(self, scenario: Scenario):
        if self.active_strategy == "gnn_trained":
            strategy_fn = lambda s: allocate_with_policy(self.gnn_encoder, s)[0]
        else:
            strategy_fn = STRATEGIES[self.active_strategy]
        return apply_equity_floor(scenario, strategy_fn, floor=self.equity_floor)

    async def handle_demand_spike(self, zone_id: str, resource: str, amount: float) -> dict:
        t0 = time.perf_counter()
        zone = self.world.zones[zone_id]

        urgency = self.triage_model.score(
            pop=min(1.0, zone.population / 60000),
            unmet=min(1.0, zone.total_demand() / self._max_unmet_seen),
            injury=zone.urgency,  # proxy until a richer injury-mix signal exists
            vuln=zone.vulnerability_index,
        )
        zone.urgency = urgency

        scenario = self._scenario_from_world_state(zone_id, resource, amount)
        result = self._run_allocation(scenario)

        lines = []
        flows = []
        for alloc in result.allocations:
            if alloc.amount <= 0:
                continue
            depot = self.world.depots[alloc.depot_id]
            depot.stock[resource] = max(0.0, depot.stock.get(resource, 0.0) - alloc.amount)
            fund_amount = alloc.amount * UNIT_COST_INR.get(resource, 0)
            depot.budget_inr = max(0.0, depot.budget_inr - fund_amount)
            self.ledger.append(
                stakeholder_type="depot_to_zone", from_stakeholder=alloc.depot_id, to_stakeholder=zone_id,
                resource=resource, units=alloc.amount, fund_amount=fund_amount,
                description=f"{alloc.depot_id} -> {zone_id}: {alloc.amount:.1f} units {resource}",
            )
            lines.append(f"{alloc.amount:.0f} units from {alloc.depot_id} (₹{fund_amount:,.0f})")
            # structured, so the frontend's ArcLayer can draw a real depot->zone
            # flow arc instead of inferring it from the human-readable feed line
            flows.append({
                "depot_id": alloc.depot_id, "zone_id": zone_id,
                "resource": resource, "amount": alloc.amount, "fund_amount": fund_amount,
            })

        zone.demand[resource] = max(0.0, zone.demand.get(resource, 0.0) - sum(a.amount for a in result.allocations))

        elapsed_ms = (time.perf_counter() - t0) * 1000
        feed_line = (
            f"Zone {zone_id} demand spike (+{amount:.0f} units {resource}) -> "
            f"reallocated {', '.join(lines) if lines else 'nothing available'} -> "
            f"equity floor {self.equity_floor:.0%} maintained -> completed in {elapsed_ms:.0f}ms"
        )
        await self._publish_feed(feed_line, flows=flows)

        return {
            "zone_id": zone_id, "resource": resource, "amount": amount,
            "served_pct": result.served_demand_pct(), "strategy": result.strategy,
            "elapsed_ms": round(elapsed_ms, 2), "feed_line": feed_line, "flows": flows,
        }

    async def record_fund_transfers(self, transfers: list[dict]) -> None:
        for tr in transfers:
            self.ledger.append(
                stakeholder_type="donor_to_depot",
                from_stakeholder=tr["from_stakeholder"][1], to_stakeholder=tr["to_stakeholder"][1],
                resource=None, units=0, fund_amount=tr["fund_amount"], description=tr["description"],
            )
            await self._publish_feed(tr["description"])

    async def run(self) -> None:
        """Main loop: drains the world's event queue and routes DemandSpike
        events through the full decision pipeline. Other event types are
        acknowledged on the feed (they change world state directly at
        injection time); DemandSpike is the one that triggers a real
        allocation decision."""
        while True:
            evt = await self.world.events.get()
            if evt.kind == "DemandSpike":
                await self.handle_demand_spike(evt.zone_id, evt.resource, evt.amount)
            else:
                await self._publish_feed(f"{evt.kind} event: {evt.to_dict()}")
