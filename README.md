# RAAHAT — Intelligent & Transparent Disaster Relief Allocation

> **Dynamic resource allocation for disaster response, with every resource
> and fund movement written to a tamper-evident ledger anyone can verify.**

| | |
|---|---|
| 🎯 Problem Statement | **EL-02 — Intelligent & Transparent Disaster Relief Resource Allocation** |
| 🏆 Hackathon | **ELEVATE 1.0**, DJ Sanghvi College of Engineering (with NSDC) |
| 🚀 Live Demo | *[deploy pending — see "Run it locally" below]* |
| 💻 Source | this repository |
| 🧪 Status | Backend fully functional and tested (simulation, trained allocation policy, hash-chained ledger, supervisor loop). Frontend: live map + full interactive control center. |

---

## 1. The Problem

When a disaster hits, relief resources — ambulances, medical supplies, hospital
beds, relief funds — are scarce, and conditions change by the minute: a road
gets blocked, a hospital fills up, a zone's demand spikes. Most dispatch
systems fall back on static rules (nearest hospital, first-come-first-served)
that don't adapt, and resource/fund distribution is rarely transparent enough
for donors, government bodies, or affected communities to independently
verify where things actually went.

**EL-02 asks for a platform that:**
1. Dynamically reallocates resources based on changing demand, infrastructure, transport constraints, and capacity — not static rules.
2. Models heterogeneous population urgency, vehicle capabilities, and hospital/depot capacity.
3. Tracks **resource *and* fund** movement across stakeholders with appropriate privacy controls, using blockchain or other tamper-evident technology.

## 2. Our Approach

RAAHAT is a live "command map" over a simulated disaster-affected region
(Mumbai). A **trained graph neural network policy** reasons over the live
road/zone/hospital/depot graph and reallocates resources as conditions
change, benchmarked live against classical dispatch algorithms (Greedy,
Hungarian, min-cost flow) so the improvement is measured evidence, not just
a claim. Every resource movement *and every fund transfer* — including a
simulated donor replenishing a depot's budget — is written to a **SHA-256
hash-chained ledger**, independently re-verifiable in the browser via
WebCrypto, not just by trusting a server response.

**Why a GNN, not a generic model:** the allocation problem is structurally a
graph — which zones are reachable, which roads are blocked or congested — a
flat-feature model can't reason about that structure the way a graph neural
network can.

**Why a hash-chain, not a full blockchain:** the brief explicitly allows
"blockchain *or* other tamper-evident technology." A hash-chain is fast,
genuinely verifiable live on stage with zero wallet/gas friction, and is
what production disaster-relief transparency platforms actually use at
their core — full smart-contract systems are reserved for real-money
settlement, which this prototype deliberately doesn't build, since the brief
never asked for it.

Full architecture rationale and PRD-to-module traceability: [`SYSTEM-ARCHITECTURE.md`](SYSTEM-ARCHITECTURE.md). Build plan: [`BUILD-PLAN.md`](BUILD-PLAN.md).

## 3. Evaluator Workflow — test this in 3 minutes

Once running (see §5), open the app. A welcome card explains what you're
looking at — dismiss it, or reopen anytime with the **?** button
bottom-right.

### Step 1 — Trigger a scenario (60s)
Open the **Scenario** tab (right side panel). Pick any zone and press
**Trigger demand spike**. Watch the zone marker shift toward amber/red on
the map, and the **Allocation Feed** (left panel) explain the reallocation
in plain language — which depot it pulled from, how many units, the ₹
value, and whether the equity floor held.

### Step 2 — Compare the trained policy against baselines (60s)
Open the **Controls** tab. Switch the **active allocation strategy**
between the trained GNN policy and the classical baselines (Greedy,
Hungarian, min-cost flow), then press **Run benchmark** — this runs all
four strategies against the same held-out scenarios and shows real
served-demand percentages side by side, not a single cherry-picked run.

### Step 3 — Verify the ledger yourself (60s)
Open the **Ledger** tab. Press **Verify chain** — the browser independently
re-hashes every record via WebCrypto and compares against the server's
chain, shown as two separate checks (server-side and browser-side). Then
press **Simulate tamper**, which corrupts the most recent record directly
in the database (a debug-only endpoint, not used anywhere else), and press
**Verify chain** again — watch it catch the exact corrupted record.

## 4. What's genuinely measured (not estimated)

From a real benchmark run on held-out scenarios (reproduce with
`GET /benchmark` once running locally):

