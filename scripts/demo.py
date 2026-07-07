"""MediGuard CLI demo — run the full pipeline on a patient report, no server needed.

    python scripts/demo.py "32, pregnant, cramps and fever, high sugar"
    python scripts/demo.py            # runs a built-in example
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Windows consoles default to cp1252; force UTF-8 so the box/emoji output prints.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from mediguard.pipeline import MediGuardPipeline  # noqa: E402

_STATUS_ICON = {"allow": "✅", "warn": "⚠️", "downgrade": "⚠️", "block": "❌"}


def main() -> None:
    text = sys.argv[1] if len(sys.argv) > 1 else (
        "58 year old man with high blood pressure and type 2 diabetes, on metformin and aspirin"
    )
    print(f"\nPatient report:\n  {text}\n")
    pipe = MediGuardPipeline()
    results = pipe.run(pipe.extractor.extract(text, consent_captured=True))

    if not results:
        print("No recognized conditions to act on.")
        return

    for cr in results:
        print(f"── {cr.condition_display} ({cr.condition_code}) " + "─" * 30)
        if cr.abstain:
            print(f"   🧑‍⚕️ Defer to clinician: {cr.abstain_reason}")
        for rec in cr.recommendations:
            icon = _STATUS_ICON.get(rec.verdict.status.value, "•")
            tag = " [deferred]" if rec.abstain else ""
            print(f"   {icon} {rec.candidate.drug.name:24s} {rec.verdict.status.value:10s}"
                  f" conf={rec.confidence:.2f}{tag}")
            for r in rec.verdict.reasons:
                print(f"        - [{r.severity.value}] {r.message}")
        print()

    print(results[0].recommendations[0].disclaimer)


if __name__ == "__main__":
    main()
