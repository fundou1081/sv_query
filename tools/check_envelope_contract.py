#!/usr/bin/env python3
"""check_envelope_contract.py — P182.1a inventory + P182.1b canary + P182.1c matrix
+ P182.1d failure inventory + P182.1f failure contract.

Five explicit modes:

- ``--inventory`` (default): read-only, static; reads registry/JSON_CONTRACT and
  prints the envelope surface. It does not execute any command.
- ``--canary``: executes exactly 6 success cases + 1 failure case on the
  scheduler_minimal fixture and gates the standard envelope.
- ``--matrix-core``: executes the 26 core standard success cases from an
  explicit manifest (command + argv + real fixture). Failure/unknown/truncated,
  direct and exp commands are out of scope for P182.1c phase 1.
- ``--failure-inventory``: executes one explicit failure input per core standard
  command and records rc/ok/error_code/errors/result plus a descriptive
  classification. Read-only and non-gating: observed inconsistencies never
  change the exit code. Commands without a legitimate failure input are marked
  ``NO_FAILURE_INPUT`` with a reason.
- ``--matrix-failure``: gating mode over the same 26-case failure manifest.
  Non-allowlisted commands must exit rc=1 with ``ok=false``. The four hybrid
  exceptions (``drivers`` / ``loads`` / ``trace evidence`` / ``trace profile``)
  must exit rc=0 with ``ok=false``, a non-empty ``errors`` list, and
  ``E_SIGNAL_NOT_FOUND`` on every entry. Any violation prints FAIL and exits 1.

Usage:
    python3 tools/check_envelope_contract.py --inventory
    python3 tools/check_envelope_contract.py --inventory --json
    python3 tools/check_envelope_contract.py --canary
    python3 tools/check_envelope_contract.py --matrix-core
    python3 tools/check_envelope_contract.py --failure-inventory
    python3 tools/check_envelope_contract.py --failure-inventory --json
    python3 tools/check_envelope_contract.py --matrix-failure
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from _bootstrap import ensure_src_first  # noqa: E402

ensure_src_first()

from sv_query.cli._registry import ALIASES, COMMANDS, JSON_CONTRACT  # noqa: E402


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

# P182.1c — every fixture below is an existing repository fixture; each argv was
# taken from an existing test or docs invocation. No generated/one-off data.
FIX_SCHEDULER = "sim/tests/fixtures/scheduler_minimal/filelist.f"
FIX_SYNC_FIFO = "sim/tests/integration/dataflow_fixtures/sync_fifo.sv"
FIX_MIXED = "sim/tests/fixtures/mixed_corpus/env_nested_constraint.sv"
FIX_CONSTRAINT = "sim/tests/fixtures/constraint_neighborhood.sv"
FIX_STRUCT = "sim/tests/fixtures/json_contract/struct.sv"
FIX_BITSLICE = "sim/tests/fixtures/json_contract/bitslice.sv"
FIX_M3 = "sim/tests/fixtures/minimal_3module/filelist.f"
FIX_ARCH = "sim/tests/fixtures/arch_pair.sv"
FIX_TB = "sim/tests/fixtures/tb_join_tb.sv"
FIX_TB_RTL = "sim/tests/fixtures/tb_join_rtl.sv"
MATRIX_TB_JOIN_TAG = "p182_1c_tb_join"
VERIFY_CLAIM = (
    '{"type": "connection", "instance": "top.u", "port": "a", '
    '"internal": "top.u.a"}'
)


@dataclass(frozen=True)
class MatrixCase:
    """One explicit core-standard success case."""

    command: str
    argv: tuple[str, ...]
    fixture: str
    setup: tuple[tuple[str, ...], ...] = ()
    support_fixtures: tuple[str, ...] = ()
    uncovered_reason: str | None = None


CORE_SUCCESS_MANIFEST: tuple[MatrixCase, ...] = (
    MatrixCase(
        "drivers",
        ("drivers", "Scheduler_minimal.s0_reg", "--filelist", FIX_SCHEDULER, "--json"),
        FIX_SCHEDULER,
    ),
    MatrixCase(
        "loads",
        ("loads", "Scheduler_minimal.s0_reg", "--filelist", FIX_SCHEDULER, "--json"),
        FIX_SCHEDULER,
    ),
    MatrixCase(
        "trace evidence",
        ("trace", "evidence", "sync_fifo.reg_stage1", "-f", FIX_SYNC_FIFO, "--json"),
        FIX_SYNC_FIFO,
    ),
    MatrixCase(
        "trace profile",
        ("trace", "profile", "sync_fifo.data_out", "-f", FIX_SYNC_FIFO, "--json"),
        FIX_SYNC_FIFO,
    ),
    MatrixCase(
        "trace lookup",
        ("trace", "lookup", "--path", "sync_fifo.data_out", "-f", FIX_SYNC_FIFO, "--json"),
        FIX_SYNC_FIFO,
    ),
    MatrixCase(
        "trace manifest",
        ("trace", "manifest", "--path", "sync_fifo.data_out", "-f", FIX_SYNC_FIFO, "--json"),
        FIX_SYNC_FIFO,
    ),
    MatrixCase(
        "trace constraints",
        ("trace", "constraints", "packet.addr", "-f", FIX_MIXED, "--json"),
        FIX_MIXED,
    ),
    MatrixCase(
        "trace constraint-neighborhood",
        ("trace", "constraint-neighborhood", "rnd_item.a", "-f", FIX_CONSTRAINT, "--json"),
        FIX_CONSTRAINT,
    ),
    MatrixCase(
        "trace tb-join",
        ("trace", "tb-join", "tb_item.rcont", "-f", FIX_TB,
         "--from-snapshot", MATRIX_TB_JOIN_TAG, "--json"),
        FIX_TB,
        setup=(
            ("snapshot", "save", FIX_TB_RTL, "--tag", MATRIX_TB_JOIN_TAG, "--json"),
        ),
        support_fixtures=(FIX_TB_RTL,),
    ),
    MatrixCase(
        "trace frontier",
        ("trace", "frontier", "top.w", "--direction", "fanout", "-f", FIX_ARCH, "--json"),
        FIX_ARCH,
    ),
    MatrixCase(
        "trace constraint-chain",
        ("trace", "constraint-chain", "rnd_item.a", "rnd_item.d",
         "-f", FIX_CONSTRAINT, "--json"),
        FIX_CONSTRAINT,
    ),
    MatrixCase(
        "trace covergroups",
        ("trace", "covergroups", "-f", FIX_MIXED, "--json"),
        FIX_MIXED,
    ),
    MatrixCase(
        "trace coverpoints",
        ("trace", "coverpoints", "top.e.p.addr", "-f", FIX_MIXED, "--json"),
        FIX_MIXED,
    ),
    MatrixCase(
        "trace covergroup",
        ("trace", "covergroup", "cg_env", "--instance", "top.e", "-f", FIX_MIXED, "--json"),
        FIX_MIXED,
    ),
    MatrixCase(
        "controlflow analyze",
        ("controlflow", "analyze", "Scheduler_minimal.s0_reg",
         "--filelist", FIX_SCHEDULER, "--json"),
        FIX_SCHEDULER,
    ),
    MatrixCase(
        "controlflow list-conditioned",
        ("controlflow", "list-conditioned", "--filelist", FIX_SCHEDULER, "--json"),
        FIX_SCHEDULER,
    ),
    MatrixCase(
        "dataflow analyze",
        ("dataflow", "analyze", "sync_fifo.reg_stage1", "sync_fifo.data_out",
         "-f", FIX_SYNC_FIFO, "--json"),
        FIX_SYNC_FIFO,
    ),
    MatrixCase(
        "verify consistency",
        ("verify", "consistency", "-f", FIX_STRUCT, "--json"),
        FIX_STRUCT,
    ),
    MatrixCase(
        "verify claim",
        ("verify", "claim", "-f", FIX_STRUCT, "--claim", VERIFY_CLAIM, "--json"),
        FIX_STRUCT,
    ),
    MatrixCase(
        "verify structural",
        ("verify", "structural", "-f", FIX_STRUCT, "--json"),
        FIX_STRUCT,
    ),
    MatrixCase(
        "scope",
        ("scope", "top", "-f", FIX_STRUCT, "--json"),
        FIX_STRUCT,
    ),
    MatrixCase(
        "stats",
        ("stats", "--filelist", FIX_SCHEDULER, "--json"),
        FIX_SCHEDULER,
    ),
    MatrixCase(
        "graph nodes",
        ("graph", "nodes", "--filelist", FIX_SCHEDULER, "--json"),
        FIX_SCHEDULER,
    ),
    MatrixCase(
        "graph edges",
        ("graph", "edges", "--filelist", FIX_SCHEDULER, "--json"),
        FIX_SCHEDULER,
    ),
    MatrixCase(
        "filelist prune",
        ("filelist", "prune", "--filelist", FIX_M3, "--top", "top_minimal", "--json"),
        FIX_M3,
    ),
    MatrixCase(
        "graph subgraph",
        ("graph", "subgraph", "sync_fifo.data_out", "-f", FIX_SYNC_FIFO,
         "--depth", "1", "--json"),
        FIX_SYNC_FIFO,
    ),
)


# P182.1d — one explicit minimal failure input per core standard command.
# Fixtures are existing repository files where the failure is a semantic bad
# argument; ``fixture`` is None when the failure itself is a missing source or
# filelist and no existing fixture is consumed. Nothing is invented: every
# failure below was observed on the current tree before being recorded.
FAILURE_MISSING_FILE = "does_not_exist_p182_1d.sv"
FAILURE_MISSING_FILELIST = "does_not_exist_p182_1d.f"
FAILURE_SNAPSHOT_TAG = "no_such_snapshot_p182_1d"


@dataclass(frozen=True)
class FailureCase:
    """One explicit core-standard failure input (observation, not a contract)."""

    command: str
    argv: tuple[str, ...]
    fixture: str | None = None
    no_failure_reason: str | None = None


CORE_FAILURE_MANIFEST: tuple[FailureCase, ...] = (
    FailureCase(
        "drivers",
        ("drivers", "NoSuchSignal", "--filelist", FIX_SCHEDULER, "--json"),
        FIX_SCHEDULER,
    ),
    FailureCase(
        "loads",
        ("loads", "NoSuchSignal", "--filelist", FIX_SCHEDULER, "--json"),
        FIX_SCHEDULER,
    ),
    FailureCase(
        "trace evidence",
        ("trace", "evidence", "NoSuchSignal", "-f", FIX_SYNC_FIFO, "--json"),
        FIX_SYNC_FIFO,
    ),
    FailureCase(
        "trace profile",
        ("trace", "profile", "NoSuchSignal", "-f", FIX_SYNC_FIFO, "--json"),
        FIX_SYNC_FIFO,
    ),
    FailureCase(
        "trace lookup",
        ("trace", "lookup", "--path", "sync_fifo.data_out",
         "-f", FAILURE_MISSING_FILE, "--json"),
    ),
    FailureCase(
        "trace manifest",
        ("trace", "manifest", "--path", "sync_fifo.data_out",
         "-f", FAILURE_MISSING_FILE, "--json"),
    ),
    FailureCase(
        "trace constraints",
        ("trace", "constraints", "NoSuchItem", "-f", FIX_MIXED, "--json"),
        FIX_MIXED,
    ),
    FailureCase(
        "trace constraint-neighborhood",
        ("trace", "constraint-neighborhood", "NoSuchItem", "-f", FIX_CONSTRAINT, "--json"),
        FIX_CONSTRAINT,
    ),
    FailureCase(
        "trace tb-join",
        ("trace", "tb-join", "tb_item.rcont", "-f", FIX_TB,
         "--from-snapshot", FAILURE_SNAPSHOT_TAG, "--json"),
        FIX_TB,
    ),
    FailureCase(
        "trace frontier",
        ("trace", "frontier", "top.nope", "--direction", "fanout",
         "-f", FIX_ARCH, "--json"),
        FIX_ARCH,
    ),
    FailureCase(
        "trace constraint-chain",
        ("trace", "constraint-chain", "rnd_item.nope", "rnd_item.d",
         "-f", FIX_CONSTRAINT, "--json"),
        FIX_CONSTRAINT,
    ),
    FailureCase(
        "trace covergroups",
        ("trace", "covergroups", "-f", FAILURE_MISSING_FILE, "--json"),
    ),
    FailureCase(
        "trace coverpoints",
        ("trace", "coverpoints", "top.e.nope", "-f", FIX_MIXED, "--json"),
        FIX_MIXED,
    ),
    FailureCase(
        "trace covergroup",
        ("trace", "covergroup", "no_such_cg", "--instance", "top.e",
         "-f", FIX_MIXED, "--json"),
        FIX_MIXED,
    ),
    FailureCase(
        "controlflow analyze",
        ("controlflow", "analyze", "NoSuchSignal",
         "--filelist", FIX_SCHEDULER, "--json"),
        FIX_SCHEDULER,
    ),
    FailureCase(
        "controlflow list-conditioned",
        ("controlflow", "list-conditioned", "--filelist", FAILURE_MISSING_FILELIST, "--json"),
    ),
    FailureCase(
        "dataflow analyze",
        ("dataflow", "analyze", "NoSuchSignal", "sync_fifo.data_out",
         "-f", FIX_SYNC_FIFO, "--json"),
        FIX_SYNC_FIFO,
    ),
    FailureCase(
        "verify consistency",
        ("verify", "consistency", "-f", FAILURE_MISSING_FILE, "--json"),
    ),
    FailureCase(
        "verify claim",
        ("verify", "claim", "-f", FIX_STRUCT, "--claim", "{bad json", "--json"),
        FIX_STRUCT,
    ),
    FailureCase(
        "verify structural",
        ("verify", "structural", "-f", FAILURE_MISSING_FILE, "--json"),
    ),
    FailureCase(
        "scope",
        ("scope", "top.nope", "-f", FIX_STRUCT, "--json"),
        FIX_STRUCT,
    ),
    FailureCase(
        "stats",
        ("stats", "--file", FAILURE_MISSING_FILE, "--json"),
    ),
    FailureCase(
        "graph nodes",
        ("graph", "nodes", "--filelist", FAILURE_MISSING_FILELIST, "--json"),
    ),
    FailureCase(
        "graph edges",
        ("graph", "edges", "--filelist", FAILURE_MISSING_FILELIST, "--json"),
    ),
    FailureCase(
        "filelist prune",
        ("filelist", "prune", "--filelist", FIX_M3, "--top", "top_minimal",
         "--output", "p182_1d_bad_output.txt", "--json"),
        FIX_M3,
    ),
    FailureCase(
        "graph subgraph",
        ("graph", "subgraph", "sync_fifo.nope", "-f", FIX_SYNC_FIFO,
         "--depth", "1", "--json"),
        FIX_SYNC_FIFO,
    ),
)


@dataclass(frozen=True)
class CaseRun:
    rc: int
    stdout: str
    stderr: str


Runner = Callable[[tuple[str, ...]], CaseRun]
MatrixRunner = Callable[[tuple[str, ...], dict[str, str] | None], CaseRun]
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


def run_cli_case_with_env(argv: tuple[str, ...],
                          env: dict[str, str] | None = None) -> CaseRun:
    proc = subprocess.run(
        [sys.executable, "run_cli.py", *argv],
        cwd=ROOT, capture_output=True, text=True, timeout=CANARY_TIMEOUT_SECONDS,
        env=env,
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
    if root.get("errors") != []:
        problems.append(
            f"errors={root.get('errors')!r}, expected empty list"
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


def core_standard_commands() -> list[str]:
    """Registry truth for P182.1c: listed core commands with a standard envelope."""
    return [c.key for c in COMMANDS
            if c.listed and c.layer == "core" and c.envelope == "standard"]


def matrix_manifest_problems() -> list[str]:
    """Static manifest checks: count, registry coverage, and real fixture files."""
    problems: list[str] = []
    names = [case.command for case in CORE_SUCCESS_MANIFEST]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        problems.append(f"duplicate manifest commands: {', '.join(duplicates)}")
    expected = set(core_standard_commands())
    actual = set(names)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        problems.append(f"missing core standard commands: {', '.join(missing)}")
    if extra:
        problems.append(f"non-core-standard commands in manifest: {', '.join(extra)}")
    if len(CORE_SUCCESS_MANIFEST) != 26:
        problems.append(
            f"manifest has {len(CORE_SUCCESS_MANIFEST)} cases, expected 26"
        )
    for case in CORE_SUCCESS_MANIFEST:
        if case.uncovered_reason:
            continue
        for rel in (case.fixture, *case.support_fixtures):
            if not (ROOT / rel).exists():
                problems.append(f"{case.command}: fixture missing: {rel}")
        if case.fixture not in case.argv:
            problems.append(
                f"{case.command}: manifest fixture {case.fixture} absent from argv"
            )
    return problems


def _setup_problem(execute: MatrixRunner, argv: tuple[str, ...],
                   env: dict[str, str]) -> str | None:
    try:
        run = execute(argv, env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"setup {' '.join(argv)} failed: {type(exc).__name__}: {exc}"
    if run.rc != 0:
        return f"setup {' '.join(argv)}: rc={run.rc}, expected 0"
    root, parse_problems = _parse_root(run)
    if root is None:
        return f"setup {' '.join(argv)}: {parse_problems[0]}"
    if root.get("ok") is not True:
        return f"setup {' '.join(argv)}: ok={root.get('ok')!r}, expected true"
    return None


def _run_matrix_case(case: MatrixCase, execute: MatrixRunner,
                     env: dict[str, str]) -> CaseOutcome:
    if case.uncovered_reason:
        return CaseOutcome(case.command, "uncovered", None,
                           (case.uncovered_reason,))
    for setup_argv in case.setup:
        problem = _setup_problem(execute, setup_argv, env)
        if problem:
            return CaseOutcome(case.command, "setup", None, (problem,))
    try:
        run = execute(case.argv, env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        problem = f"execution failed: {type(exc).__name__}: {exc}"
        return CaseOutcome(case.command, "success", None, (problem,))
    return CaseOutcome(case.command, "success", run.rc,
                       tuple(success_violations(run)))


def run_matrix_core(
    runner: MatrixRunner | None = None,
    env: dict[str, str] | None = None,
) -> list[CaseOutcome]:
    execute = run_cli_case_with_env if runner is None else runner
    if env is not None:
        return [_run_matrix_case(case, execute, env)
                for case in CORE_SUCCESS_MANIFEST]
    with tempfile.TemporaryDirectory(prefix="svq_p182_1c_") as snapshot_dir:
        run_env = dict(os.environ, SVQ_SNAPSHOT_DIR=snapshot_dir)
        return [_run_matrix_case(case, execute, run_env)
                for case in CORE_SUCCESS_MANIFEST]


def render_matrix_core(
    outcomes: list[CaseOutcome],
    manifest_problems: list[str] | None = None,
) -> bool:
    print("P182.1c core standard success matrix (26 core standard commands)")
    problems = [] if manifest_problems is None else manifest_problems
    if problems:
        print("manifest: FAIL")
        for problem in problems:
            print(f"  - {problem}")
    for outcome in outcomes:
        if outcome.kind == "uncovered":
            print(f"UNCOVERED\t{outcome.label}")
        elif outcome.kind == "setup":
            print(f"SETUP_FAIL\t{outcome.label}")
        else:
            verdict = "PASS" if outcome.passed else "FAIL"
            rc = "-" if outcome.rc is None else str(outcome.rc)
            print(f"{verdict}\t{outcome.label}\trc={rc}")
        for problem in outcome.problems:
            print(f"  - {problem}")
    passed = sum(1 for outcome in outcomes
                 if outcome.kind == "success" and outcome.passed)
    blocked = len(outcomes) - passed
    ok = not problems and passed == len(outcomes) and len(outcomes) == 26
    detail = f"{passed}/{len(outcomes)}"
    if blocked:
        detail += f", {blocked} blocked"
    print(f"matrix-core: {'PASS' if ok else 'FAIL'} ({detail})")
    return ok


# ---------------------------------------------------------------------------
# P182.1d — failure inventory (observation only, non-gating)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FailureObservation:
    """What one real CLI failure invocation returned; descriptive, not a verdict."""

    rc: int | None
    stdout_json: bool
    ok: bool | None
    error_code: str | None
    errors_present: bool
    errors_count: int | None
    result_present: bool
    classification: str
    execution_error: str | None = None

    def as_dict(self) -> dict:
        return {
            "rc": self.rc,
            "stdout_json": self.stdout_json,
            "ok": self.ok,
            "error_code": self.error_code,
            "errors_present": self.errors_present,
            "errors_count": self.errors_count,
            "result_present": self.result_present,
            "classification": self.classification,
            "execution_error": self.execution_error,
        }


@dataclass(frozen=True)
class FailureEntry:
    command: str
    argv: tuple[str, ...]
    fixture: str | None
    status: str
    reason: str | None
    observation: FailureObservation | None

    def as_dict(self) -> dict:
        return {
            "command": self.command,
            "argv": list(self.argv),
            "fixture": self.fixture,
            "status": self.status,
            "reason": self.reason,
            "observation": None if self.observation is None
                           else self.observation.as_dict(),
        }


def _classify_failure(rc: int | None, ok: bool | None, stdout_json: bool) -> str:
    """Describe rc/ok only. This is not a pass/fail contract."""
    if not stdout_json:
        return "usage_error_no_envelope" if rc == 2 else "no_json_output"
    if rc == 2:
        return "usage_error"
    if rc not in (0, None):
        return "operational_error"
    if ok is False:
        return "business_ok_false"
    if ok is True:
        return "success_not_failure"
    return "rc0_ok_unknown"


def observe_failure(run: CaseRun) -> FailureObservation:
    """Extract rc/ok/error_code/errors/result from one failure invocation."""
    try:
        root = json.loads(run.stdout)
    except json.JSONDecodeError:
        return FailureObservation(
            rc=run.rc, stdout_json=False, ok=None, error_code=None,
            errors_present=False, errors_count=None, result_present=False,
            classification=_classify_failure(run.rc, None, False),
        )
    if not isinstance(root, dict):
        return FailureObservation(
            rc=run.rc, stdout_json=False, ok=None, error_code=None,
            errors_present=False, errors_count=None, result_present=False,
            classification=_classify_failure(run.rc, None, False),
        )
    ok = root.get("ok")
    if not isinstance(ok, bool):
        ok = None
    error_code = root.get("error_code")
    if not isinstance(error_code, str) or not error_code:
        error_code = None
    errors = root.get("errors")
    errors_present = "errors" in root
    errors_count = len(errors) if isinstance(errors, list) else None
    return FailureObservation(
        rc=run.rc,
        stdout_json=True,
        ok=ok,
        error_code=error_code,
        errors_present=errors_present,
        errors_count=errors_count,
        result_present="result" in root,
        classification=_classify_failure(run.rc, ok, True),
    )


def failure_manifest_problems() -> list[str]:
    """Static manifest checks: count, registry coverage, fixtures, argv."""
    problems: list[str] = []
    names = [case.command for case in CORE_FAILURE_MANIFEST]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        problems.append(f"duplicate manifest commands: {', '.join(duplicates)}")
    expected = set(core_standard_commands())
    actual = set(names)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        problems.append(f"missing core standard commands: {', '.join(missing)}")
    if extra:
        problems.append(f"non-core-standard commands in manifest: {', '.join(extra)}")
    if len(CORE_FAILURE_MANIFEST) != 26:
        problems.append(
            f"manifest has {len(CORE_FAILURE_MANIFEST)} cases, expected 26"
        )
    for case in CORE_FAILURE_MANIFEST:
        if not case.argv:
            problems.append(f"{case.command}: empty argv")
        if case.no_failure_reason:
            continue
        if case.fixture is not None:
            if not (ROOT / case.fixture).exists():
                problems.append(f"{case.command}: fixture missing: {case.fixture}")
            if case.fixture not in case.argv:
                problems.append(
                    f"{case.command}: manifest fixture {case.fixture} absent from argv"
                )
    return problems


def _run_failure_case(case: FailureCase, execute: MatrixRunner,
                      env: dict[str, str]) -> FailureEntry:
    if case.no_failure_reason:
        return FailureEntry(case.command, case.argv, case.fixture,
                            "no_failure_input", case.no_failure_reason, None)
    try:
        run = execute(case.argv, env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        observation = FailureObservation(
            rc=None, stdout_json=False, ok=None, error_code=None,
            errors_present=False, errors_count=None, result_present=False,
            classification="execution_error",
            execution_error=f"{type(exc).__name__}: {exc}",
        )
    else:
        observation = observe_failure(run)
    return FailureEntry(case.command, case.argv, case.fixture,
                        "observed", None, observation)


def run_failure_inventory(
    runner: MatrixRunner | None = None,
    env: dict[str, str] | None = None,
) -> list[FailureEntry]:
    execute = run_cli_case_with_env if runner is None else runner
    if env is not None:
        return [_run_failure_case(case, execute, env)
                for case in CORE_FAILURE_MANIFEST]
    with tempfile.TemporaryDirectory(prefix="svq_p182_1d_") as snapshot_dir:
        run_env = dict(os.environ, SVQ_SNAPSHOT_DIR=snapshot_dir)
        return [_run_failure_case(case, execute, run_env)
                for case in CORE_FAILURE_MANIFEST]


def failure_inventory(runner: MatrixRunner | None = None,
                      env: dict[str, str] | None = None) -> dict:
    entries = run_failure_inventory(runner, env)
    observations = [e.observation for e in entries if e.observation is not None]
    classes = Counter(o.classification for o in observations)
    summary = {
        "expected_commands": 26,
        "entries": len(entries),
        "observed": len(observations),
        "no_failure_input": sum(1 for e in entries
                                if e.status == "no_failure_input"),
        "operational_error": classes.get("operational_error", 0),
        "business_ok_false": classes.get("business_ok_false", 0),
        "usage_error": (classes.get("usage_error", 0)
                        + classes.get("usage_error_no_envelope", 0)),
        "no_json_output": classes.get("no_json_output", 0),
        "execution_error": classes.get("execution_error", 0),
        "success_not_failure": classes.get("success_not_failure", 0),
        "rc0_ok_unknown": classes.get("rc0_ok_unknown", 0),
        "top_level_error_code_present": sum(1 for o in observations
                                            if o.error_code),
        "errors_key_present": sum(1 for o in observations
                                  if o.errors_present),
        "result_present": sum(1 for o in observations if o.result_present),
    }
    return {
        "inventory": "P182.1d",
        "mode": "read-only-failure-inventory",
        "manifest_problems": failure_manifest_problems(),
        "summary": summary,
        "rows": [entry.as_dict() for entry in entries],
    }


def render_failure_inventory(data: dict) -> None:
    print("P182.1d core standard failure inventory (read-only, non-gating)")
    problems = data.get("manifest_problems") or []
    if problems:
        print("manifest: PROBLEMS (informational only, exit stays 0)")
        for problem in problems:
            print(f"  - {problem}")
    print("command\trc\tok\terror_code\terrors\tresult\tclassification")
    for row in data["rows"]:
        observation = row["observation"]
        if observation is None:
            print(f"{row['command']}\t-\t-\t-\t-\t-\tNO_FAILURE_INPUT")
            print(f"  reason: {row['reason']}")
            continue
        rc = "-" if observation["rc"] is None else str(observation["rc"])
        ok = "-" if observation["ok"] is None else str(observation["ok"])
        code = observation["error_code"] or "-"
        if observation["errors_count"] is not None:
            errors = str(observation["errors_count"])
        else:
            errors = "absent" if not observation["errors_present"] else "non-list"
        result = "yes" if observation["result_present"] else "no"
        print(f"{row['command']}\t{rc}\t{ok}\t{code}\t{errors}\t{result}\t"
              f"{observation['classification']}")
        if observation["execution_error"]:
            print(f"  execution_error: {observation['execution_error']}")
    s = data["summary"]
    print(f"entries: {s['entries']}/{s['expected_commands']} "
          f"observed={s['observed']} no_failure_input={s['no_failure_input']}")
    print(f"classification: operational_error={s['operational_error']} "
          f"business_ok_false={s['business_ok_false']} "
          f"usage_error={s['usage_error']} "
          f"no_json_output={s['no_json_output']} "
          f"execution_error={s['execution_error']} "
          f"success_not_failure={s['success_not_failure']} "
          f"rc0_ok_unknown={s['rc0_ok_unknown']}")
    print(f"presence: top_level_error_code={s['top_level_error_code_present']} "
          f"errors_key={s['errors_key_present']} result={s['result_present']}")
    print("note: observations only; no pass/fail verdict and no exit-code change")


# ---------------------------------------------------------------------------
# P182.1f — strict failure contract + hybrid allowlist (gating)
# ---------------------------------------------------------------------------

# Exactly four exceptions to the strict rc=1 rule. Each one is a per-signal
# command whose not-found result is expressed per signal in ``errors[]``.
# This is an allowlist, not a claim that rc=0 is acceptable in general.
HYBRID_ALLOWLIST: tuple[str, ...] = (
    "drivers",
    "loads",
    "trace evidence",
    "trace profile",
)
HYBRID_ERROR_CODE = "E_SIGNAL_NOT_FOUND"


def strict_failure_violations(run: CaseRun) -> list[str]:
    """Strict rule: rc=1 + ok=false. Deliberately says nothing else."""
    problems = [] if run.rc == 1 else [f"rc={run.rc}, expected 1"]
    root, parse_problems = _parse_root(run)
    problems.extend(parse_problems)
    if root is None:
        return problems
    if root.get("ok") is not False:
        problems.append(f"ok={root.get('ok')!r}, expected false")
    return problems


def hybrid_failure_violations(run: CaseRun) -> list[str]:
    """Hybrid rule: rc=0 + ok=false + per-error E_SIGNAL_NOT_FOUND."""
    problems = [] if run.rc == 0 else [f"rc={run.rc}, expected 0"]
    root, parse_problems = _parse_root(run)
    problems.extend(parse_problems)
    if root is None:
        return problems
    if root.get("ok") is not False:
        problems.append(f"ok={root.get('ok')!r}, expected false")
    errors = root.get("errors")
    if not isinstance(errors, list) or not errors:
        problems.append(f"errors={errors!r}, expected non-empty list")
        return problems
    for index, error in enumerate(errors):
        code = error.get("error_code") if isinstance(error, dict) else None
        if code != HYBRID_ERROR_CODE:
            problems.append(
                f"errors[{index}].error_code={code!r}, expected "
                f"{HYBRID_ERROR_CODE!r}"
            )
    return problems


def failure_contract_manifest_problems() -> list[str]:
    """Static checks for the gating mode; reuses the P182.1d manifest checks."""
    problems = failure_manifest_problems()
    names = [case.command for case in CORE_FAILURE_MANIFEST]
    allowlist_missing = [name for name in HYBRID_ALLOWLIST if name not in names]
    if allowlist_missing:
        problems.append(
            "hybrid allowlist commands absent from failure manifest: "
            + ", ".join(allowlist_missing)
        )
    return problems


def _run_failure_contract_case(case: FailureCase, execute: MatrixRunner,
                               env: dict[str, str]) -> CaseOutcome:
    if case.no_failure_reason:
        return CaseOutcome(
            case.command, "no_failure_input", None,
            (f"no failure input recorded: {case.no_failure_reason}",),
        )
    hybrid = case.command in HYBRID_ALLOWLIST
    kind = "hybrid" if hybrid else "strict"
    validator = hybrid_failure_violations if hybrid else strict_failure_violations
    try:
        run = execute(case.argv, env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        problem = f"execution failed: {type(exc).__name__}: {exc}"
        return CaseOutcome(case.command, kind, None, (problem,))
    return CaseOutcome(case.command, kind, run.rc, tuple(validator(run)))


def run_matrix_failure(
    runner: MatrixRunner | None = None,
    env: dict[str, str] | None = None,
) -> list[CaseOutcome]:
    execute = run_cli_case_with_env if runner is None else runner
    if env is not None:
        return [_run_failure_contract_case(case, execute, env)
                for case in CORE_FAILURE_MANIFEST]
    with tempfile.TemporaryDirectory(prefix="svq_p182_1f_") as snapshot_dir:
        run_env = dict(os.environ, SVQ_SNAPSHOT_DIR=snapshot_dir)
        return [_run_failure_contract_case(case, execute, run_env)
                for case in CORE_FAILURE_MANIFEST]


def render_matrix_failure(
    outcomes: list[CaseOutcome],
    manifest_problems: list[str] | None = None,
) -> bool:
    print("P182.1f failure contract matrix (26 core standard commands)")
    problems = [] if manifest_problems is None else manifest_problems
    if problems:
        print("manifest: FAIL")
        for problem in problems:
            print(f"  - {problem}")
    for outcome in outcomes:
        if outcome.kind == "no_failure_input":
            print(f"NO_FAILURE_INPUT\t{outcome.label}")
        else:
            verdict = "PASS" if outcome.passed else "FAIL"
            rc = "-" if outcome.rc is None else str(outcome.rc)
            print(f"{verdict}\t{outcome.label}\t{outcome.kind}\trc={rc}")
        for problem in outcome.problems:
            print(f"  - {problem}")
    passed = sum(1 for outcome in outcomes if outcome.passed)
    ok = (not problems and passed == len(outcomes)
          and len(outcomes) == 26)
    print(f"matrix-failure: {'PASS' if ok else 'FAIL'} "
          f"({passed}/{len(outcomes)})")
    return ok


# ---------------------------------------------------------------------------
# P182.1e — direct envelope contract (static, read-only, no CLI execution)
# ---------------------------------------------------------------------------
DIRECT_ROOT_EXPECTATIONS: dict[str, str] = {
    "instances": "object",
    "connections": "object",
    "hierarchy": "object",
    "params": "object",
    "ports": "object",
    "class": "object",
    "paths": "object",
    "search": "object",
    "capabilities": "object",
    "snapshot save": "object",
    "snapshot list": "list_or_object",
    "snapshot compare": "object",
    "snapshot delete": "object",
}


def direct_contract_rows() -> list[dict]:
    rows = []
    for spec in COMMANDS:
        if not spec.listed or spec.envelope != "direct":
            continue
        contract = _contract(spec.key)
        rows.append({
            "name": spec.key,
            "root": DIRECT_ROOT_EXPECTATIONS.get(spec.key, "unknown"),
            "contract": bool(contract),
            "contract_keys": sorted(contract) if contract else [],
        })
    return rows


def direct_contract_problems() -> list[str]:
    rows = direct_contract_rows()
    names = [row["name"] for row in rows]
    problems = []
    if len(rows) != 13:
        problems.append(f"direct commands: {len(rows)}, expected 13")
    if len(set(names)) != len(names):
        problems.append("duplicate direct command")
    expected = set(DIRECT_ROOT_EXPECTATIONS)
    missing = sorted(expected - set(names))
    extra = sorted(set(names) - expected)
    if missing:
        problems.append("missing direct contract rows: " + ", ".join(missing))
    if extra:
        problems.append("unexpected direct commands: " + ", ".join(extra))
    for row in rows:
        if not row["contract"]:
            problems.append(f"{row['name']}: missing JSON_CONTRACT entry")
        if row["root"] == "unknown":
            problems.append(f"{row['name']}: no declared root kind")
    return problems


def render_direct_contract(rows: list[dict], problems: list[str]) -> bool:
    print("P182.1e direct envelope contract (static; no command execution)")
    for row in rows:
        print(f"{row['name']}\troot={row['root']}\tcontract={row['contract']}")
    for problem in problems:
        print(f"  - {problem}")
    ok = not problems
    print(f"direct-contract: {'PASS' if ok else 'FAIL'} ({len(rows)}/13)")
    return ok


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--inventory", action="store_true",
                      help="read-only inventory (default)")
    mode.add_argument("--canary", action="store_true",
                      help="run the 6 success + 1 failure envelope canary")
    mode.add_argument("--matrix-core", action="store_true",
                      help="run the 26 core standard success matrix")
    mode.add_argument("--failure-inventory", action="store_true",
                      help="record one failure input per core standard command "
                           "(observation only, non-gating)")
    mode.add_argument("--matrix-failure", action="store_true",
                      help="gate rc/ok/error_code for the 26 failure inputs "
                           "(strict + 4-command hybrid allowlist)")
    mode.add_argument("--direct-contract", action="store_true",
                      help="static direct-envelope contract check (no CLI execution)")
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
    if args.matrix_core:
        if args.json:
            parser.error("--json is not supported with --matrix-core")
        outcomes = run_matrix_core()
        problems = matrix_manifest_problems()
        return 0 if render_matrix_core(outcomes, problems) else 1
    if args.failure_inventory:
        data = failure_inventory()
        if args.json:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            render_failure_inventory(data)
        return 0
    if args.matrix_failure:
        if args.json:
            parser.error("--json is not supported with --matrix-failure")
        outcomes = run_matrix_failure()
        problems = failure_contract_manifest_problems()
        return 0 if render_matrix_failure(outcomes, problems) else 1
    if args.direct_contract:
        if args.json:
            parser.error("--json is not supported with --direct-contract")
        rows = direct_contract_rows()
        problems = direct_contract_problems()
        return 0 if render_direct_contract(rows, problems) else 1
    data = inventory()
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        render_text(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
