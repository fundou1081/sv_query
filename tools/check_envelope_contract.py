#!/usr/bin/env python3
"""check_envelope_contract.py — P182.1a inventory + P182.1b canary gate.

Two explicit modes:

- ``--inventory`` (default): read-only, static; reads registry/JSON_CONTRACT and
  prints the envelope surface. It does not execute any command.
- ``--canary``: executes exactly 6 success cases + 1 failure case on the
  scheduler_minimal fixture and gates the standard envelope. The full
  success/failure/unknown/truncated matrix is out of scope for P182.1b phase 1.

Usage:
    python3 tools/check_envelope_contract.py --inventory
    python3 tools/check_envelope_contract.py --inventory --json
    python3 tools/check_envelope_contract.py --canary
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
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


FIXTURE = "sim/tests/fixtures/scheduler_minimal/filelist.f"
SIGNAL = "Scheduler_minimal.s0_reg"
SUCCESS_KEYS = tuple(JSON_CONTRACT["envelope_policy"]["standard"].split("/"))
CANARY_TIMEOUT_SECONDS = 180

CANARY_SUCCESS_CASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("stats", ("stats", "--filelist", FIXTURE, "--json")),
    ("drivers", ("drivers", SIGNAL, "--filelist", FIXTURE, "--json")),
    ("loads", ("loads", SIGNAL, "--filelist", FIXTURE, "--json")),
    ("graph nodes", ("graph", "nodes", "--filelist", FIXTURE, "--json")),
    ("graph edges", ("graph", "edges", "--filelist", FIXTURE, "--json")),
    ("controlflow analyze", ("controlflow", "analyze", SIGNAL, "--filelist", FIXTURE, "--json")),
)
# Known rc=0/ok=false mismatch for `drivers <unknown signal>` is intentionally
# NOT gated here; P182.1b phase 1 records it as a known limitation instead.
CANARY_FAILURE_CASE = (
    "stats missing file",
    ("stats", "--file", "does_not_exist_canary.sv", "--json"),
)


@dataclass(frozen=True)
class CaseRun:
    rc: int
    stdout: str
    stderr: str


Runner = Callable[[tuple[str, ...]], CaseRun]
Validator = Callable[[CaseRun], list[str]]


@dataclass(frozen=True)
class CaseOutcome:
    label: str
    kind: str
    rc: int | None
    problems: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.problems


def run_cli_case(argv: tuple[str, ...]) -> CaseRun:
    proc = subprocess.run(
        [sys.executable, "run_cli.py", *argv],
        cwd=ROOT, capture_output=True, text=True, timeout=CANARY_TIMEOUT_SECONDS,
    )
    return CaseRun(proc.returncode, proc.stdout, proc.stderr)


def _parse_root(run: CaseRun) -> tuple[dict | None, list[str]]:
    try:
        root = json.loads(run.stdout)
    except json.JSONDecodeError as exc:
        return None, [f"stdout is not JSON ({exc.msg} at pos {exc.pos})"]
    if not isinstance(root, dict):
        return None, [f"root is {type(root).__name__}, expected object"]
    return root, []


def success_violations(run: CaseRun) -> list[str]:
    problems = [] if run.rc == 0 else [f"rc={run.rc}, expected 0"]
    root, parse_problems = _parse_root(run)
    problems.extend(parse_problems)
    if root is None:
        return problems
    missing = [key for key in SUCCESS_KEYS if key not in root]
    if missing:
        problems.append(f"missing keys: {', '.join(missing)}")
    if root.get("ok") is not True:
        problems.append(f"ok={root.get('ok')!r}, expected true")
    if not isinstance(root.get("errors"), list):
        problems.append(
            f"errors is {type(root.get('errors')).__name__}, expected list"
        )
    return problems


def failure_violations(run: CaseRun) -> list[str]:
    problems = [] if run.rc == 1 else [f"rc={run.rc}, expected 1"]
    root, parse_problems = _parse_root(run)
    problems.extend(parse_problems)
    if root is None:
        return problems
    if root.get("ok") is not False:
        problems.append(f"ok={root.get('ok')!r}, expected false")
    error_code = root.get("error_code")
    if not isinstance(error_code, str) or not error_code:
        problems.append("missing non-empty error_code")
    return problems


def _run_case(label: str, kind: str, argv: tuple[str, ...], runner: Runner,
              validator: Validator) -> CaseOutcome:
    try:
        run = runner(argv)
    except (OSError, subprocess.TimeoutExpired) as exc:
        problem = f"execution failed: {type(exc).__name__}: {exc}"
        return CaseOutcome(label, kind, None, (problem,))
    return CaseOutcome(label, kind, run.rc, tuple(validator(run)))


def run_canary(runner: Runner | None = None) -> list[CaseOutcome]:
    execute = run_cli_case if runner is None else runner
    outcomes = [
        _run_case(label, "success", argv, execute, success_violations)
        for label, argv in CANARY_SUCCESS_CASES
    ]
    label, argv = CANARY_FAILURE_CASE
    outcomes.append(
        _run_case(label, "failure", argv, execute, failure_violations)
    )
    return outcomes


def render_canary(outcomes: list[CaseOutcome]) -> bool:
    print("P182.1b canary envelope gate (6 success + 1 failure, scheduler_minimal)")
    for outcome in outcomes:
        verdict = "PASS" if outcome.passed else "FAIL"
        rc = "-" if outcome.rc is None else str(outcome.rc)
        print(f"{verdict}\t{outcome.label}\trc={rc}")
        for problem in outcome.problems:
            print(f"  - {problem}")
    passed = sum(1 for outcome in outcomes if outcome.passed)
    ok = passed == len(outcomes)
    print(f"canary: {'PASS' if ok else 'FAIL'} ({passed}/{len(outcomes)})")
    return ok


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--inventory", action="store_true",
                      help="read-only inventory (default)")
    mode.add_argument("--canary", action="store_true",
                      help="run the 6 success + 1 failure envelope canary")
    parser.add_argument("--json", action="store_true",
                        help="machine-readable inventory output")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.canary:
        if args.json:
            parser.error("--json is not supported with --canary")
        return 0 if render_canary(run_canary()) else 1
    data = inventory()
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        render_text(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
