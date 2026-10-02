from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .decision.benchmark import run_benchmark
from .decision.np_policy import load_models
from .demo import DEMO_SCENARIOS
from .ledger.store import Ledger, canonical_payload
from .replay import ReplayBuffer
from .sim.world import World, run_tick_loop
from .supervisor import Supervisor

LEDGER_DB_PATH = os.environ.get("RAAHAT_LEDGER_DB", os.path.join(os.path.dirname(__file__), "..", "ledger.db"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    world = World()
    ledger = Ledger(db_path=LEDGER_DB_PATH)
    # Both trained models load from one exported .npz (scripts/export_weights.py
    # -- torch trains, this runtime runs pure NumPy; see np_policy.py for why).
    gnn_encoder, triage_model = load_models()
    supervisor = Supervisor(world, ledger, gnn_encoder, triage_model)

    app.state.world = world
    app.state.ledger = ledger
    app.state.supervisor = supervisor
    app.state.ws_clients = set()
    app.state.replay = ReplayBuffer(window_s=60.0)

    async def on_tick(fund_transfers):
        await supervisor.record_fund_transfers(fund_transfers)
        await _broadcast_state(app)

    async def _replay_recorder():
        # Decoupled from any specific WS client -- a single durable
        # subscription that records every feed item into the replay buffer
        # for as long as the app runs, independent of who's connected.
        q = app.state.supervisor.subscribe_feed()
        try:
            while True:
                item = await q.get()
                app.state.replay.append("feed", item)
        finally:
            app.state.supervisor.unsubscribe_feed(q)

    tick_task = asyncio.create_task(run_tick_loop(world, interval_s=1.0, on_tick=on_tick))
    supervisor_task = asyncio.create_task(supervisor.run())
    replay_task = asyncio.create_task(_replay_recorder())

    yield

    tick_task.cancel()
    supervisor_task.cancel()
    replay_task.cancel()
    ledger.close()


app = FastAPI(title="RAAHAT Disaster Relief Allocation API", lifespan=lifespan)

# Public, read/no-secret demo API -- no cookies/auth to protect, so an open
# CORS policy is a legitimate choice here (not a vulnerability to lock down),
# and it's what makes local dev (frontend :5173/5174/5175+ -> backend :8842)
# and the deployed cross-origin case both work without per-environment config.
# This was a REAL bug, not just styling: every POST/GET from the browser was
# failing CORS preflight (OPTIONS -> 405) before this, which silently broke
# every interactive control (Scenario Injector, Ledger verify, Equity floor,
# Strategy switch) even though curl-based testing never caught it, since curl
# doesn't perform CORS preflight.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _broadcast_state(app: FastAPI) -> None:
    snapshot = app.state.world.snapshot()
    app.state.replay.append("state", snapshot)
    if not app.state.ws_clients:
        return
    payload = {"type": "state", "data": snapshot}
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
        app.state.supervisor.unsubscribe_feed(feed_queue)


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
        {
            "id": r.id,
            "timestamp": r.timestamp,
            "prev_hash": r.prev_hash,
            "hash": r.hash,
            "canonical_payload": canonical_payload(r.prev_hash, r.timestamp, r.data),
            **r.data,
        }
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


# ---------- Scripted demo scenarios (Phase 6.1) ----------

@app.post("/demo/{scenario_name}")
async def run_demo_scenario(scenario_name: str):
    fn = DEMO_SCENARIOS.get(scenario_name)
    if fn is None:
        raise HTTPException(status_code=404, detail=f"unknown scenario '{scenario_name}', expected one of {list(DEMO_SCENARIOS)}")
    return await fn(app.state.world, app.state.supervisor)


# ---------- Demo-safety replay buffer (Phase 6.3) ----------

@app.get("/replay")
async def get_replay():
    return {"window_s": app.state.replay.window_s, "items": app.state.replay.recent()}


class _StripServerPrefix:
    """Vercel services routing delivers the public path unmodified, so the
    same-origin /server/* rewrite reaches FastAPI as /server/health etc.
    Strips the /server prefix (http + websocket scopes) so the API keeps its
    plain /health, /ws route paths while the browser calls /server/*."""

    def __init__(self, asgi_app):
        self.asgi_app = asgi_app

    def __getattr__(self, name):
        # delegate app.state etc. so the rest of the module is unchanged
        return getattr(self.asgi_app, name)

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket") and scope.get("path", "").startswith("/server/"):
            scope = dict(scope)
            scope["path"] = scope["path"][len("/server"):] or "/"
            scope["raw_path"] = scope["path"].encode()
        await self.asgi_app(scope, receive, send)


app = _StripServerPrefix(app)
