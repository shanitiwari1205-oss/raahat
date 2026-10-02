# RAAHAT — PPT Content Plan
### PS EL-02 (Disaster Relief) — mapped exactly to the ELEVATE 1.0 template (9 slides in template → 8 usable, Instructions slide deleted before submission)

Same template as the drone-swarm PS's plan — if your brother is building EL-05, your two decks will look structurally consistent (good for the team/college's overall submission quality) without being identical content.

Judging rubric from the template's Instructions slide: **Problem understanding & solution, Technical Depth & Scaling, Originality & Differentiation, Quality of research/prototype/presentation.**

General visual rules (same as EL-05's plan, keep the template's own look intact):
- Keep the template's header bar, background, and airplane motif exactly as-is.
- One clear visual per slide — never bullets-only.
- Use the template's amber/gold accent for callouts/highlights.
- Large bold number callouts for metrics, not buried in paragraphs.

---

## Slide 1 — Title
**Fields to fill:**
- Team Name: *[your team name]*
- PS ID: **EL-02**
- PS Name: **Intelligent & Transparent Disaster Relief Resource Allocation**
- Abstract (~40-50 words):
  > "RAAHAT is a disaster-response platform that dynamically reallocates scarce emergency resources — ambulances, medical supplies, hospital capacity — across a live road network as conditions change, using a trained graph-neural-network policy benchmarked against classical dispatch algorithms, with every resource movement recorded on a tamper-evident ledger anyone can verify."
- **If Phase 0 of `BUILD-PLAN.md` is deployed by submission time, add the live link directly under the abstract** — e.g. *"Live prototype: raahat-relief.vercel.app"* — this is a genuine differentiator most teams won't have.

---

## Slide 2 — Proposed Solution
Sub-sections: *Proposed Solution and Core Concept / Key Functionalities and Detailed Approach / Problem-Solution Alignment*

**Core Concept (2-3 sentences):**
> A live "command map" sitting above a disaster-affected region's road network, hospitals, and supply depots. As conditions change — a road gets blocked, a hospital fills up, a zone's demand spikes — a trained allocation policy reroutes ambulances, relief trucks, and supplies in real time, while every movement of resources and funds is written to a transparent, independently-verifiable ledger.

**Key Functionalities (bullets, bold the verb):**
- **Reallocates** resources dynamically across a live road/hospital/depot graph, not static nearest-hospital rules
- **Scores urgency** per zone with a trained triage model, not a hardcoded priority list
- **Enforces fairness** via a configurable equity floor so efficiency never starves small/remote zones
- **Records every movement** on a tamper-evident ledger, independently verifiable live

**Problem-Solution Alignment (comparison table):**
| PRD asks for | RAAHAT delivers |
|---|---|
| Dynamic allocation under changing demand/infrastructure/capacity | GNN-based trained policy reasons over the live road graph, not static rules |
| Transparent, traceable resource/fund distribution with privacy controls | Hash-chained ledger, zone-level only (no beneficiary PII), verifiable on demand |
| Blockchain or tamper-evident tech "may be explored" | Hash-chain core + optional real testnet smart-contract anchor |

**Visual:** 3-icon row in colored circles — map-pin ("Models the disaster"), network/graph icon ("Reallocates live"), chain-link icon ("Tracks transparently").

---

## Slide 3 — Technical Approach
Sub-sections: *System Architecture and Overall Workflow / Technologies, Frameworks and Models / Implementation and System Components*

**Layout: Gemini-generated architecture diagram dominant (top ~65%), tech badge row underneath.**

**System Architecture and Overall Workflow:**
- Insert the Gemini-generated diagram from `SYSTEM-ARCHITECTURE.md` §4.
- Caption: *"5-layer pipeline: Relief Command Map → Supervisor/Ledger → ML Decision Layer (Triage Scorer, GNN Allocation Policy, Equity Optimizer) → Disaster Scenario Engine → Entity Fleet (ambulances, trucks, hospitals, depots)."*

**Technologies, Frameworks and Models (badge row):**
`Python / FastAPI (simulation + orchestration)` · `PyTorch Geometric (GNN policy)` · `ONNX Runtime (fast inference)` · `React + deck.gl (live 3D-tilted map)` · `MapLibre GL (basemap)` · `SQLite hash-chain (ledger)` · `OR-Tools / SciPy (baseline algorithms)`

**Implementation and System Components (3 lines, with real numbers once captured):**
- Allocation is modeled as a graph problem — zones/hospitals/depots as nodes, roads as edges — so a GNN policy reasons about network structure, not just flat features
- Trained policy benchmarked live against Greedy, Hungarian-optimal, and min-cost-flow baselines — [X]% improvement once you have Phase 6.2's number
- Every allocation writes a hash-chained ledger record; chain integrity is re-verifiable client-side in milliseconds

**Callout box:** *"Why a GNN and not a generic model: the allocation problem is structurally a graph — which zones are reachable, which roads are congested — a plain model over flat features can't reason about that structure the way a graph neural network can."*

---

## Slide 4 — Innovation and Uniqueness
Sub-sections: *Innovative Approach and Core Differentiators / Unique Features and Functionalities / Comparison with Existing Approaches*

**Core Differentiators (3 bullets):**
- GNN-based policy that reasons over the live road-network graph, not a flat-feature model pretending structure doesn't matter
- An explicit, operator-adjustable **equity floor** — efficiency and fairness are both first-class, tunable, and demoable live (toggle it on/off on the same scenario and watch the distribution change)
- Transparency that's actually verifiable on stage — a "Verify Chain" button, and a deliberate tamper demo showing a corrupted record getting rejected — not a claim, a proof

