<div align="center">

# 🚨 RAAHAT
### Intelligent & Transparent Disaster Relief Resource Allocation

**When a disaster hits, RAAHAT reallocates scarce ambulances, medical supplies, hospital beds, and relief funds in real time — and writes every single movement to a tamper-evident ledger anyone can independently verify, live, in the browser.**

[![Live Demo](https://img.shields.io/badge/🔴_LIVE_DEMO-pending_deploy-lightgrey?style=for-the-badge)](#)

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://python.org)
[![PyTorch](https://img.shields.io/badge/PyTorch-GNN_policy-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org)
[![React](https://img.shields.io/badge/React_+_deck.gl-live_map-61DAFB?logo=react&logoColor=white)](https://deck.gl)
[![Tests](https://img.shields.io/badge/backend_tests-19%2F19_passing-brightgreen)](backend/tests/)
[![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)

</div>

---

## 📋 At a glance

| | |
|---|---|
| **Problem Statement** | **EL-02 — Intelligent & Transparent Disaster Relief Resource Allocation** |
| **Hackathon** | ELEVATE 1.0, DJ Sanghvi College of Engineering (with NSDC) |
| **Live demo** | **[raahat.vercel.app](https://elevate-disaster-relief.vercel.app)** — full app, deployed (Vercel) |
| **Source** | this repository |
| **Status** | Full backend (simulation, trained allocation policy vs. 3 classical baselines, hash-chained ledger, supervisor loop) + full interactive frontend (live map, 3 scripted demo scenarios, scenario injector, ledger explorer with independent client-side verification). 22/22 backend tests passing. |

---

## 1. The problem we were asked to solve

> Design an intelligent disaster-response platform that dynamically allocates scarce emergency resources based on changing demand, infrastructure conditions, transportation constraints, and available capacity, while providing transparent and traceable records of **resource and fund** distribution. Model affected populations with different urgency levels, ambulances/relief resources with varying capabilities, hospitals with changing capacities, disrupted road networks, and limited medical supplies/funds — reallocating dynamically rather than via static rules (nearest-hospital/first-come). Track allocation and movement of relief resources/funds **across stakeholders** with appropriate privacy controls; blockchain or other tamper-evident technologies may be explored. — *EL-02, paraphrased from the official brief*

Most relief-dispatch tooling falls back on static rules — nearest hospital, first-come-first-served — that don't adapt as roads close or supplies run out, and resource/fund distribution is rarely verifiable by anyone outside the system operator.

## 2. Our idea, in 20 seconds

RAAHAT is a live "command map" over a simulated disaster-affected region (Mumbai). A **trained graph neural network policy** reasons over the live road/zone/hospital/depot graph and reallocates ambulances, relief trucks, and supplies as conditions change — benchmarked live against three classical dispatch algorithms so the improvement is measured evidence, not a claim. An **equity floor** guarantees vulnerable zones a protected minimum before the efficiency-maximizing pass runs, so fairness is a tunable, demoable control, not an afterthought. Every resource movement *and every fund transfer* — including a simulated donor replenishing a depot's budget — is written to a **SHA-256 hash-chained ledger**, independently re-verifiable in the browser via WebCrypto, not just by trusting a server response.

## 3. ✅ Every PS requirement — addressed, and where to check it

| # | PS asked for | What we built | Where to verify |
|---|---|---|---|
| 1 | Dynamic allocation under **changing demand, infrastructure, transport constraints, capacity** | Zone demand/urgency that rises in real time, a weighted road graph with blockable edges, hospital capacity that depletes/frees, depot stock that depletes — all driving the same allocation decision | `backend/app/sim/`, triggerable live via the **Scenario** tab |
| 2 | Populations with **different urgency levels** | Trained triage/severity scorer (MLP), not a hardcoded priority list | `backend/app/decision/triage.py` |
| 3 | Resources/ambulances with **varying capabilities**, hospitals with **changing capacity** | Heterogeneous `Ambulance`/`ReliefTruck` entities, `Hospital` with bed/ICU capacity | `backend/app/sim/entities.py` |
| 4 | **Disrupted road networks** | `networkx` weighted directed graph, edges carry `blocked` state — click a road on the live map to block it | `backend/app/sim/graph.py`, map interaction |
| 5 | **Limited medical supplies** | Finite per-resource-type depot stock, consumed on allocation | `backend/app/sim/entities.py` (`Depot`) |
| 6 | **Limited funds** | *(originally under-specified in most team's readings of the brief — see below)* `Depot.budget`, a `Donor`/`FundingBody` entity that periodically injects relief funds | `backend/app/sim/entities.py` (`Donor`) |
| 7 | Reallocate dynamically, **not static nearest-hospital/first-come rules** | Trained GNN policy, benchmarked live against Greedy/Hungarian/min-cost-flow | `backend/app/decision/`, **Controls** tab's live benchmark |
| 8 | Transparent, traceable **resource distribution** | SHA-256 hash-chain ledger, append-only | `backend/app/ledger/`, **Ledger** tab |
| 9 | Transparent, traceable **fund distribution across stakeholders** | Every ledger record carries a `fund_amount` (₹) and `stakeholder_type` (donor / depot / hospital / zone) field, not just resource units — a donor→depot fund injection is its own loggable, verifiable record, same chain | **Ledger** tab shows both unit and ₹ columns per record |
| 10 | **Appropriate privacy controls** | Only zone-level/aggregate data is ever written to the ledger — no individual beneficiary PII, ever modeled or stored | Ledger Explorer's "Public view: zone-level only" badge |
| 11 | Blockchain **or** other tamper-evident technology "may be explored" | SHA-256 hash-chain core (fast, zero wallet/gas friction, genuinely verifiable live on stage) — the brief explicitly allows this as an alternative to full blockchain, and we deliberately didn't bolt on an unaudited smart-contract system the brief never required | See §6 for the reasoning in full |
| 12 | Demonstrate **allocation changing live** as conditions change | Scenario Injector (manual triggers) + 3 scripted demo scenarios that escalate and resolve automatically | **Demo** / **Scenario** tabs |
| 13 | Visualization of allocation/state/outcomes | deck.gl live map: `ArcLayer` animated resource-flow arcs, `HeatmapLayer` urgency glow, color-coded zones/hospitals/depots | the map itself |
| 14 | Demonstrate **transparent tracking and verification** | "Verify chain" (server) + an independent browser-side WebCrypto re-hash, plus a "Simulate tamper" button that corrupts a real record so you can watch both checks catch it | **Ledger** tab |

**The one requirement most easy to under-read**: the brief says "resource **and fund** distribution" and "limited medical supplies**/funds**" twice — deliberately paired with resources, not synonymous with them. We built this as a first-class part of the system (the `Donor` entity, the `fund_amount`/`stakeholder_type` ledger fields) specifically because it's the clause a surface reading of the brief misses.

## 4. Evaluator workflow — test this in 3 minutes, no setup beyond §8

Once the app is open (live link or local — see §8), a welcome card explains what you're looking at; dismiss it or reopen anytime with the **?** button bottom-right.

### Step 1 — Run a scripted scenario (60s)
Open the **Demo** tab (default). Press **Run scenario** on any of the three cards — *Demand Spike*, *Road Block + Reroute*, *Hospital Capacity Cascade*. Watch the map react live: colored zone markers shift, an animated arc flows from the depot that's supplying relief, and the **Allocation Feed** (left panel) explains the decision in plain language — which depot, how many units, the ₹ value, whether the equity floor held. The Hospital Capacity Cascade scenario also toggles the equity floor on/off on the same conditions so you can see the fairness trade-off directly.

### Step 2 — Compare the trained policy against baselines, live (60s)
Open the **Controls** tab. Switch the active allocation strategy between the trained GNN policy and the classical baselines (Greedy, Hungarian, min-cost flow), then press **Run benchmark** — this runs all four strategies against the same held-out scenarios and returns real served-demand percentages side by side, computed fresh, not a precomputed/cherry-picked number (see §5 for what these numbers actually are).

### Step 3 — Verify the ledger yourself (60s)
Open the **Ledger** tab. Press **Verify chain** — the browser independently re-hashes every record via WebCrypto against the exact canonical bytes the server hashed, shown as two separate pass/fail checks (server-side and browser-side), not one check trusting the other. Then press **Simulate tamper** (a debug-only endpoint that corrupts the most recent record directly in the database — nothing else uses it) and press **Verify chain** again: watch both checks independently catch the exact corrupted record ID.

## 5. What's genuinely measured — not estimated

Every number below is from a real run against the live running system (full methodology and the honest engineering story behind them: [`docs/benchmark-results.md`](docs/benchmark-results.md)). Reproduce any of it yourself with `GET /benchmark` once running (§8).

#### Allocation quality — generous-stock regime (20 held-out scenarios)
| Strategy | Served demand | Equity violation |
|---|---|---|
| Greedy (nearest-available) | 100.0% | 0.000 |
| Hungarian (optimal assignment) | 94.5% | 0.045 |
| Min-cost flow | 98.7% | 0.000 |
| **Trained GNN policy** | **100.0%** | **0.000** |

Under generous supply most strategies saturate near the ceiling — this regime mainly proves every strategy is *correct*, not which is *better*. That's why we also ran a harder one:

#### Allocation quality — real scarcity regime (stock cut 70%, demand +60%, 2 roads blocked)
| Strategy | Served demand | Equity violation |
|---|---|---|
| Greedy (nearest-available) | 82.4% | 0.064 |
| Hungarian (optimal assignment) | 70.2% | 0.045 |
| Min-cost flow | 81.5% | 0.025 |
| **Trained GNN policy** | **82.4%** | **0.064** |

**Honest framing, not a cherry-pick:** an earlier version of the trained policy actually *lost* to every baseline here (65.8% served) — root-caused to a real, documented set of bugs (stale node embeddings, a missing feasibility mask, no multi-depot splitting, and a train/test distribution mismatch where the policy had literally never seen scarcity during training). Fixed and retrained; the full before/after story, verified reproducible across three independent training seeds, is kept in [`docs/benchmark-results.md`](docs/benchmark-results.md) rather than hidden. The fair claim is **"matches the best hand-tuned classical heuristic using one general learned policy, not hardcoded nearest-first logic"** — not "beats every baseline," and we're not claiming otherwise.

#### Equity floor — real before/after, same scarce starting condition
| Equity floor | Served | What happened |
|---|---|---|
| OFF | 20% (10/50 units) | Main strategy allocated conservatively from the nearer depot only |
| **ON (30%)** | **30% (15/50 units)** | Floor reserved its guarantee up front, pulling from **both** depots |

This is the clearest, most unambiguous differentiator in the system — a value judgment made visible and operator-controlled instead of hidden inside a black-box score.

#### Latency, throughput, tamper-detection
| Metric | Result |
|---|---|
| GNN inference, demo scale (5 zones) | 2.4ms mean |
| GNN inference, stress scale (15 zones) | 5.5ms mean |
| Simulation tick loop (300 real ticks) | 0.004ms mean — never falls behind a 1s interval |
| Full event→allocation→ledger→feed pipeline, 20 back-to-back events | 677.8 events/sec, 1.47ms mean/event |
| Ledger tamper detection | 100% — caught at the exact corrupted record ID, server- and client-side, every time |

## 6. One-line answer if a judge asks "where's the actual blockchain?"

> The brief explicitly says blockchain *or* other tamper-evident technology. We built a SHA-256 hash-chain as the core because it's fast, genuinely verifiable live on stage with zero wallet/gas friction, and matches what production disaster-relief transparency platforms actually use underneath — full smart-contract/token systems are reserved for real-money settlement, which we deliberately didn't bolt on, because the brief never asked for it and an unaudited contract built in a hackathon window is a weaker, not stronger, answer.

## 7. Architecture

```
Frontend (Vite + React + TypeScript + deck.gl / MapLibre, neo-brutalist UI)
  -- WebSocket --> live world state + allocation feed + resource-flow data
  -- REST --> scenario injection, scripted demos, equity floor, strategy switch, ledger, benchmark, replay
       |
Backend (Python 3.12 + FastAPI, single process)
  Simulation core   -- road graph, zones/hospitals/depots/vehicles, donor funding, event generator
  Decision layer    -- trained GNN policy vs. Greedy / Hungarian / min-cost-flow baselines
  Equity optimizer  -- protected-demand floor, pre-allocation reservation pass
  Ledger            -- SHA-256 hash chain, resource + fund + stakeholder fields
  Supervisor loop   -- event -> triage -> allocation -> equity -> ledger -> feed, all wired together
```

Full architecture rationale and PRD-to-module traceability: [`SYSTEM-ARCHITECTURE.md`](SYSTEM-ARCHITECTURE.md). Phase-by-phase build plan: [`BUILD-PLAN.md`](BUILD-PLAN.md). Pitch deck content plan: [`PPT-CONTENT-PLAN.md`](PPT-CONTENT-PLAN.md).

**Nothing here is a mock or a stub:** the GNN is a real message-passing policy trained via REINFORCE (actor-critic) on this exact simulation in PyTorch (hand-rolled, not `torch_geometric`, specifically so a judge can retrain it without fragile wheel-matching); the trained weights ship as a 20 KB `.npz` and the live server runs them through a numerically verified pure-NumPy twin of the torch forward pass (`np_policy.py` — parity-tested to ~1e-7, torch kept out of the deployed runtime to fit Vercel's 500 MB function limit); the baselines are genuine `scipy`/`networkx` implementations, not fakes to lose to on purpose; the ledger is a real SHA-256 chain with real tamper-detection, not a decorative table.

## 8. Run it — live or local

**Live demo:** **[https://elevate-disaster-relief.vercel.app](https://elevate-disaster-relief.vercel.app)** — deployed on Vercel as one project with two same-origin services (`web` frontend + `api` FastAPI behind `/server/*`), no setup needed. The three scripted demo scenarios, the Scenario Injector, the live benchmark, and the Ledger Explorer all work against the live deployment.

**Run it yourself:**
```bash
git clone <this-repo-url>
cd raahat

# backend — runtime needs only requirements.txt (inference is pure NumPy)
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8842

# frontend (separate terminal)
cd frontend
npm install
npm run dev   # open the URL Vite prints
```
Training or re-exporting the models additionally needs `pip install -r requirements-train.txt` (torch) and `python -m scripts.export_weights` from `backend/`.
The frontend talks to the backend via `frontend/.env.local` (`VITE_WS_URL=ws://localhost:8842/ws`) in local dev; in production it defaults to the same-origin `/server/ws` path that `vercel.json`'s rewrite rules provide, so no env var is needed at deploy time.

**Reproduce every number in this README:**
```bash
cd backend && source .venv/bin/activate
python -m pytest tests/ -v              # 22 automated tests (3 verify torch↔NumPy parity when torch is installed)
curl http://localhost:8842/server/benchmark    # allocation strategy comparison, live
python -m scripts.stress_test           # latency/throughput numbers
```

## 9. Project structure

```
backend/app/
  sim/        road graph, entities (Zone/Hospital/Depot/Donor/Vehicle), tick loop, events
  decision/   baselines, GNN policy + training, triage scorer, equity optimizer, benchmark
  ledger/     SHA-256 hash-chain store
  supervisor.py   event -> triage -> allocation -> equity -> ledger -> feed pipeline
  main.py     FastAPI routes + WebSocket
frontend/src/
  components/   ReliefMap (ArcLayer/HeatmapLayer/click-to-block), ControlCenter
                (Demo/Scenario/Controls/Ledger tabs), Hud, IntroOverlay
  api.ts         REST client + client-side ledger re-hash (WebCrypto)
  store.ts       WebSocket state (Zustand)
docs/benchmark-results.md   every real number in this README, with full methodology
SYSTEM-ARCHITECTURE.md      full architecture + PRD traceability
BUILD-PLAN.md               phase-by-phase build plan
PPT-CONTENT-PLAN.md         pitch deck content plan, filled with real numbers
```

## 10. Tech stack

`Python 3.12` / `FastAPI` (simulation + orchestration, single process) · `PyTorch` (hand-rolled GNN message-passing encoder, training only) + `NumPy` (numerically verified inference twin that actually serves traffic — keeps the deploy under Vercel's 500 MB cap) · `scipy` / `networkx` (Hungarian, min-cost-flow baselines) · `SQLite` (hash-chain ledger) · `React` + `TypeScript` + `deck.gl` (live 3D-tilted map) · `MapLibre GL` (basemap, no API key required) · `Zustand` (frontend state) · `WebCrypto` (client-side ledger verification) · deployed on `Vercel` (one project, two same-origin services, native WebSocket on the Python runtime).

## 11. References

- PPO-GNN approaches to humanitarian aid vehicle routing on road networks — precedent for a graph-structured allocation policy.
- Lexicographic min-cost-flow disaster optimizers with a configurable equity floor — precedent for the Equity Optimizer.
- Production disaster-relief transparency platforms that use hash-chained/Merkle-rooted ledgers at their verifiable core, reserving full smart-contract systems for real-money settlement — precedent for the ledger design choice (we deliberately stay at the lighter end of this spectrum for a hackathon-scoped prototype, rather than overclaiming a full on-chain system we didn't build).
- Classical OR baselines: Hungarian algorithm (Kuhn, 1955); min-cost-flow (standard network-flow literature).
