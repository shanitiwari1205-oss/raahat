# RAAHAT — Benchmark & Stress Test Results (Phase 6.2 / 6.4)

All numbers below are real, measured against the running system on this machine
(not estimated). Reproduce with `cd backend && source .venv/bin/activate` then
`curl http://localhost:8842/benchmark` (allocation comparison) or
`python -m scripts.stress_test` (latency/throughput).

## Allocation strategy comparison — baseline regime

Generous stock relative to demand (the original scenario generator defaults).
20 held-out scenarios (seeds 5000-5019), untouched during GNN training.

| Strategy | Served demand | Reward | Equity violation | Capacity valid |
|---|---|---|---|---|
| Greedy (nearest-available) | 100.00% | 94.80 | 0.000 | ✅ |
| Hungarian (optimal assignment) | 94.54% | 87.83 | 0.045 | ✅ |
| Min-cost flow | 98.65% | 93.45 | 0.000 | ✅ |
| **Trained GNN policy** | **100.00%** | **94.75** | **0.000** | ✅ |

Under generous supply, most strategies saturate near 100% — this regime mainly
proves every strategy is *correct* (valid, capacity-respecting allocations),
not which one is *better*. That's why a second, harder regime was added.

## Allocation strategy comparison — scarcity regime

Depot stock cut to 30% of baseline, demand raised 60%, two roads deliberately
blocked (`depot-2→zone-4`, `depot-1→zone-2`). Same 20 seeds.

| Strategy | Served demand | Reward | Equity violation | Capacity valid |
|---|---|---|---|---|
| Greedy (nearest-available) | 82.44% | 70.60 | 0.064 | ✅ |
| Hungarian (optimal assignment) | 70.15% | 61.98 | 0.045 | ✅ |
| Min-cost flow | 81.53% | 71.46 | 0.025 | ✅ |
| **Trained GNN policy** | **65.83%** | **57.30** | **0.086** | ✅ |

**Honest finding, not smoothed over**: under real scarcity, the trained GNN
policy currently performs *worse* than all three classical baselines on
served-demand %, and has the highest equity violation of the four. This
contradicts the "trained policy beats baselines" framing the Innovation slide
was originally going to make, and should be treated as a genuine open issue,
not spun. The likely cause, observed independently while building the Phase
6.1 demo scenarios: the policy is sometimes conservative under a single
reduced-demand allocation and doesn't reach for a farther depot with spare
stock even when it's available, whereas Greedy/min-cost-flow are specifically
built to maximize use of whatever capacity exists. Fixing this is a Phase 2
retraining question (e.g. weighting unserved demand more heavily in the
reward, or including more scarcity-heavy scenarios in training) — out of
scope for this build pass. **Recommendation for the pitch**: present the
baseline-regime numbers as the headline (where the GNN is competitive) and be
upfront in Q&A that the scarcity regime surfaced a real training gap, rather
than hiding it and risking a judge finding it independently via the public
benchmark endpoint.

## Equity floor — real before/after (Phase 6.1's "Hospital Capacity Cascade" demo)

Both depots' blood stock forced to 10 units each (20 total, well below the
50-unit spike) so there genuinely isn't enough supply to go around, same
starting condition both times:

| Equity floor | Served | What happened |
|---|---|---|
| OFF (0%) | 20% (10/50 units) | Main strategy allocated conservatively from the nearer depot only |
| **ON (30%)** | **30% (15/50 units)** | Floor reserved its guaranteed 30% up front, pulling from **both** depots (10 from depot-2, 5 from depot-1) |

This is the floor's real guarantee working as designed: ON delivers at least
its protected percentage regardless of what the main strategy alone would
have done.

## Decision-layer latency (`python -m scripts.stress_test`)

| | Greedy | Hungarian | Min-cost flow | GNN (trained) |
|---|---|---|---|---|
| 5 zones (demo scale), mean / max | 0.019ms / 0.031ms | 0.059ms / 0.094ms | 0.441ms / 0.797ms | 2.445ms / 3.696ms |
| 15 zones (stress scale), mean / max | 0.033ms / 0.039ms | 0.082ms / 0.096ms | 0.839ms / 0.991ms | 5.495ms / 6.426ms |

All strategies stay well under 10ms even at 3x the demo's entity count —
scaling is not a concern for a live demo.

## Simulation tick loop

300 real ticks: **mean 0.0038ms, max 0.0197ms** per tick. The 1s tick
interval leaves enormous headroom; the tick loop will never fall behind.

## Supervisor end-to-end throughput

20 consecutive demand-spike events processed back-to-back through the full
triage → allocation → equity → ledger → feed pipeline on a live `World` +
`Supervisor` instance: **677.8 events/sec**, mean 1.47ms/event, max 3.39ms —
far faster than any operator (or judge) could click.