**Comparison table (pull from `SYSTEM-ARCHITECTURE.md` §7):**
Nearest-hospital/static dispatch | Pure OR-only tools | Blockchain-heavy relief-fund platforms | Dashboard-only trackers | **RAAHAT**

**Visual:** the comparison table is the visual — clean grid, bold the RAAHAT column, generous cell padding.

---

## Slide 5 — Feasibility and Viability
Sub-sections: *Technical and Operational Feasibility / Scalability, Deployment and Resource Requirements / Challenges, Risks and Sustainability*

**Stat callouts (large numbers, fill once captured per `BUILD-PLAN.md` §4):**
- `<Xms>` — Allocator inference latency
- `<1s>` — event-to-reallocation visible latency on stage
- `[X]%` — served-demand improvement, trained GNN policy vs. best classical baseline
- `100%` — ledger tamper-detection rate (if you ran the Phase 6.5 corrupted-record demo)

**Technical and Operational Feasibility:**
> Every component is a proven pattern applied to this specific problem: GNN-based routing policies are directly precedented in humanitarian/logistics routing literature, classical OR baselines (Hungarian, min-cost-flow) are industry-standard dispatch tools, and hash-chained ledgers are the actual core of production disaster-relief transparency platforms — not a novel unproven combination.

**Scalability, Deployment and Resource Requirements:**
- Stateless-per-scenario backend — horizontally scalable behind a standard load balancer
- Road graph is swappable for real OpenStreetMap data and real disaster-event feeds (USGS/GDACS) without touching the Allocation Engine or frontend contract
- Deployed today as containers / a single Vercel project — same images scale to Kubernetes for a real deployment

**Challenges, Risks and Sustainability (honest, judges respect this):**
- Sim-to-real gap once real road/traffic data replaces the synthetic graph — mitigated by the graph-abstraction boundary (same interface, swappable data source)
- Equity floor vs. efficiency is a genuine value judgment, not a solved objective fact — the system makes that trade-off visible and operator-controlled rather than hiding it inside a black-box score
- Ledger scalability at national scale — mitigated by batching records into periodic Merkle-root anchors rather than writing every micro-transaction on-chain

---

## Slide 6 — Impact and Scaling
Sub-sections: *Target Users and Areas of Application / Expected Impact and Key Benefits / "VC says yes tomorrow" — Users, Breaks, Crashes, Robustness*

**Target Users and Areas of Application:**
- Disaster-response coordination cells (state/district emergency management)
- NGOs and relief organizations coordinating multi-agency distribution
- Hospital networks needing real-time capacity-aware ambulance routing
- Donor/government bodies needing verifiable proof funds reached their intended use

**Expected Impact and Key Benefits (outcome-framed):**
- Faster, measurably better resource allocation under disruption vs. static dispatch (Phase 6.2 number)
- Fairer outcomes for small/remote/vulnerable zones via the equity floor, not just raw throughput maximization
- Restored trust in relief distribution — any stakeholder can independently verify where resources actually went

**"Users next week" / robustness answer:**
> The architecture already answers this: the backend is stateless-per-scenario (standard horizontal scaling), the road graph swaps for real OpenStreetMap + live disaster-feed data without touching the decision layer, and every event type we demo live (demand spike, road block, hospital capacity cascade, depot depletion) is a real typed event in the system, not a scripted path. Scaling from a simulated region to a real deployment changes the data source, not the architecture — and the ledger's tamper-evidence guarantee holds at any scale since it's a property of the hash chain itself, not of how much data is in it.

---

## Slide 7 — Research and References
Sub-sections: *Research Background and Supporting Evidence / Datasets, Papers, Sources and References / Demo, Competitor Analysis, GitHub or Supporting Links*

**Research Background and Supporting Evidence:**
- Precedent for GNN-based routing on road networks under risk/disruption: PPO-GNN approaches to humanitarian aid vehicle routing in conflict/disaster-affected road networks
- Precedent for equity-aware allocation: lexicographic min-cost-flow approaches that guarantee a protected demand floor before optimizing throughput
- Precedent for the ledger approach: production disaster-relief transparency platforms (AidLedger, CrisisChain) use hash-chained/Merkle-rooted records as their verifiable core, with full smart-contract systems reserved for real-money settlement — we follow the same layering

**Datasets / Papers / Sources:**
- PPO-GNN humanitarian aid routing (conflict-zone road networks, risk-aware routing benchmarks)
- Lexicographic min-cost-flow equity-aware disaster optimization approaches
- Classical OR baselines: Hungarian algorithm (Kuhn, 1955), min-cost-flow (standard network-flow literature)
- Scenario/road-network data: procedurally generated for the demo, architected to swap in real OpenStreetMap + USGS/GDACS feeds (see Feasibility slide)

**Demo / Competitor Analysis / Links:**
- GitHub repo: *[your repo link]*
- **Live demo: *[your deployed Vercel URL]*** — put this prominently, it's a real edge over teams without one
- Nearest existing approaches referenced for comparison: static dispatch systems, OR-only tools, blockchain-heavy relief-fund platforms, dashboard-only trackers (see Slide 4 comparison table)

---

## Optional Slide 8 (template allows +1, total 8 content slides max)
**Suggested use: "Live Metrics Snapshot"** — real screenshots from your Phase 6 benchmark run: the baseline-comparison bar chart (served-demand % across Greedy/Hungarian/Min-Cost-Flow/Trained GNN), the equity-floor before/after comparison, and the ledger tamper-detection demo screenshot. Only include this slide if the numbers are real by submission time.

---

## Before export
- Delete the Instructions slide.
- Confirm no team member names appear anywhere.
- Confirm shared links (GitHub, live demo) are publicly viewable.
- File name: `EL-02_[YourTeamName].pptx` (or `.pdf`).
- Total slide count ≤ 9 (8 content + title).
