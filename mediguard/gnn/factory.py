"""Select the DDI predictor backend.

Default: SpectralDDIPredictor (numpy/sklearn, runs everywhere).
Optional: PyTorch-Geometric GNN if the `gnn` extra is installed and loads.
Both implement DDIPredictor, so the ConfidenceGate is backend-agnostic.
"""

from __future__ import annotations

from mediguard.gnn.base import DDIPredictor
from mediguard.gnn.predictor import SpectralDDIPredictor


def make_ddi_predictor(prefer_torch: bool = False) -> DDIPredictor:
    if prefer_torch:
        try:
            from mediguard.gnn.gnn_torch import TorchGNNPredictor

            return TorchGNNPredictor()
        except Exception:  # noqa: BLE001 - fall back to the always-available predictor
            pass
    return SpectralDDIPredictor()
