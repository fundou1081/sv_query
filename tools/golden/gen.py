#!/usr/bin/env python3
"""
gen.py — Generate actual JSON from a SystemVerilog project using sv_query.

[PR1 2026-06-13] Placeholder. Will be implemented after `visualize module` command.

Usage:
  python tools/golden/gen.py --module axi_xbar --view module \\
      --filelist /tmp/pulp_axi_xbar.f --output actual.json
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Generate actual visualization JSON")
    parser.add_argument("--module", required=True, help="Module to analyze")
    parser.add_argument("--view", required=True, choices=["module", "dataflow", "pipeline"])
    parser.add_argument("--filelist", type=Path, help="Filelist")
    parser.add_argument("--file", type=Path, help="Single file (alternative to --filelist)")
    parser.add_argument("--output", type=Path, required=True, help="Output JSON")
    parser.add_argument("--instance-depth", type=int, default=1,
                        help="Instance hierarchy truncation depth (default 1)")
    args = parser.parse_args()

    if not args.filelist and not args.file:
        print("Error: need --filelist or --file", file=sys.stderr)
        sys.exit(2)

    # [PR1 2026-06-13] TODO: implement when `visualize module` command exists.
    # For now, write a stub JSON so the diff tool can be exercised.
    stub = {
        "_stub": True,
        "_reason": "visualize module command not yet implemented (PR1 in progress)",
        "module": args.module,
        "view": args.view,
        "nodes": [],
        "edges": [],
        "clusters": [],
    }
    with open(args.output, "w") as f:
        json.dump(stub, f, indent=2, ensure_ascii=False)
    print(f"⚠ Wrote stub JSON to {args.output} (visualize module not yet implemented)")
    sys.exit(0)


if __name__ == "__main__":
    main()
