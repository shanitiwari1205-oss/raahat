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
| **Trained GNN policy** | **82.44%** | **70.60** | **0.064** | ✅ |

**Resolved — history kept for honesty.** An earlier pass found the trained
GNN underperforming all three baselines here (65.83% served, worse than
Greedy's 82.44%). Root-caused to three real, compounding bugs/gaps in
`gnn_policy.py`, not a fundamental limit of the approach:

1. **Stale node embeddings.** `allocate_with_policy` ran the encoder once per
   resource from the *initial* stock state, then sequentially depleted depot
   stock while sampling from those same frozen logits — so the policy kept
   reasoning about depots as if they still had their starting stock, even
   deep into a scenario where a nearby depot had actually run dry. Fixed by
   re-running the encoder with live remaining-stock features before every
   single depot choice.
2. **No feasibility mask.** Without masking, probability mass stayed on
   already-empty depots instead of being redistributed to a farther depot
   that still had stock — directly matching the "won't reach for a farther
   depot" symptom first observed while building the Phase 6.1 demo scenarios.
3. **No multi-depot splitting.** `greedy_nearest` (the baseline it was losing
   to) keeps pulling from the next-nearest depot if one alone can't cover a
   demand (`baselines.py`); the GNN policy picked exactly one depot per
   demand and stopped, even under-served. This was a structural capability
   gap, not just a training issue. Fixed by looping the depot choice per
   demand until it's either fully served or no reachable depot has stock
   left — same structure the baseline already had.
4. **Train/test distribution mismatch.** Training only ever used
   `generate_scenario()`'s generous defaults; the policy had never seen
   scarcity or blocked roads during training at all. Fixed by mixing ~60% of
   training episodes into a scarcity/blocked-road distribution matching this
   benchmark's own regime.

After all four fixes and retraining (150 iterations × 20 episodes, ~75s CPU,
`seed=11`), the GNN now **exactly matches Greedy** — the strongest baseline
under scarcity — and beats Hungarian and ties min-cost-flow. Verified
reproducible across three independent training seeds (11, 23, 42), not a
one-off. Re-ran the baseline-regime benchmark too (table above) to confirm
nothing regressed: still 100% served, reward essentially unchanged
(94.75 → 94.75).

**Honest framing for the pitch**: the GNN now ties the best classical
baseline under scarcity rather than beating it outright — a fair claim is
"matches the best hand-tuned heuristic using a general learned policy, not
hardcoded nearest-first logic," not "strictly beats every baseline." The
equity-floor result below remains the clearer, unambiguous differentiator for
the Innovation slide.

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
