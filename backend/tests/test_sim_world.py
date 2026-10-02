from app.sim.world import World


def test_demand_spike_updates_state_and_emits_event():
    w = World()
    before = w.zones["zone-1"].demand["water"]
    evt = w.inject_demand_spike("zone-1", "water", 25.0)
    assert w.zones["zone-1"].demand["water"] == before + 25.0
    assert evt.kind == "DemandSpike"
    queued = w.events.get_nowait()
    assert queued.zone_id == "zone-1" and queued.amount == 25.0


def test_road_block_sets_both_directions_and_emits_event():
    w = World()
    u, v = "depot-1", "zone-1"
    assert w.graph[u][v]["blocked"] is False
    evt = w.inject_road_block(u, v)
    assert w.graph[u][v]["blocked"] is True
    assert w.graph[v][u]["blocked"] is True
    assert evt.kind == "RoadBlocked"


def test_hospital_capacity_drop_emits_event_only_past_threshold():
    w = World()
    h = w.hospitals["hospital-1"]
    # fill to just under threshold -- should NOT emit
    evt = w.inject_hospital_capacity_drop("hospital-1", beds=int(h.bed_capacity * 0.5))
    assert evt is None
    assert w.events.empty()
    # push over threshold -- should emit
    evt2 = w.inject_hospital_capacity_drop("hospital-1", beds=int(h.bed_capacity * 0.5))
    assert evt2 is not None
    assert evt2.kind == "HospitalFull"
    assert h.beds_used / h.bed_capacity >= 0.9


def test_depot_depletion_reduces_stock_and_emits_event():
    w = World()
    before = w.depots["depot-1"].stock["medicine"]
    evt = w.inject_depot_depletion("depot-1", "medicine", amount=100)
    assert w.depots["depot-1"].stock["medicine"] == before - 100
    assert evt.kind == "SupplyLow"


def test_depot_depletion_full_wipe_when_no_amount_given():
    w = World()
    evt = w.inject_depot_depletion("depot-1", "water")
    assert w.depots["depot-1"].stock["water"] == 0
    assert evt.kind == "SupplyLow"


def test_ambulance_down_emits_event():
    w = World()
    evt = w.inject_ambulance_down("amb-1")
    assert evt.kind == "AmbulanceDown"
    assert evt.vehicle_id == "amb-1"


def test_tick_recomputes_urgency_from_unmet_demand():
    w = World()
    w.inject_demand_spike("zone-1", "water", 500.0)  # large unmet demand
    w.tick(dt=1.0)
    assert w.zones["zone-1"].urgency > 0.0


def test_tick_runs_donor_replenishment_after_interval():
    w = World()
    donor = w.donors["donor-1"]
    donor.replenish_interval_s = 0.0  # force immediate eligibility
    total_budget_before = sum(d.budget_inr for d in w.depots.values())
    transfers = w.tick(dt=1.0)
    total_budget_after = sum(d.budget_inr for d in w.depots.values())
    assert any(t["from_stakeholder"] == ("donor", "donor-1") for t in transfers)
    assert total_budget_after > total_budget_before


def test_multiple_injection_events_all_land_on_queue_in_order():
    w = World()
    w.inject_demand_spike("zone-1", "water", 10)
    w.inject_road_block("zone-1", "zone-3")
    w.inject_depot_depletion("depot-1", "food", 50)
    kinds = []
    while not w.events.empty():
        kinds.append(w.events.get_nowait().kind)
    assert kinds == ["DemandSpike", "RoadBlocked", "SupplyLow"]
