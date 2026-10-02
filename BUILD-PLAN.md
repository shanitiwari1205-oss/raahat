# RAAHAT — Deployable Prototype Build Plan
### PS EL-02 (Disaster Relief) — lean architecture + phase-by-phase plan to ship a real, live-linked, map-based, ML-backed prototype before the PPT round

This supersedes §5 of `SYSTEM-ARCHITECTURE.md` for actual execution. Same modules as the full design — Simulation Core, Triage Scorer, Allocation Engine (PPO+GNN), Equity Optimizer, Hash-chained Ledger, Supervisor Loop, Relief Command Map — collapsed into fewer services so it builds fast and **deploys as one live public URL** you put in the PPT.

---

## 1. Why the stack collapses (not the architecture)

Same reasoning as the drone-swarm PS's build plan (if your brother is building that one, compare notes — the pattern is identical, just the simulation domain differs): a multi-service, multi-language design is the right **production** answer, but burns enormous build time on plumbing before anything is demoable. Collapse to the minimum that still proves every PRD claim live.

| Logical module | Production version | **Prototype version (what you actually build)** |
|---|---|---|
| Simulation core (road graph, zones, hospitals, depots) | Separate service | **Python, in-process, `asyncio` background tick task inside the same FastAPI app** |
| Triage Scorer | Separate model service | Small trained model, loaded in-process |
| Allocation Engine (PPO+GNN) | Separate inference service | PyTorch Geometric trained offline → ONNX → loaded in-process via `onnxruntime` |
| Equity Optimizer | Separate service | A plain Python function run after the Allocation Engine's output, same process |
| Ledger | Possibly its own service + real blockchain | **SQLite hash-chain table, in-process** — this alone already satisfies "transparent and traceable" |
| Supervisor Loop | Separate orchestrator service | `asyncio` task in the same FastAPI app consuming an in-memory event queue |
| WebSocket hub | Go + Redis | FastAPI's native WebSocket, in-memory client set (Redis only if you scale past one instance) |
| Frontend | React + deck.gl | **Same** — this is the one piece that stays exactly as designed, it's your visual centerpiece |

**Net result: one backend process (Python/FastAPI) + one frontend (Vite/React/deck.gl) = 2 things to build and deploy.**

---

## 2. Deployment target

**Vercel Services** — same pattern as the drone-swarm PS, confirmed against current Vercel reference templates (FastAPI + WebSocket + a Vite/React frontend, one project, one public URL, no CORS headaches since everything is same-origin):

```
vercel.json
{
  "services": {
    "web": { "root": "frontend/", "framework": "vite" },
    "api": { "root": "backend/", "entrypoint": "app.main:app", "framework": "fastapi" }
  },
  "rewrites": [
    { "source": "/server/(.*)", "destination": { "service": "api" } },
    { "source": "/(.*)", "destination": { "service": "web" } }
  ]
}
```

