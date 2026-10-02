"""Exports trained torch weights to the NumPy runtime format (dev-only; needs
requirements-train.txt). Run from backend/: python -m scripts.export_weights

Produces app/models_store/gnn_weights.npz holding:
  - gnn.*      : gnn_policy.GNNEncoder state_dict (from gnn_policy.pt)
  - triage.*   : triage.TriageScorer weights, trained here with the same
                 150-epoch startup recipe main.py used before the NumPy
                 migration (training at app startup would need torch).

Then verifies the NumPy runtime (app.decision.np_policy) reproduces the torch
model's edge logits, value estimate, and full allocation output on generated
scenarios before writing anything.
"""
from __future__ import annotations

import os

import numpy as np
import torch

from app.decision.gnn_policy import GNNEncoder
from app.decision.np_policy import NumpyGNNEncoder, NumpyTriage, _build_graph_inputs, allocate_with_policy
from app.decision.scenario import generate_scenario
from app.decision.triage import train_triage_scorer

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PT_PATH = os.path.join(BACKEND_DIR, "app", "models_store", "gnn_policy.pt")
NPZ_PATH = os.path.join(BACKEND_DIR, "app", "models_store", "gnn_weights.npz")


def _t(x: np.ndarray) -> torch.Tensor:
    return torch.from_numpy(np.asarray(x, dtype=np.float32))


def main() -> None:
    # --- GNN: load the trained checkpoint we already ship ---
    encoder = GNNEncoder()
    encoder.load_state_dict(torch.load(PT_PATH, map_location="cpu"))
    encoder.eval()
    gnn_state = {k: v.numpy() for k, v in encoder.state_dict().items()}

    # --- Triage: retrain with the exact startup recipe (deterministic seed) ---
    triage, _ = train_triage_scorer(epochs=150)
    triage.eval()
    triage_state = {k: v.numpy() for k, v in triage.state_dict().items()}  # keys already "net.N.*"

    np_gnn = NumpyGNNEncoder(gnn_state)
    np_triage = NumpyTriage(triage_state)

    # --- Parity: torch vs NumPy on fixed scenarios, both regimes ---
    max_logit_diff = 0.0
    max_value_diff = 0.0
    mismatches = 0
    for kwargs in ({}, {"stock_scale": 0.3, "demand_scale": 1.6,
                        "blocked_edges": [("depot-2", "zone-4"), ("depot-1", "zone-2")]}):
        for seed in range(5000, 5010):
            scenario = generate_scenario(seed=seed, **kwargs)
            for resource in sorted({d.resource for d in scenario.demands}):
                built = _build_graph_inputs(scenario, resource)
                if built is None:
                    continue
                depots, demands, depot_feats, zone_feats, edge_index, edge_travel = built
                with torch.no_grad():
                    t_logits, t_value = encoder(_t(depot_feats), _t(zone_feats), edge_index, _t(edge_travel))
                n_logits, n_value = np_gnn.forward(depot_feats, zone_feats, edge_index, edge_travel)
                max_logit_diff = max(max_logit_diff, float(np.abs(t_logits.numpy() - n_logits).max())
                                     if len(edge_index) else 0.0)
                max_value_diff = max(max_value_diff, abs(float(t_value.item()) - n_value))

            # full-pipeline parity: identical allocations, sample=False path
            from app.decision.gnn_policy import allocate_with_policy as torch_allocate
            t_result, _, _ = torch_allocate(encoder, scenario, sample=False)
            n_result, _ = allocate_with_policy(np_gnn, scenario)
            ta = [(a.depot_id, a.zone_id, a.resource, round(a.amount, 6)) for a in t_result.allocations]
            na = [(a.depot_id, a.zone_id, a.resource, round(a.amount, 6)) for a in n_result.allocations]
            if ta != na:
                mismatches += 1
                print(f"MISMATCH seed={seed} kwargs={kwargs}:\n  torch={ta}\n  numpy={na}")

    # triage parity on a grid
    max_triage_diff = 0.0
    for pop in np.linspace(0, 1, 11):
        for unmet in np.linspace(0, 1, 11):
            for inj in np.linspace(0, 1, 5):
                for vuln in (0.2, 0.5, 0.8):
                    with torch.no_grad():
                        t = triage(torch.tensor([[pop, unmet, inj, vuln]], dtype=torch.float32)).item()
                    n = np_triage.score(float(pop), float(unmet), float(inj), float(vuln))
                    max_triage_diff = max(max_triage_diff, abs(t - n))

    print(f"max |edge-logit diff| = {max_logit_diff:.2e}")
    print(f"max |value diff|      = {max_value_diff:.2e}")
    print(f"max |triage diff|     = {max_triage_diff:.2e}")
    print(f"allocation mismatches = {mismatches}/20 scenarios")

    assert max_logit_diff < 1e-4, "GNN logits diverge from torch"
    assert max_value_diff < 1e-4, "GNN value diverges from torch"
    assert max_triage_diff < 1e-5, "Triage scores diverge from torch"
    assert mismatches == 0, "NumPy policy produced different allocations than torch"

    np.savez(NPZ_PATH, **{f"gnn.{k}": v for k, v in gnn_state.items()},
             **{f"triage.{k}": v for k, v in triage_state.items()})
    print(f"wrote {NPZ_PATH} ({os.path.getsize(NPZ_PATH)} bytes) -- parity verified")


if __name__ == "__main__":
    main()
