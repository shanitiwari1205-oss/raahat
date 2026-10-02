"""NumPy inference mirror of the torch models (gnn_policy.GNNEncoder,
triage.TriageScorer) for the deployed runtime.

Why this exists: Vercel caps Python serverless functions at 500 MB and the
CPU-only torch wheel alone is ~770 MB, so torch cannot ship in the deployed
function at all -- no amount of trimming fixes that. Training stays in torch
(gnn_policy.py / triage.py + scripts/export_weights.py, installed via
requirements-train.txt); runtime inference is this mathematically identical
NumPy reimplementation. Weight parity against the torch version is verified
by tests/test_numpy_parity.py (auto-skipped when torch isn't installed, e.g.
in the deploy build) and again inside export_weights.py at export time.

The forward math mirrors the torch code exactly, including GRUCell gate
semantics (torch computes n = tanh(W_in x + b_in + r * (W_hn h + b_hn)),
i.e. the hidden bias is added before the reset-gate multiply).
"""
from __future__ import annotations

import os

import numpy as np

from .allocation_types import Allocation, AllocationResult
from .scenario import Scenario

NODE_EMBED_DIM = 16
EQUITY_FLOOR = 0.3  # default protected-demand fraction for vulnerable zones

WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "..", "models_store", "gnn_weights.npz")


def _linear(x: np.ndarray, w: np.ndarray, b: np.ndarray) -> np.ndarray:
    return x @ w.T + b


def _relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(x, 0.0)


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def _gru_cell(x: np.ndarray, h: np.ndarray, w_ih: np.ndarray, w_hh: np.ndarray,
              b_ih: np.ndarray, b_hh: np.ndarray) -> np.ndarray:
    gi = x @ w_ih.T + b_ih
    gh = h @ w_hh.T + b_hh
    g = w_ih.shape[0] // 3  # gate size = embed dim; w_ih is [3*g, embed]
    r = _sigmoid(gi[:g] + gh[:g])
    z = _sigmoid(gi[g:2 * g] + gh[g:2 * g])
    nn = np.tanh(gi[2 * g:] + r * gh[2 * g:])
    return (1.0 - z) * nn + z * h


class NumpyGNNEncoder:
    """Weights-only twin of gnn_policy.GNNEncoder (2-round mean-aggregation
    message passing + edge scoring head + value head)."""

    def __init__(self, w: dict[str, np.ndarray]):
        self.w = {k: np.asarray(v, dtype=np.float32) for k, v in w.items()}

    def forward(self, depot_feats: np.ndarray, zone_feats: np.ndarray,
                edge_index: list[tuple[int, int]], edge_travel_norm: np.ndarray):
        w = self.w
        d = _relu(_linear(depot_feats, w["depot_init.weight"], w["depot_init.bias"]))
        z = _relu(_linear(zone_feats, w["zone_init.weight"], w["zone_init.bias"]))

        for _ in range(2):  # 2 rounds of message passing
            msgs: dict[int, list[np.ndarray]] = {(kind, i): []
                                                 for kind in ("d", "z")
                                                 for i in range(d.shape[0] if kind == "d" else z.shape[0])}
            for e, (i, j) in enumerate(edge_index):
                edge_feat = np.array([edge_travel_norm[e]], dtype=np.float32)
                msg = _relu(_linear(np.concatenate([d[i], z[j], edge_feat]),
                                    w["edge_mlp.0.weight"], w["edge_mlp.0.bias"]))
                msgs[("d", i)].append(msg)
                msgs[("z", j)].append(msg)
            d = np.stack([
                _gru_cell(np.mean(msgs[("d", i)], axis=0), d[i],
                          w["msg_update.weight_ih"], w["msg_update.weight_hh"],
                          w["msg_update.bias_ih"], w["msg_update.bias_hh"])
                if msgs[("d", i)] else d[i]
                for i in range(d.shape[0])
            ])
            z = np.stack([
                _gru_cell(np.mean(msgs[("z", j)], axis=0), z[j],
                          w["msg_update.weight_ih"], w["msg_update.weight_hh"],
                          w["msg_update.bias_ih"], w["msg_update.bias_hh"])
                if msgs[("z", j)] else z[j]
                for j in range(z.shape[0])
            ])

        if edge_index:
            edge_logits = np.array([
                _linear(_relu(_linear(np.concatenate([d[i], z[j], [edge_travel_norm[e]]]),
                                      w["score_head.0.weight"], w["score_head.0.bias"])),
                        w["score_head.2.weight"], w["score_head.2.bias"])[0]
                for e, (i, j) in enumerate(edge_index)
            ], dtype=np.float32)
        else:
            edge_logits = np.zeros(0, dtype=np.float32)

        all_nodes = np.concatenate([d, z], axis=0)
        pooled = all_nodes.mean(axis=0) if all_nodes.shape[0] > 0 else np.zeros(NODE_EMBED_DIM, dtype=np.float32)
        value = _linear(_relu(_linear(pooled, w["value_head.0.weight"], w["value_head.0.bias"])),
                        w["value_head.2.weight"], w["value_head.2.bias"])[0]
        return edge_logits, float(value)


