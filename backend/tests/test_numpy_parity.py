"""Verifies the NumPy runtime (np_policy) numerically matches the torch
originals -- the guard that keeps the deploy-time torch removal honest.
Auto-skips when torch isn't installed (e.g. the Vercel build, which must
NOT have torch -- see requirements.txt).
"""
from __future__ import annotations

import numpy as np
import pytest

from app.decision.np_policy import NumpyGNNEncoder, NumpyTriage, _build_graph_inputs, allocate_with_policy, load_models
from app.decision.scenario import generate_scenario

torch = pytest.importorskip("torch")


def _t(x: np.ndarray):
    return torch.from_numpy(np.asarray(x, dtype=np.float32))

SCARCITY_KWARGS = {
    "stock_scale": 0.3,
    "demand_scale": 1.6,
    "blocked_edges": [("depot-2", "zone-4"), ("depot-1", "zone-2")],
}


@pytest.fixture(scope="module")
def models():
    from app.decision.gnn_policy import GNNEncoder

    gnn = GNNEncoder()
    gnn.load_state_dict(torch.load(
        "app/models_store/gnn_policy.pt", map_location="cpu"))
    gnn.eval()
    np_gnn, np_triage = load_models()
    return gnn, np_gnn, np_triage


def _regimes():
    return [{}, SCARCITY_KWARGS]


def test_gnn_forward_parity(models):
    gnn, np_gnn, _ = models
    for kwargs in _regimes():
        for seed in range(5000, 5006):
            scenario = generate_scenario(seed=seed, **kwargs)
            for resource in sorted({d.resource for d in scenario.demands}):
                built = _build_graph_inputs(scenario, resource)
                if built is None:
                    continue
                _, _, depot_feats, zone_feats, edge_index, edge_travel = built
                with torch.no_grad():
                    t_logits, t_value = gnn(_t(depot_feats), _t(zone_feats), edge_index, _t(edge_travel))
                n_logits, n_value = np_gnn.forward(depot_feats, zone_feats, edge_index, edge_travel)
                if len(edge_index):
                    assert np.abs(t_logits.numpy() - n_logits).max() < 1e-4
                assert abs(float(t_value.item()) - n_value) < 1e-4


def test_allocation_parity(models):
    from app.decision.gnn_policy import allocate_with_policy as torch_allocate

    gnn, np_gnn, _ = models
    for kwargs in _regimes():
        for seed in range(5000, 5006):
            scenario = generate_scenario(seed=seed, **kwargs)
            t_result, _, _ = torch_allocate(gnn, scenario, sample=False)
            n_result, _ = allocate_with_policy(np_gnn, scenario)
            key = lambda a: (a.depot_id, a.zone_id, a.resource, round(a.amount, 6))
            assert [key(a) for a in t_result.allocations] == [key(a) for a in n_result.allocations]


def test_triage_parity(models):
    _, _, np_triage = models
    # The shipped npz triage weights ARE the trained model, so rebuild a
    # TriageScorer from the same arrays and compare torch vs numpy forward.
    from app.decision.triage import TriageScorer, score as torch_score

    trained = TriageScorer()
    with np.load("app/models_store/gnn_weights.npz") as z:
        state = {k[len("triage."):]: torch.tensor(z[k]) for k in z.files if k.startswith("triage.")}
    trained.load_state_dict(state)
    trained.eval()

    for pop in np.linspace(0, 1, 6):
        for unmet in np.linspace(0, 1, 6):
            for inj in (0.1, 0.5, 0.9):
                for vuln in (0.2, 0.8):
                    t = torch_score(trained, float(pop), float(unmet), float(inj), float(vuln))
                    n = np_triage.score(float(pop), float(unmet), float(inj), float(vuln))
                    assert abs(t - n) < 1e-5, (pop, unmet, inj, vuln, t, n)
