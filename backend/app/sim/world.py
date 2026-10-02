"""The live disaster-simulation world: owns state, the tick loop, and the
event queue. One instance is shared by the REST injection routes, the
decision layer, and the WebSocket broadcaster — no duplicate world copies.
"""
from __future__ import annotations

import asyncio
import random
import time

from .entities import RESOURCE_TYPES, UNIT_COST_INR, make_default_world_entities
from .events import AmbulanceDown, DemandSpike, HospitalFull, RoadBlocked, SupplyLow, now
from .graph import build_road_graph

HOSPITAL_FULL_THRESHOLD = 0.9  # beds_used / bed_capacity


class World:
    def __init__(self) -> None:
        entities = make_default_world_entities()
        self.zones = entities["zones"]
        self.hospitals = entities["hospitals"]
        self.depots = entities["depots"]
        self.vehicles = entities["vehicles"]
        self.donors = entities["donors"]
        self.graph = build_road_graph()
        start_t = now()
        for donor in self.donors.values():
            donor.last_replenish_t = start_t  # don't fire immediately on startup
        self.events: asyncio.Queue = asyncio.Queue()
        self.tick_count = 0
        self.started_at = now()
        self._tick_task: asyncio.Task | None = None
        self.on_event_processed = None  # set by supervisor to subscribe, optional

    # ---------- injection functions (shared by REST routes and auto-escalation) ----------

    def inject_demand_spike(self, zone_id: str, resource: str, amount: float) -> DemandSpike:
        zone = self.zones[zone_id]
        zone.demand[resource] = zone.demand.get(resource, 0.0) + amount
        evt = DemandSpike(t=now(), zone_id=zone_id, resource=resource, amount=amount)
        self.events.put_nowait(evt)
        return evt

    def inject_road_block(self, u: str, v: str) -> RoadBlocked:
        if self.graph.has_edge(u, v):
            self.graph[u][v]["blocked"] = True
        if self.graph.has_edge(v, u):
            self.graph[v][u]["blocked"] = True
        evt = RoadBlocked(t=now(), u=u, v=v)
        self.events.put_nowait(evt)
        return evt

    def inject_hospital_capacity_drop(self, hospital_id: str, beds: int) -> HospitalFull | None:
        h = self.hospitals[hospital_id]
        h.beds_used = min(h.bed_capacity, h.beds_used + beds)
        if h.beds_used / h.bed_capacity >= HOSPITAL_FULL_THRESHOLD:
            evt = HospitalFull(t=now(), hospital_id=hospital_id)
            self.events.put_nowait(evt)
            return evt
        return None

    def inject_depot_depletion(self, depot_id: str, resource: str, amount: float | None = None) -> SupplyLow:
        d = self.depots[depot_id]
        if amount is None:
            amount = d.stock.get(resource, 0.0)  # wipe it out entirely
        d.stock[resource] = max(0.0, d.stock.get(resource, 0.0) - amount)
        evt = SupplyLow(t=now(), depot_id=depot_id, resource=resource)
        self.events.put_nowait(evt)
        return evt

    def inject_ambulance_down(self, vehicle_id: str) -> AmbulanceDown:
        evt = AmbulanceDown(t=now(), vehicle_id=vehicle_id)
        self.events.put_nowait(evt)
        return evt

    # ---------- donor fund replenishment (the funds/stakeholder fix) ----------

    def _run_donor_replenishment(self, t: float) -> list[dict]:
        """Returns a list of fund-transfer dicts (donor -> depot) for this tick."""
        transfers = []
        depot_ids = list(self.depots)
        for donor in self.donors.values():
            if t - donor.last_replenish_t >= donor.replenish_interval_s:
                donor.last_replenish_t = t
                target_depot = random.choice(depot_ids)
                self.depots[target_depot].budget_inr += donor.replenish_amount_inr
                transfers.append({
                    "from_stakeholder": ("donor", donor.id),
                    "to_stakeholder": ("depot", target_depot),
                    "fund_amount": donor.replenish_amount_inr,
                    "resource": None,
                    "units": 0,
                    "description": f"{donor.name} -> {target_depot}: fund replenishment",
                })
        return transfers

    # ---------- escalation (background disaster-story generator) ----------

    def _run_auto_escalation(self) -> None:
        """Lightweight scripted escalation so the world isn't static between
        manual Scenario Injector clicks. Runs rarely (low probability per tick)."""
        roll = random.random()
        if roll < 0.02:
            zone_id = random.choice(list(self.zones))
            resource = random.choice(RESOURCE_TYPES)
            self.inject_demand_spike(zone_id, resource, amount=random.uniform(5, 20))
        elif roll < 0.03:
            # natural decay/aging of unmet demand -> rising urgency, handled in _recompute_urgency

            pass

    def _recompute_urgency(self, dt: float) -> None:
        for zone in self.zones.values():
            unmet = zone.total_demand()
            urgency_from_unmet = min(1.0, unmet / 200.0)
            zone.urgency = 0.5 * urgency_from_unmet + 0.5 * zone.vulnerability_index
            for r in RESOURCE_TYPES:
                if zone.demand.get(r, 0) > 0:
                    zone.unmet_since[r] = zone.unmet_since.get(r, 0.0) + dt
                else:
                    zone.unmet_since[r] = 0.0

    def tick(self, dt: float = 1.0) -> list[dict]:
        """Advances the world by one step. Returns fund-transfer records
        produced this tick (for the ledger)."""
        self.tick_count += 1
        t = now()
        self._recompute_urgency(dt)
        self._run_auto_escalation()
        # hospitals slowly free up capacity as patients are discharged
        for h in self.hospitals.values():
            h.beds_used = max(0, h.beds_used - 1) if h.beds_used > 0 and self.tick_count % 5 == 0 else h.beds_used
        return self._run_donor_replenishment(t)

    def _coords(self, node_id: str) -> dict:
        node = self.graph.nodes[node_id]
        return {"lat": node["lat"], "lon": node["lon"]}

    def snapshot(self) -> dict:
        return {
            "tick": self.tick_count,
            "zones": [
                {
                    "id": z.id, "population": z.population, "demand": z.demand,
                    "urgency": round(z.urgency, 3), "vulnerability_index": z.vulnerability_index,
                    **self._coords(z.id),
                }
                for z in self.zones.values()
            ],
            "hospitals": [
                {
                    "id": h.id, "bed_capacity": h.bed_capacity, "beds_used": h.beds_used,
                    "icu_capacity": h.icu_capacity, "icu_used": h.icu_used,
                    **self._coords(h.id),
                }
                for h in self.hospitals.values()
            ],
            "depots": [
                {"id": d.id, "stock": d.stock, "budget_inr": d.budget_inr, **self._coords(d.id)}
                for d in self.depots.values()
            ],
            "roads": [
                {
                    "u": u, "v": v, "blocked": data["blocked"], "travel_time": data["travel_time"],
                    "u_coords": self._coords(u), "v_coords": self._coords(v),
                }
                for u, v, data in self.graph.edges(data=True)
            ],
        }


async def run_tick_loop(world: World, interval_s: float = 1.0, on_tick=None) -> None:
    """Background asyncio task. `on_tick(fund_transfers)` is called each tick
    so the ledger/supervisor can record donor fund movements."""
    while True:
        await asyncio.sleep(interval_s)
        transfers = world.tick(dt=interval_s)
        if on_tick is not None:
            await on_tick(transfers)
