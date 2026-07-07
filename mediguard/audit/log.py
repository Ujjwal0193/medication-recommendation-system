"""Audit log — records which rules fired for every safety evaluation.

Doubles as explainability evidence and the regulatory-defense trail. Entries are
append-only JSON lines. Also exposes the mandatory consent directive helper.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from mediguard.schemas import CONSENT_DIRECTIVE, SafetyVerdict

_DEFAULT_LOG = Path(__file__).resolve().parents[2] / "data" / "audit_log.jsonl"


class AuditLog:
    def __init__(self, path: Path | None = None):
        self.path = path or _DEFAULT_LOG
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, verdict: SafetyVerdict, *, patient_ref: str = "anonymous",
               extra: dict | None = None) -> dict:
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "patient_ref": patient_ref,
            "drug": verdict.candidate.drug.name,
            "condition": verdict.candidate.for_condition.code,
            "status": verdict.status.value,
            "max_severity": verdict.max_severity.value,
            "fired_rules": verdict.fired_rules,
            "reasons": [r.message for r in verdict.reasons],
        }
        if extra:
            entry.update(extra)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry


def consent_directive() -> str:
    """The mandatory consult-a-doctor note appended to every user-facing output."""
    return CONSENT_DIRECTIVE
