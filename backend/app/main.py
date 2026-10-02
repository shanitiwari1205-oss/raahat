from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from .decision.benchmark import run_benchmark
from .decision.gnn_policy import GNNEncoder
from .decision.triage import TriageScorer, train_triage_scorer
from .ledger.store import Ledger
from .sim.world import World, run_tick_loop
from .supervisor import Supervisor

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models_store")
GNN_WEIGHTS_PATH = os.path.join(MODEL_DIR, "gnn_policy.pt")
LEDGER_DB_PATH = os.environ.get("RAAHAT_LEDGER_DB", os.path.join(os.path.dirname(__file__), "..", "ledger.db"))


def _load_or_init_gnn() -> GNNEncoder:
    encoder = GNNEncoder()
    if os.path.exists(GNN_WEIGHTS_PATH):
        encoder.load_state_dict(torch.load(GNN_WEIGHTS_PATH, map_location="cpu"))
    encoder.eval()
    return encoder


def _init_triage() -> TriageScorer:
    # small/fast enough to train at startup rather than ship a checkpoint
    model, _ = train_triage_scorer(epochs=150)
    model.eval()
    return model


@asynccontextmanager
async def lifespan(app: FastAPI):
    world = World()
    ledger = Ledger(db_path=LEDGER_DB_PATH)
    gnn_encoder = _load_or_init_gnn()
    triage_model = _init_triage()
    supervisor = Supervisor(world, ledger, gnn_encoder, triage_model)

    app.state.world = world
    app.state.ledger = ledger
    app.state.supervisor = supervisor
    app.state.ws_clients = set()

    async def on_tick(fund_transfers):
        await supervisor.record_fund_transfers(fund_transfers)
        await _broadcast_state(app)

    tick_task = asyncio.create_task(run_tick_loop(world, interval_s=1.0, on_tick=on_tick))
    supervisor_task = asyncio.create_task(supervisor.run())

    yield

    tick_task.cancel()
    supervisor_task.cancel()
    ledger.close()


app = FastAPI(title="RAAHAT Disaster Relief Allocation API", lifespan=lifespan)


async def _broadcast_state(app: FastAPI) -> None:
    if not app.state.ws_clients:
        return
    payload = {"type": "state", "data": app.state.world.snapshot()}
    dead = []
    for ws in app.state.ws_clients:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        app.state.ws_clients.discard(ws)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    app.state.ws_clients.add(websocket)
    await websocket.send_json({"type": "state", "data": app.state.world.snapshot()})

    feed_queue = app.state.supervisor.subscribe_feed()

    async def feed_forwarder():
        while True:
            item = await feed_queue.get()
            await websocket.send_json({"type": "feed", "data": item})

    forwarder_task = asyncio.create_task(feed_forwarder())
    try:
        while True:
            await websocket.receive_text()  # client doesn't need to send anything; keeps connection open
    except WebSocketDisconnect:
        pass
    finally:
        forwarder_task.cancel()
        app.state.ws_clients.discard(websocket)


# ---------- Scenario Injector REST routes ----------

class DemandSpikeRequest(BaseModel):
    zone_id: str
    resource: str
    amount: float = Field(gt=0)


class RoadBlockRequest(BaseModel):
    u: str
    v: str


class HospitalCapacityRequest(BaseModel):
    hospital_id: str
    beds: int = Field(gt=0)


class DepotDepletionRequest(BaseModel):
    depot_id: str
    resource: str
    amount: float | None = Field(default=None, gt=0)


def _validated_zone(world: World, zone_id: str):
    if zone_id not in world.zones:
        raise HTTPException(status_code=404, detail=f"unknown zone_id '{zone_id}'")


def _validated_resource(resource: str):
    from .sim.entities import RESOURCE_TYPES
    if resource not in RESOURCE_TYPES:
        raise HTTPException(status_code=400, detail=f"unknown resource '{resource}', expected one of {RESOURCE_TYPES}")


@app.post("/scenario/demand-spike")
async def demand_spike(req: DemandSpikeRequest):
    _validated_zone(app.state.world, req.zone_id)
    _validated_resource(req.resource)
    evt = app.state.world.inject_demand_spike(req.zone_id, req.resource, req.amount)
    return {"ok": True, "event": evt.to_dict()}


@app.post("/scenario/road-block")
async def road_block(req: RoadBlockRequest):
    if not app.state.world.graph.has_edge(req.u, req.v):
        raise HTTPException(status_code=404, detail=f"no road edge {req.u}->{req.v}")
    evt = app.state.world.inject_road_block(req.u, req.v)
    return {"ok": True, "event": evt.to_dict()}


@app.post("/scenario/hospital-capacity-drop")
async def hospital_capacity_drop(req: HospitalCapacityRequest):
    if req.hospital_id not in app.state.world.hospitals:
        raise HTTPException(status_code=404, detail=f"unknown hospital_id '{req.hospital_id}'")
    evt = app.state.world.inject_hospital_capacity_drop(req.hospital_id, req.beds)
    return {"ok": True, "event": evt.to_dict() if evt else None}


@app.post("/scenario/depot-depletion")
async def depot_depletion(req: DepotDepletionRequest):
    if req.depot_id not in app.state.world.depots:
        raise HTTPException(status_code=404, detail=f"unknown depot_id '{req.depot_id}'")
    _validated_resource(req.resource)
    evt = app.state.world.inject_depot_depletion(req.depot_id, req.resource, req.amount)
    return {"ok": True, "event": evt.to_dict()}


@app.get("/scenario/state")
async def scenario_state():
    return app.state.world.snapshot()


# ---------- Equity floor + strategy controls ----------

class EquityFloorRequest(BaseModel):
    floor: float = Field(ge=0, le=1)


@app.post("/equity-floor")
async def set_equity_floor(req: EquityFloorRequest):
    app.state.supervisor.equity_floor = req.floor
    return {"ok": True, "equity_floor": req.floor}


class StrategyRequest(BaseModel):
    strategy: str


@app.post("/strategy")
async def set_strategy(req: StrategyRequest):
    valid = {"gnn_trained", "greedy", "hungarian", "min_cost_flow"}
    if req.strategy not in valid:
        raise HTTPException(status_code=400, detail=f"strategy must be one of {valid}")
    app.state.supervisor.active_strategy = req.strategy
    return {"ok": True, "active_strategy": req.strategy}


# ---------- Ledger ----------

@app.get("/ledger")
async def get_ledger(limit: int = 50, offset: int = 0):
    records = app.state.ledger.list_records(limit=limit, offset=offset)
    return [
        {"id": r.id, "timestamp": r.timestamp, "prev_hash": r.prev_hash, "hash": r.hash, **r.data}
        for r in records
    ]


@app.get("/ledger/verify")
async def verify_ledger():
    return app.state.ledger.verify()


@app.post("/ledger/_debug_corrupt/{record_id}")
async def debug_corrupt(record_id: int):
    """Debug-only endpoint for the tamper-detection demo (Phase 6.5) --
    deliberately corrupts a record so /ledger/verify can be shown catching it live."""
    app.state.ledger._debug_corrupt_record(record_id, new_units=999999)
    return {"ok": True, "corrupted_record_id": record_id}


# ---------- Benchmark ----------

@app.get("/benchmark")
async def benchmark():
    return run_benchmark(app.state.supervisor.gnn_encoder)