class NumpyTriage:
    """Weights-only twin of triage.TriageScorer (4->16->8->1 MLP + sigmoid)."""

    def __init__(self, w: dict[str, np.ndarray]):
        self.w = {k: np.asarray(v, dtype=np.float32) for k, v in w.items()}

    def forward(self, x: np.ndarray) -> np.ndarray:
        w = self.w
        h = _relu(_linear(x, w["net.0.weight"], w["net.0.bias"]))
        h = _relu(_linear(h, w["net.2.weight"], w["net.2.bias"]))
        return _sigmoid(_linear(h, w["net.4.weight"], w["net.4.bias"])).squeeze(-1)

    def score(self, pop: float, unmet: float, injury: float, vuln: float) -> float:
        return float(self.forward(np.array([[pop, unmet, injury, vuln]], dtype=np.float32))[0])


def load_models(path: str | None = None) -> tuple[NumpyGNNEncoder, NumpyTriage]:
    """Loads GNN + triage weights exported by scripts/export_weights.py."""
    p = path or WEIGHTS_PATH
    with np.load(p) as z:
        gnn = NumpyGNNEncoder({k[4:]: z[k] for k in z.files if k.startswith("gnn.")})
        triage = NumpyTriage({k[7:]: z[k] for k in z.files if k.startswith("triage.")})
    return gnn, triage


def _build_graph_inputs(scenario: Scenario, resource: str):
    depots = [ds for ds in scenario.depot_stocks if ds.resource == resource]
    demands = [d for d in scenario.demands if d.resource == resource]
    if not depots or not demands:
        return None

    max_stock = max(ds.stock for ds in depots) or 1.0
    max_demand = max(d.amount for d in demands) or 1.0
    max_travel = max(
        (t for t in scenario.travel_time.values() if t != float("inf")), default=1.0
    ) or 1.0

    depot_feats = np.array([[ds.stock / max_stock, 1.0] for ds in depots], dtype=np.float32)
    zone_feats = np.array(
        [[d.amount / max_demand, d.urgency, d.vulnerability_index] for d in demands], dtype=np.float32
    )

    edge_index, edge_travel = [], []
    for i, dep in enumerate(depots):
        for j, dem in enumerate(demands):
            tt = scenario.travel_time.get((dep.depot_id, dem.zone_id), float("inf"))
            if tt == float("inf"):
                continue
            edge_index.append((i, j))
            edge_travel.append(tt / max_travel)

    return depots, demands, depot_feats, zone_feats, edge_index, np.array(edge_travel, dtype=np.float32)


def allocate_with_policy(
    encoder: NumpyGNNEncoder, scenario: Scenario
) -> tuple[AllocationResult, float]:
    """Greedy inference twin of the torch version's sample=False path (the
    only path the live supervisor and benchmark use): depots are chosen
    per demand in urgency order from the GNN's edge-score distribution's
    argmax, re-encoding with *current* remaining stock each step
    (stale-embedding fix), masked to depots that still have stock
    (feasibility fix), and splitting across multiple depots until the
    demand is met or stock runs out (multi-depot fix). Returns the
    allocation result and the mean initial-state value estimate."""
    allocations: list[Allocation] = []
    values: list[float] = []

    resources = sorted({d.resource for d in scenario.demands})
    for resource in resources:
        built = _build_graph_inputs(scenario, resource)
        if built is None:
            continue
        depots, demands, depot_feats, zone_feats, edge_index, edge_travel = built
        _, value = encoder.forward(depot_feats, zone_feats, edge_index, edge_travel)
        values.append(value)
        if not edge_index:
            continue

        max_stock = max(dep.stock for dep in depots) or 1.0
        remaining_stock = {dep.depot_id: dep.stock for dep in depots}
        demand_order = sorted(range(len(demands)), key=lambda j: -demands[j].urgency)

        for j in demand_order:
            dem = demands[j]
            remaining_demand = dem.amount

            while remaining_demand > 1e-9:
                live_depot_feats = np.array(
                    [[remaining_stock[dep.depot_id] / max_stock, 1.0] for dep in depots], dtype=np.float32
                )
                live_edge_logits, _ = encoder.forward(live_depot_feats, zone_feats, edge_index, edge_travel)

                candidate_edges = [
                    e for e, (i, jj) in enumerate(edge_index)
                    if jj == j and remaining_stock[depots[i].depot_id] > 1e-9
                ]
                if not candidate_edges:
                    break
                logits = live_edge_logits[candidate_edges]
                choice = int(np.argmax(logits))

                depot_i = edge_index[candidate_edges[choice]][0]
                depot_id = depots[depot_i].depot_id
                available = remaining_stock[depot_id]
                send = min(available, remaining_demand)
                if send <= 0:
                    break
                remaining_stock[depot_id] -= send
                remaining_demand -= send
                allocations.append(Allocation(depot_id, dem.zone_id, resource, send))

    result = AllocationResult(strategy="gnn_trained", allocations=allocations, scenario=scenario)
    pooled_value = float(np.mean(values)) if values else 0.0
    return result, pooled_value
