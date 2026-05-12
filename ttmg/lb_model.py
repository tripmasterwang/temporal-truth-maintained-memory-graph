"""CalLB MLP reranker.

Tiny MLP that maps a (q, item) feature vector → P(item is load-bearing).
Single hidden layer, ~14K params. CPU-only training in <5 min.

Trained with BCE loss on `1[label = LB]` (3-tier label collapsed to binary).
The 3-tier semantics (LB / S / D) re-enter the pipeline in the CRC layer
where the *risk* depends on the D class, not the binary training target.

Public surface:
  - LBReranker (nn.Module): the MLP itself.
  - train_mlp(X, y, dim_hidden=32, ...) -> (model, train_history).
  - save(model, path), load(path) -> model.
  - score(model, X) -> sigmoid logits as np.ndarray (CPU).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset


class LBReranker(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 32):
        super().__init__()
        self.input_dim = int(input_dim)
        self.hidden_dim = int(hidden_dim)
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.fc3 = nn.Linear(hidden_dim, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = F.relu(self.fc1(x))
        h = F.relu(self.fc2(h))
        return self.fc3(h).squeeze(-1)  # logits


def _set_seed(seed: int) -> None:
    np.random.seed(seed)
    torch.manual_seed(seed)


def train_mlp(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_dev: np.ndarray,
    y_dev: np.ndarray,
    *,
    hidden_dim: int = 32,
    lr: float = 1e-3,
    weight_decay: float = 1e-4,
    epochs: int = 5,
    batch_size: int = 64,
    seed: int = 0,
) -> Tuple[LBReranker, Dict]:
    """Train the MLP. Returns (model, history dict).

    `X_train` shape (N_train, D); `y_train` shape (N_train,) with 0/1 labels.
    """
    _set_seed(seed)
    input_dim = X_train.shape[1]
    model = LBReranker(input_dim=input_dim, hidden_dim=hidden_dim)
    optim = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)

    Xt = torch.from_numpy(X_train.astype(np.float32))
    yt = torch.from_numpy(y_train.astype(np.float32))
    Xd = torch.from_numpy(X_dev.astype(np.float32))
    yd = torch.from_numpy(y_dev.astype(np.float32))

    # Class-imbalance handling: pos_weight = (#neg / #pos) so BCE is balanced.
    n_pos = float(yt.sum().item())
    n_neg = float(len(yt) - n_pos)
    pos_weight = torch.tensor([(n_neg / max(1.0, n_pos))], dtype=torch.float32)

    ds = TensorDataset(Xt, yt)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=True, drop_last=False)

    history = {"train_loss": [], "dev_loss": [], "dev_auc": []}
    for ep in range(epochs):
        model.train()
        ep_loss = 0.0
        n_batches = 0
        for xb, yb in loader:
            optim.zero_grad()
            logits = model(xb)
            loss = F.binary_cross_entropy_with_logits(logits, yb, pos_weight=pos_weight)
            loss.backward()
            optim.step()
            ep_loss += float(loss.item())
            n_batches += 1
        # Dev eval
        model.eval()
        with torch.no_grad():
            dev_logits = model(Xd)
            dev_loss = F.binary_cross_entropy_with_logits(
                dev_logits, yd, pos_weight=pos_weight
            ).item()
            dev_probs = torch.sigmoid(dev_logits).cpu().numpy()
        try:
            from sklearn.metrics import roc_auc_score
            dev_auc = float(roc_auc_score(y_dev, dev_probs)) if len(set(y_dev.tolist())) > 1 else float("nan")
        except Exception:
            dev_auc = float("nan")
        history["train_loss"].append(ep_loss / max(1, n_batches))
        history["dev_loss"].append(dev_loss)
        history["dev_auc"].append(dev_auc)
    return model, history


def save(model: LBReranker, path: str, feature_names: tuple) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "input_dim": model.input_dim,
        "hidden_dim": model.hidden_dim,
        "feature_names": list(feature_names),
        "state_dict": {k: v.cpu().tolist() for k, v in model.state_dict().items()},
    }
    with open(p, "w") as fh:
        json.dump(payload, fh)


def load(path: str) -> Tuple[LBReranker, list]:
    with open(path) as fh:
        payload = json.load(fh)
    model = LBReranker(input_dim=int(payload["input_dim"]), hidden_dim=int(payload["hidden_dim"]))
    sd = {k: torch.tensor(v) for k, v in payload["state_dict"].items()}
    model.load_state_dict(sd)
    model.eval()
    return model, list(payload["feature_names"])


def score(model: LBReranker, X: np.ndarray) -> np.ndarray:
    """Return sigmoid probabilities for each row of X. Shape (N,)."""
    model.eval()
    with torch.no_grad():
        Xt = torch.from_numpy(X.astype(np.float32))
        logits = model(Xt)
        probs = torch.sigmoid(logits).cpu().numpy()
    return probs