| Strategy | Served demand | Equity violation |
|---|---|---|
| Greedy (nearest-available) | 100.0% | 0.0 |
| Hungarian (optimal assignment) | 94.5% | 0.045 |
| Min-cost flow | 98.7% | 0.0 |
| **Trained GNN policy** | **100.0%** | **0.0** |

Trained-policy inference latency: ~1.3–1.5ms (native PyTorch; see §6 for why
this isn't ONNX). Honest caveat: these scenarios have generous stock
relative to demand, so several strategies hit the 100% ceiling — the
policy's real edge over Greedy should widen under scarcity and road-block
scenarios, which is a priority for the next build phase (scripted demo
hardening), not yet exercised in this benchmark.

Hash-chain tamper detection: verified live — corrupting one record is
caught by both the server's `/ledger/verify` and the browser's independent
WebCrypto re-hash, at the exact record ID.

## 5. Architecture summary

```
Frontend (Vite + React + TS + deck.gl/MapLibre)
  -- WebSocket --> live world state + allocation feed
  -- REST --> scenario injection, equity floor, strategy switch, ledger, benchmark
       |
Backend (Python + FastAPI, single process)
  Simulation core -- road graph, zones/hospitals/depots/vehicles, donor funding
  Decision layer  -- trained GNN policy vs Greedy/Hungarian/min-cost-flow baselines
  Equity optimizer -- protected-demand floor, pre-allocation reservation pass
  Ledger          -- SHA-256 hash chain, resource + fund + stakeholder fields
  Supervisor loop -- wires events -> triage -> allocation -> equity -> ledger -> feed
```

## 6. Tech stack

`Python 3.12 / FastAPI` (simulation + orchestration, single process) ·
`PyTorch` (hand-rolled GNN message-passing encoder — not `torch_geometric`,
to avoid fragile wheel-matching when judges rerun this) · `scipy` / `networkx`
(Hungarian, min-cost-flow baselines) · `SQLite` (hash-chain ledger) ·
`React + TypeScript + deck.gl` (live 3D-tilted map) · `MapLibre GL` (basemap,
no API key required) · `Zustand` (frontend state) · `WebCrypto` (client-side
ledger verification).

Deliberate deviations from the original build plan, each for a concrete
reason: REINFORCE + learned baseline instead of full PPO-clip (the PPO-clip
formulation was mathematically unsound for this one-shot allocation
setting); no ONNX export (the encoder's control flow over variable-size
graphs doesn't trace to a static ONNX graph — benchmarked native PyTorch
inference instead, which is the latency number reported above).

## 7. Run it locally

**Backend:**
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu  # CPU-only, see requirements.txt
pip install -r requirements.txt
uvicorn app.main:app --port 8842
```

**Frontend** (separate terminal):
```bash
cd frontend
npm install
npm run dev
```
Open the URL Vite prints (defaults to `http://localhost:5173`, falls back to
the next free port). The frontend talks to the backend via `frontend/.env.local`
(`VITE_WS_URL=ws://localhost:8842/ws`).

**Tests:**
```bash
cd backend && source .venv/bin/activate && python -m pytest tests/ -v
```

## 8. Project structure

```
backend/app/
  sim/        road graph, entities (Zone/Hospital/Depot/Donor/Vehicle), tick loop, events
  decision/   baselines, GNN policy + training, triage scorer, equity optimizer, benchmark
  ledger/     SHA-256 hash-chain store
  supervisor.py   event -> triage -> allocation -> equity -> ledger -> feed pipeline
  main.py     FastAPI routes + WebSocket
frontend/src/
  components/   ReliefMap, Hud, ControlCenter (Scenario/Controls/Ledger tabs), IntroOverlay
  api.ts         REST client + client-side ledger re-hash
  store.ts       WebSocket state (Zustand)
SYSTEM-ARCHITECTURE.md   full architecture + PRD traceability
BUILD-PLAN.md            phase-by-phase build plan
PPT-CONTENT-PLAN.md      pitch deck content plan
```

## 9. References

- PPO-GNN approaches to humanitarian aid vehicle routing on road networks (precedent for a graph-structured allocation policy).
- Lexicographic min-cost-flow disaster optimizers with a configurable equity floor (precedent for the Equity Optimizer).
- Hash-chained/Merkle-rooted ledgers as the verifiable core of production disaster-relief transparency platforms, with full smart-contract systems reserved for real-money settlement (precedent for the ledger design choice).
- Classical OR baselines: Hungarian algorithm (Kuhn, 1955); min-cost-flow (standard network-flow literature).
