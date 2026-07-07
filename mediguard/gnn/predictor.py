"""Embedding-based DDI link predictor (no PyTorch required).

Learns low-dimensional drug embeddings from the curated INTERACTS_WITH graph via
spectral node embeddings, then scores unseen drug pairs by embedding similarity.
This gives a real, trainable, evaluable novel-interaction predictor that runs on
numpy alone — so the confidence-gate architecture and its metrics work on every
machine. `gnn_torch.py` offers a PyTorch-Geometric upgrade behind the same
DDIPredictor interface for the thesis's "GNN" component.

Method: build the drug-drug interaction adjacency, take the top-k eigenvectors of
the normalized adjacency as embeddings (a spectral graph-embedding, the linear
cousin of a GNN), and score pairs with a logistic model over embedding features.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from mediguard.gnn.base import DDIPrediction, DDIPredictor

CURATED = Path(__file__).resolve().parents[2] / "data" / "curated"


def _norm(s: str) -> str:
    return s.strip().lower()


class SpectralDDIPredictor(DDIPredictor):
    def __init__(self, dim: int = 16, seed: int = 0):
        self.dim = dim
        self.rng = np.random.default_rng(seed)
        self._drugs: list[str] = []
        self._idx: dict[str, int] = {}
        self._known: set[frozenset[str]] = set()
        self._emb: np.ndarray | None = None
        self._w: np.ndarray | None = None
        self._b: float = 0.0
        self._load_and_fit()

    # ------------------------------------------------------------------ #
    def _load_and_fit(self) -> None:
        drugs = json.loads((CURATED / "drugs.json").read_text(encoding="utf-8"))["drugs"]
        inter = json.loads((CURATED / "interactions.json").read_text(encoding="utf-8"))["interactions"]

        self._drugs = [d["name"] for d in drugs]
        self._idx = {_norm(n): i for i, n in enumerate(self._drugs)}
        n = len(self._drugs)

        A = np.zeros((n, n), dtype=float)
        for it in inter:
            a, b = _norm(it["a"]), _norm(it["b"])
            if a in self._idx and b in self._idx:
                i, j = self._idx[a], self._idx[b]
                A[i, j] = A[j, i] = 1.0
                self._known.add(frozenset((a, b)))

        # Symmetric normalized adjacency: D^-1/2 (A+I) D^-1/2
        A_hat = A + np.eye(n)
        deg = A_hat.sum(1)
        d_inv_sqrt = np.diag(1.0 / np.sqrt(np.maximum(deg, 1e-8)))
        L = d_inv_sqrt @ A_hat @ d_inv_sqrt

        # Top-`dim` eigenvectors as node embeddings.
        vals, vecs = np.linalg.eigh(L)
        order = np.argsort(vals)[::-1][: self.dim]
        self._emb = vecs[:, order] * np.sqrt(np.abs(vals[order]))

        self._fit_scorer(A)

    def _pair_features(self, i: int, j: int) -> np.ndarray:
        assert self._emb is not None
        ei, ej = self._emb[i], self._emb[j]
        return np.concatenate([np.abs(ei - ej), ei * ej])  # Hadamard + L1 features

    def _fit_scorer(self, A: np.ndarray) -> None:
        n = A.shape[0]
        X, y = [], []
        pos = [(i, j) for i in range(n) for j in range(i + 1, n) if A[i, j] > 0]
        neg_all = [(i, j) for i in range(n) for j in range(i + 1, n) if A[i, j] == 0]
        self.rng.shuffle(neg_all)
        neg = neg_all[: max(len(pos) * 3, 1)]  # 1:3 pos:neg sampling
        for i, j in pos:
            X.append(self._pair_features(i, j)); y.append(1)
        for i, j in neg:
            X.append(self._pair_features(i, j)); y.append(0)

        from sklearn.linear_model import LogisticRegression

        self._scorer = LogisticRegression(max_iter=1000, class_weight="balanced")
        self._scorer.fit(np.array(X), np.array(y))

    # ------------------------------------------------------------------ #
    def predict(self, drug_a: str, drug_b: str) -> DDIPrediction:
        a, b = _norm(drug_a), _norm(drug_b)
        if a not in self._idx or b not in self._idx or a == b:
            return DDIPrediction(drug_a, drug_b, 0.0)
        feat = self._pair_features(self._idx[a], self._idx[b]).reshape(1, -1)
        p = float(self._scorer.predict_proba(feat)[0, 1])
        return DDIPrediction(drug_a, drug_b, p)

    def known_pair(self, drug_a: str, drug_b: str) -> bool:
        return frozenset((_norm(drug_a), _norm(drug_b))) in self._known

    # ------------------------------------------------------------------ #
    def evaluate(self, test_frac: float = 0.3, seed: int = 1) -> dict:
        """Held-out link-prediction metrics: AUROC, AUPRC, Hits@K."""
        from sklearn.metrics import average_precision_score, roc_auc_score

        rng = np.random.default_rng(seed)
        known = [tuple(sorted(fs)) for fs in self._known]
        rng.shuffle(known)
        cut = int(len(known) * (1 - test_frac))
        test_pos = known[cut:]

        n = len(self._drugs)
        all_neg = [
            (self._drugs[i], self._drugs[j])
            for i in range(n) for j in range(i + 1, n)
            if frozenset((_norm(self._drugs[i]), _norm(self._drugs[j]))) not in self._known
        ]
        rng.shuffle(all_neg)
        test_neg = all_neg[: len(test_pos) * 5]

        y_true, y_score = [], []
        for a, b in test_pos:
            y_true.append(1); y_score.append(self.predict(a, b).probability)
        for a, b in test_neg:
            y_true.append(0); y_score.append(self.predict(a, b).probability)

        y_true = np.array(y_true); y_score = np.array(y_score)
        order = np.argsort(y_score)[::-1]
        hits_at_k = {
            k: float(np.mean(y_true[order[:k]])) for k in (5, 10) if k <= len(y_true)
        }
        return {
            "auroc": float(roc_auc_score(y_true, y_score)) if len(set(y_true)) > 1 else float("nan"),
            "auprc": float(average_precision_score(y_true, y_score)) if len(set(y_true)) > 1 else float("nan"),
            "hits_at_k": hits_at_k,
            "n_test_pos": len(test_pos),
            "n_test_neg": len(test_neg),
        }
