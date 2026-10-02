"""Trained urgency/triage scorer -- a small MLP over zone features, not a
hardcoded weighted sum. Trained on procedurally generated synthetic scenario
data where the "ground truth" urgency comes from a nonlinear formula the
network has to learn, so training is genuine (not memorizing a trivial
linear relationship).
"""
from __future__ import annotations

import random

import torch
import torch.nn as nn

FEATURE_NAMES = ["population_norm", "unmet_duration_norm", "injury_severity_mix", "vulnerability_index"]


class TriageScorer(nn.Module):
    def __init__(self, in_features: int = len(FEATURE_NAMES), hidden: int = 16):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_features, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden // 2),
            nn.ReLU(),
            nn.Linear(hidden // 2, 1),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


def _synthetic_ground_truth(pop, unmet, injury, vuln) -> float:
    """Nonlinear synthetic label: urgency rises superlinearly with unmet
    duration once injury severity is high, and vulnerability amplifies it."""
    base = 0.35 * unmet + 0.3 * injury + 0.2 * pop
    amplified = base * (1 + 0.6 * vuln) + 0.4 * (unmet ** 2) * injury
    return max(0.0, min(1.0, amplified))


def generate_training_data(n: int = 4000, seed: int = 7) -> tuple[torch.Tensor, torch.Tensor]:
    rng = random.Random(seed)
    xs, ys = [], []
    for _ in range(n):
        pop = rng.uniform(0, 1)
        unmet = rng.uniform(0, 1)
        injury = rng.uniform(0, 1)
        vuln = rng.uniform(0, 1)
        label = _synthetic_ground_truth(pop, unmet, injury, vuln)
        noisy_label = max(0.0, min(1.0, label + rng.gauss(0, 0.03)))
        xs.append([pop, unmet, injury, vuln])
        ys.append(noisy_label)
    return torch.tensor(xs, dtype=torch.float32), torch.tensor(ys, dtype=torch.float32)


def train_triage_scorer(epochs: int = 200, lr: float = 0.01, seed: int = 7) -> tuple[TriageScorer, list[float]]:
    torch.manual_seed(seed)
    model = TriageScorer()
    x_train, y_train = generate_training_data(n=3000, seed=seed)
    x_val, y_val = generate_training_data(n=600, seed=seed + 1)

    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()

    val_curve = []
    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        pred = model(x_train)
        loss = loss_fn(pred, y_train)
        loss.backward()
        optimizer.step()

        if epoch % 10 == 0 or epoch == epochs - 1:
            model.eval()
            with torch.no_grad():
                val_loss = loss_fn(model(x_val), y_val).item()
            val_curve.append(val_loss)

    return model, val_curve


def score(model: TriageScorer, pop: float, unmet: float, injury: float, vuln: float) -> float:
    model.eval()
    with torch.no_grad():
        x = torch.tensor([[pop, unmet, injury, vuln]], dtype=torch.float32)
        return float(model(x).item())
