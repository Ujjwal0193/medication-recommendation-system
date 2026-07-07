"""Normalize curated drug names to RxNorm RxCUIs via the free RxNav API.

RxNav (https://rxnav.nlm.nih.gov) is a public NLM service — no key, free to use.
This script cross-checks the RxCUIs hand-entered in data/curated/drugs.json and
reports mismatches / lookups. It is *advisory*: the curated file remains the
source of truth, but running this before a demo catches stale codes.

Usage:
    python etl/normalize_rxnorm.py            # verify all curated drugs
    python etl/normalize_rxnorm.py --write    # write verified RxCUIs back

Offline-safe: on any network error it reports and continues (does not crash the
build), because the KG loader does not depend on RxNav being reachable.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

CURATED = Path(__file__).resolve().parents[1] / "data" / "curated" / "drugs.json"
RXNAV_BASE = "https://rxnav.nlm.nih.gov/REST"
TIMEOUT = 10


def lookup_rxcui(name: str) -> str | None:
    """Return the ingredient RxCUI for a drug name, or None."""
    url = f"{RXNAV_BASE}/rxcui.json?name={quote(name)}&search=2"
    try:
        r = requests.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        ids = r.json().get("idGroup", {}).get("rxnormId", [])
        return ids[0] if ids else None
    except Exception as exc:  # noqa: BLE001 - advisory tool, never fatal
        print(f"  ! network/parse error for {name!r}: {exc}", file=sys.stderr)
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write verified RxCUIs back to drugs.json")
    args = ap.parse_args()

    data = json.loads(CURATED.read_text(encoding="utf-8"))
    drugs = data["drugs"]

    matches = mismatches = missing = 0
    for d in drugs:
        name = d["name"]
        curated_rxcui = d.get("rxcui")
        found = lookup_rxcui(name)
        time.sleep(0.1)  # be polite to the public API

        if found is None:
            print(f"[?] {name:28s} curated={curated_rxcui}  RxNav=<no result>")
            missing += 1
        elif found == curated_rxcui:
            print(f"[OK] {name:28s} rxcui={found}")
            matches += 1
        else:
            print(f"[!!] {name:28s} curated={curated_rxcui}  RxNav={found}  (mismatch)")
            mismatches += 1
            if args.write:
                d["rxcui"] = found

    print(f"\nSummary: {matches} match, {mismatches} mismatch, {missing} not found "
          f"({len(drugs)} drugs).")

    if args.write and mismatches:
        CURATED.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote updated RxCUIs to {CURATED}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
