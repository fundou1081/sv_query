#!/usr/bin/env python3
"""check_envelope_contract.py — P182.1a read-only envelope inventory.

This phase intentionally does NOT execute commands and does NOT gate:
it reads the registry/JSON_CONTRACT and prints the current envelope surface.
The executable success/failure/unknown/truncated matrix belongs to P182.1b.

Usage:
    python3 tools/check_envelope_contract.py --inventory
    python3 tools/check_envelope_contract.py --inventory --json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from _bootstrap import ensure_src_first  # noqa: E402

ensure_src_first()

from cli._registry import ALIASES, COMMANDS, JSON_CONTRACT  # noqa: E402


def _contract(key: str) -> dict | None:
    return JSON_CONTRACT.get("commands", {}).get(key)


def _row(spec) -> dict:
    contract = _contract(spec.key)
    if spec.envelope == "standard":
        root = "object(ok,command,params,result,errors)"
        shape = "standard"
    elif contract and ("result_fields" in contract or "fields" in contract):
        root = "object(contract fields)"
        shape = "direct-contract"
    else:
        root = "unknown/varies"
        shape = "direct-no-contract"
    contract_envelope = contract.get("envelope") if contract else None
    return {
        "name": spec.key,
        "layer": spec.layer,
        "group": spec.group,
        "envelope": spec.envelope,
        "contract_envelope": contract_envelope,
        "envelope_mismatch": bool(contract_envelope and contract_envelope != spec.envelope),
        "json": spec.json,
        "listed": spec.listed,
        "aliases": sorted(a for a, c in ALIASES.items() if c == spec.key),
        "shape": shape,
        "root": root,
        "contract_keys": sorted(contract) if contract else [],
    }


def inventory() -> dict:
    listed = [c for c in COMMANDS if c.listed]
    rows = [_row(c) for c in listed]
    env = Counter(r["envelope"] for r in rows)
    layers = Counter(r["layer"] for r in rows)
    mismatches = [r["name"] for r in rows if r["envelope_mismatch"]]
    return {
        "inventory": "P182.1a",
        "mode": "read-only-static",
        "counts": {
            "total": len(rows),
            "by_layer": dict(sorted(layers.items())),
            "by_envelope": dict(sorted(env.items())),
            "aliases": len(ALIASES),
        },
        "envelope_mismatches": mismatches,
        "rows": rows,
    }


def render_text(data: dict) -> None:
    c = data["counts"]
    print("P182.1a envelope inventory (read-only, no execution)")
    print(f"total={c['total']} by_layer={c['by_layer']} "
          f"by_envelope={c['by_envelope']} aliases={c['aliases']}")
    print("name\tlayer\tenvelope\tshape\troot")
    for r in data["rows"]:
        print(f"{r['name']}\t{r['layer']}\t{r['envelope']}\t{r['shape']}\t{r['root']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", action="store_true", help="read-only inventory (default)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()
    data = inventory()
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        render_text(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