- Frontend connects to `wss://<your-project>.vercel.app/server/ws`.
- Map base layer: use **MapLibre GL** (free, no API key required) as deck.gl's base map — avoids needing a Mapbox token for the demo; swap to Mapbox later if you want nicer default basemap styling and don't mind an API key.
- SQLite persists per-deploy; swap to a free-tier Postgres (Neon/Supabase) later for cross-redeploy persistence — one connection-string change, not a rewrite.
- Env vars: none required for the core system (no LLM dependency unlike the drone-swarm PS — this PS's "intelligence" is the trained GNN policy + classical baselines, which is actually a cleaner, fully-deterministic demo with zero API-call risk on stage).

**Deploy the skeleton on Day 1** (empty map + 3 fake zones updating on a timer, live at a public URL) before any real simulation/ML exists — you always have a working link for the PPT, and every subsequent phase just ships to the same URL.

---

## 3. Phase-by-Phase Build Plan

### Phase 0 — Skeleton + Live Link
**0.1** — `backend/`: FastAPI app, `/health`, `/ws` route broadcasting 3 hardcoded zones + 1 hospital on a timer.
**0.2** — `frontend/`: Vite + React + TS + deck.gl over MapLibre, one map centered on a real city (pick your region — Mumbai is an easy, locally resonant choice given the college's location), 3 colored circle markers updating from `/ws` via a simple Zustand store.
**0.3** — `vercel.json` as above, `vercel --prod`. **Confirm the live URL works — markers visible on a real map, publicly reachable — before writing any real logic.** This URL goes straight into the PPT today.
**0.4** — Agree the 3 demo scenarios now (Phase 6 below).

### Phase 1 — Real Simulation Core
**1.1** — `backend/app/sim/graph.py`: road graph via `networkx` — a handful of zone/hospital/depot nodes connected by weighted edges (travel_time, capacity, blocked flag). Use real approximate coordinates for your chosen city/region so the map looks geographically honest, not abstract.
**1.2** — `backend/app/sim/entities.py`: `Zone` (population, demand per resource type, urgency score), `Hospital` (bed/ICU capacity), `Depot` (stock per resource type), `Ambulance`/`ReliefTruck` (capacity, speed, current assignment).
**1.3** — `asyncio` tick task (~every 500ms-1s is plenty — resource reallocation doesn't need a fast frame rate like a physics sim; state-change events matter more than motion smoothness here).
**1.4** — Event generator: scripted disaster escalation (aftershock → demand spike, flood → road edge blocked, mass-casualty → hospital capacity consumed) — reuse the same functions for both the auto-escalation and the Scenario Injector's manual triggers.
**1.5** — Fault/event injection functions as plain Python functions callable from REST routes: `inject_demand_spike(zone_id, amount)`, `inject_road_block(edge_id)`, `inject_hospital_capacity_drop(hospital_id, amount)`, `inject_depot_depletion(depot_id, resource)`.
**1.6** — Event queue (`asyncio.Queue`) the tick loop pushes typed events onto: `DemandSpike`, `HospitalFull`, `RoadBlocked`, `SupplyLow`, `AmbulanceDown`.
**Exit criteria:** `curl` the injection routes, confirm the right events land in logs, before touching ML or frontend.

### Phase 2 — Decision Layer (start this early — it's the long pole)
**2.1** — Build a lightweight `gymnasium` environment wrapping the Phase 1 world (headless, fast iteration).
**2.2** — **Baselines first**: Greedy nearest-available, `scipy.optimize.linear_sum_assignment` (Hungarian), and a min-cost-flow baseline via `networkx.min_cost_flow` or Google OR-Tools — these are your comparison evidence, implement them before the trained policy.
**2.3** — Train the Triage/Severity Scorer: small MLP or logistic regression over zone features (population, unmet-demand duration, injury-severity mix) → urgency score, trained on procedurally generated scenario data.
**2.4** — Train the PPO+GNN Allocation policy (`torch_geometric` + `stable-baselines3` or a custom PPO loop — keep the network small, CPU-trainable in minutes): reward = served-demand − travel-time penalty − equity-violation penalty. Log the training curve.
**2.5** — Export to ONNX, load with `onnxruntime` in the FastAPI backend, benchmark inference latency.
**2.6** — Equity Optimizer: a post-processing pass enforcing a configurable minimum protected-demand floor per zone before the trained policy's efficiency-maximizing allocation runs — operator-adjustable via a REST endpoint the frontend's Equity Floor slider calls.

### Phase 3 — Ledger
**3.1** — `backend/app/ledger/`: SQLite table `ledger_records(id, timestamp, prev_hash, data_json, hash)`. Every allocation/resource movement appends a record whose `hash = SHA256(prev_hash + canonical_json(data))`.
**3.2** — `GET /ledger` (paginated) and `GET /ledger/verify` (re-walks the whole chain server-side, returns pass/fail + any break point) — this is what the frontend's "Verify Chain" button calls, and it's real, not decorative.
**3.3 (optional stretch, only if ahead of schedule)** — Deploy a minimal Solidity contract (`anchorRoot(bytes32 root)`, nothing else — no token, no escrow) to a public testnet (Polygon Amoy — free faucet, fast), periodically compute a Merkle root over recent ledger records and anchor it via a simple `web3.py` call. This is a small, safe, demoable amount of real blockchain — resist the urge to build more than this one function, it adds risk without adding PRD coverage.

### Phase 4 — Supervisor Loop (wires Phase 1+2+3 together)
**4.1** — `asyncio` task consuming the Phase 1.6 event queue: routes each event to Triage Scorer → Allocation Engine → Equity Optimizer, in sequence.
**4.2** — Every resulting allocation decision: (a) appends a Ledger record (Phase 3), (b) pushes a human-readable entry onto the WebSocket broadcast for the Allocation Feed — build these together.

### Phase 5 — Relief Command Map (frontend)
**5.1** — Replace Phase 0's hardcoded payload with real WebSocket state: zone fulfillment %/urgency (color-coded), hospital capacity gauges, depot stock levels.
**5.2** — `ArcLayer`: animated arcs for active resource flows (depot→zone), colored/thickness-scaled by resource amount.
**5.3** — `HexagonLayer` or `HeatmapLayer`: live severity/urgency heatmap over the map.
**5.4** — Roads rendered dim/red when `blocked`.
**5.5** — **Scenario Injector panel** — buttons wired to Phase 1.5's REST routes; put a few directly as map interactions too (e.g. click a road to block it) for extra "wow."
**5.6** — **Allocation Feed** — scrolling live log from the WebSocket decision stream, human-readable sentence templates.
**5.7** — **Ledger Explorer** — table of recent records + a "Verify Chain" button calling `/ledger/verify`, and ideally a client-side re-hash too so it's visibly not just trusting the server's word.
**5.8** — **Equity Floor slider** — calls the Phase 2.6 endpoint, visibly changes the next allocation pass's distribution.

### Phase 6 — Demo Scenarios, Benchmarking, Hardening (do not skip)
**6.1** — Script and rehearse 3 scenarios, ~60-90s each:
  - *A — Demand spike*: trigger a sudden demand spike in one zone, watch the Allocation Engine reroute supply from nearby depots in real time, Allocation Feed explains why, arc animates on the map.
  - *B — Road block + reroute*: block a key road, watch the policy find an alternate route/depot, with the blocked road visibly shown and the arc visibly rerouting.
  - *C — Hospital capacity cascade*: push a hospital near capacity, watch ambulance routing shift to an alternate hospital, and show the Equity Floor slider's effect by toggling it on/off on the same scenario — a clean before/after that's easy for a judge to see.
**6.2** — **Baseline comparison run**: same scenario, Greedy vs Hungarian vs Min-Cost-Flow vs Trained GNN policy, capture served-demand %/time numbers — hard evidence for Innovation/Feasibility slides.
**6.3** — **Demo-safety replay buffer**: rolling in-memory list of the last ~60s of broadcasts, a `/replay` mode the frontend can switch to if live WiFi drops.
**6.4** — Stress test: scale to 10-15 zones/entities, confirm the map stays smooth, screenshot for Feasibility.
**6.5** — Ledger verify demo: deliberately show a tampered record failing verification (e.g. a debug-only endpoint that corrupts one row) to prove the tamper-evidence claim isn't just assumed — this is a genuinely strong, concrete "prove it" moment for judges.
**6.6** — Final timed rehearsal, someone else operating the Scenario Injector cold.

---

## 4. What to capture for the PPT

| Metric | Captured in | Slide |
|---|---|---|
| **Live demo URL** | Phase 0.3 | Title / Feasibility |
| Allocator inference latency (ms) | Phase 2.5 | Feasibility |
| Served-demand % — Greedy vs Hungarian vs Min-Cost-Flow vs Trained GNN | Phase 6.2 | Innovation / Feasibility |
| Equity floor ON vs OFF — distribution fairness comparison | Phase 2.6 / 6.1-C | Innovation |
| Ledger verify: tampered record correctly rejected | Phase 6.5 | Feasibility / Innovation |
| Event→reallocation visible latency on stage | Phase 6.1 | Technical Approach |
| Training reward curve | Phase 2.4 | Technical Approach |

---

## 5. One-line answer if a judge asks "where's the actual blockchain?"

> "The PRD explicitly says blockchain *or* other tamper-evident technology — we built a hash-chained ledger as the core because it's fast, genuinely verifiable live on stage with zero wallet/gas friction, and matches what production disaster-relief ledger projects actually use underneath. We also anchor the Merkle root to a public testnet smart contract [if you built 3.3] so there's a real on-chain transaction too — but we didn't build a token/escrow system the brief never asked for, because that adds risk without adding coverage."
