"""Optional PyTorch-Geometric GNN DDI predictor (thesis "GNN novelty" component).

Requires `pip install -e ".[gnn]"`. Implements a GCN encoder + dot-product link
decoder over the drug-drug interaction graph (the SafeDrug / Decagon family of
approaches), exposing the same DDIPredictor interface as the numpy predictor so
the ConfidenceGate and the rest of the system are unchanged.

If torch / torch_geometric are unavailable this module fails to import and the
factory falls back to SpectralDDIPredictor automatically.
"""

from __future__ import annotations

import json
from pathlib import Path

from mediguard.gnn.base import DDIPrediction, DDIPredictor

CURATED = Path(__file__).resolve().parents[2] / "data" / "curated"


def _norm(s: str) -> str:
    return s.strip().lower()


class TorchGNNPredictor(DDIPredictor):
    def __init__(self, dim: int = 32, epochs: int = 200, seed: int = 0):
        import torch
        from torch_geometric.nn import GCNConv

        self.torch = torch
        torch.manual_seed(seed)

        drugs = json.loads((CURATED / "drugs.json").read_text(encoding="utf-8"))["drugs"]
        inter = json.loads((CURATED / "interactions.json").read_text(encoding="utf-8"))["interactions"]
        self._drugs = [d["name"] for d in drugs]
        self._idx = {_norm(n): i for i, n in enumerate(self._drugs)}
        self._known: set[frozenset[str]] = set()

        edges = []
        for it in inter:
            a, b = _norm(it["a"]), _norm(it["b"])
            if a in self._idx and b in self._idx:
                i, j = self._idx[a], self._idx[b]
                edges += [[i, j], [j, i]]
                self._known.add(frozenset((a, b)))

        n = len(self._drugs)
        self._edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()
        self._x = torch.eye(n)  # one-hot node features

        class Encoder(torch.nn.Module):
            def __init__(self, in_dim, hid):
                super().__init__()
                self.c1 = GCNConv(in_dim, hid)
                self.c2 = GCNConv(hid, hid)

            def forward(self, x, ei):
                x = self.c1(x, ei).relu()
                return self.c2(x, ei)

        self._model = Encoder(n, dim)
        self._train(epochs)

    def _train(self, epochs: int) -> None:
        torch = self.torch
        opt = torch.optim.Adam(self._model.parameters(), lr=0.01)
        pos = self._edge_index
        n = self._x.size(0)
        for _ in range(epochs):
            self._model.train(); opt.zero_grad()
            z = self._model(self._x, self._edge_index)
            neg = torch.randint(0, n, pos.size(), device=pos.device)
            pos_score = (z[pos[0]] * z[pos[1]]).sum(-1)
            neg_score = (z[neg[0]] * z[neg[1]]).sum(-1)
            loss = torch.nn.functional.binary_cross_entropy_with_logits(
                torch.cat([pos_score, neg_score]),
                torch.cat([torch.ones_like(pos_score), torch.zeros_like(neg_score)]),
            )
            loss.backward(); opt.step()
        self._model.eval()
        with torch.no_grad():
            self._z = self._model(self._x, self._edge_index)

    def predict(self, drug_a: str, drug_b: str) -> DDIPrediction:
        a, b = _norm(drug_a), _norm(drug_b)
        if a not in self._idx or b not in self._idx or a == b:
            return DDIPrediction(drug_a, drug_b, 0.0)
        score = (self._z[self._idx[a]] * self._z[self._idx[b]]).sum().item()
        prob = 1.0 / (1.0 + pow(2.718281828, -score))
        return DDIPrediction(drug_a, drug_b, float(prob))

    def known_pair(self, drug_a: str, drug_b: str) -> bool:
        return frozenset((_norm(drug_a), _norm(drug_b))) in self._known
