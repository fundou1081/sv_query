#!/usr/bin/env python3
"""P158.4 — executable SPI corpus runner.

Reads `tools/agent/task_corpora/opentitan_spi_tasks.json`, maps every task
`kind` to a concrete public-CLI invocation (including `--from-snapshot`), and
asserts the declared `expected` outcome against the CLI's JSON output.

Design rules (SEMANTIC_CONTRACTS §8, DISCIPLINE §0.1):

* **No silent skip.** A malformed task (unknown `kind`, missing required
  field, unknown `expected` key) is a hard failure of that task — never a
  skip and never a pass.
* **Expected values are contract-anchored.** Every `expected` key maps to a
  documented JSON field of the CLI output (see `EXPECTED_SPECS`). A key that
  is not in the spec is an error, so a typo cannot silently pass.
* **Independent oracle.** The `expected` values in the corpus JSON are not
  generated from this runner; they are independently checked against the
  OpenTitan RTL (see `docs/validation/P152_SPI_CORPUS_2026-11-10.md`).
* **Bounded.** Each CLI invocation has an explicit timeout; a timeout is a
  failure, never a pass.

Usage:
    python3 tools/agent/run_spi_corpus.py            # human readable
    python3 tools/agent/run_spi_corpus.py --json     # machine readable
    python3 tools/agent/run_spi_corpus.py --task SPI-T2
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "run_cli.py"
CORPUS = ROOT / "tools" / "agent" / "task_corpora" / "opentitan_spi_tasks.json"

DEFAULT_TIMEOUT = 300


class TaskError(Exception):
    """Malformed task definition — a hard failure, never a skip."""


# ---------------------------------------------------------------------------
# CLI invocation per task kind
# ---------------------------------------------------------------------------
#
# Each builder returns (argv, extractor). The extractor maps the CLI JSON
# payload to a flat dict of "observed" values, which is then compared with the
# task's `expected` dict using the per-kind expected spec.


def _drivers_argv(task: dict, snapshot: str) -> list[str]:
    signal = task.get("signal")
    if not isinstance(signal, str) or not signal:
        raise TaskError("kind=direct_neighbors requires a non-empty 'signal'")
    return ["drivers", signal, "--from-snapshot", snapshot]


def _loads_argv(task: dict, snapshot: str) -> list[str]:
    signal = task.get("signal")
    if not isinstance(signal, str) or not signal:
        raise TaskError("kind=direct_neighbors requires a non-empty 'signal'")
    return ["loads", signal, "--from-snapshot", snapshot]


def _paths_argv(task: dict, snapshot: str) -> list[str]:
    src, dst = task.get("from"), task.get("to")
    if not isinstance(src, str) or not isinstance(dst, str) or not src or not dst:
        raise TaskError("kind=directed_path requires non-empty 'from' and 'to'")
    # `paths` has three output modes (src/cli/core/semantic/paths.py):
    #   default   -> {found, hop_count, path}
    #   --all     -> {count, all_paths}
    #   --canonical -> {found, hop_count, path, candidate_count}
    # The corpus pins the mode so `expected` is unambiguous: `canonical` is the
    # only mode that reports found + hop_count + candidate_count together and
    # it uses a deterministic policy ("max_nodes_then_lexicographic").
    mode = task.get("mode", "canonical")
    if mode not in ("canonical", "one", "all"):
        raise TaskError(f"kind=directed_path: unknown mode {mode!r} "
                        f"(canonical|one|all)")
    argv = ["paths", src, dst, "--directed"]
    if mode == "canonical":
        argv.append("--canonical")
    elif mode == "all":
        argv.append("--all")
    argv += ["--from-snapshot", snapshot]
    return argv


def _verify_claim_argv(task: dict, snapshot: str) -> list[str]:
    kind = task.get("kind")
    claim_type = task.get("claim_type")
    if claim_type == "path":
        src, dst = task.get("from"), task.get("to")
        if not isinstance(src, str) or not isinstance(dst, str):
            raise TaskError(f"kind={kind} requires non-empty 'from' and 'to'")
        claim = {"type": "path", "from": src, "to": dst}
    elif claim_type == "driver":
        signal, driver = task.get("signal"), task.get("driver")
        if not isinstance(signal, str) or not isinstance(driver, str):
            raise TaskError(f"kind={kind} requires non-empty 'signal' and 'driver'")
        claim = {"type": "driver", "signal": signal, "driver": driver}
    else:
        raise TaskError(f"kind={kind} needs 'claim_type' (path|driver), got {claim_type!r}")
    return ["verify", "claim", "--claim", json.dumps(claim),
            "--from-snapshot", snapshot]


def _frontier_argv(task: dict, snapshot: str) -> list[str]:
    signal = task.get("signal")
    if not isinstance(signal, str) or not signal:
        raise TaskError("kind=frontier requires a non-empty 'signal'")
    return ["trace", "frontier", signal, "--from-snapshot", snapshot]


def _unknown_argv(task: dict, snapshot: str) -> list[str]:
    signal = task.get("signal")
    if not isinstance(signal, str) or not signal:
        raise TaskError("kind=unknown requires a non-empty 'signal'")
    return ["drivers", signal, "--from-snapshot", snapshot]


def _consistency_argv(task: dict, snapshot: str) -> list[str]:
    return ["verify", "consistency", "--checks", "connection",
            "--from-snapshot", snapshot]


# ---------------------------------------------------------------------------
# Extraction: CLI JSON payload -> flat "observed" dict
# ---------------------------------------------------------------------------


def _first_signal(payload: dict) -> dict:
    signals = ((payload.get("result") or {}).get("signals") or [])
    if not signals:
        raise TaskError("CLI payload has no result.signals[0]")
    return signals[0]


def _extract_drivers(payload: dict) -> dict:
    """`drivers` reports the number of drivers as `driver_count`."""
    sig = _first_signal(payload)
    return {"driver_count": sig.get("driver_count")}


def _extract_loads(payload: dict) -> dict:
    """`loads` reports the number of consumers as `count` (there is no
    `load_count` field; only the drivers payload carries `driver_count`)."""
    sig = _first_signal(payload)
    return {"count": sig.get("count")}


def _extract_paths(payload: dict) -> dict:
    """Normalise the three `paths` output modes to one flat dict.

    * `canonical` / default: `found` + `hop_count` + `candidate_count`
    * `--all`: only `count` (candidate count) and `all_paths`; `found` is
      derived as "at least one candidate", `hop_count` from the first
      candidate (edges = len(nodes) - 1).
    """
    all_paths = payload.get("all_paths") or []
    hop_count = payload.get("hop_count")
    if hop_count is None and all_paths:
        hop_count = len(all_paths[0]) - 1
    candidate_count = payload.get("candidate_count")
    if candidate_count is None:
        candidate_count = payload.get("count")
    found = payload.get("found")
    if found is None:
        found = bool(all_paths)
    return {
        "found": bool(found),
        "hop_count": hop_count,
        "candidate_count": candidate_count,
    }


def _extract_verify_claim(payload: dict) -> dict:
    return {"status": (payload.get("result") or {}).get("status")}


def _extract_frontier(payload: dict) -> dict:
    summary = (payload.get("result") or {}).get("summary") or {}
    return {"frontier_count": summary.get("frontier_count")}


def _extract_unknown(payload: dict) -> dict:
    errors = payload.get("errors") or []
    text = " ".join([
        str(payload.get("error") or ""),
        str((payload.get("result") or {}).get("error") or ""),
        " ".join(str(e.get("error") or "") for e in errors),
    ])
    return {"ok": payload.get("ok"), "error_text": text}


def _extract_consistency(payload: dict) -> dict:
    result = payload.get("result") or {}
    checks = {c.get("check"): c for c in (result.get("checks") or [])}
    conn = checks.get("connection")
    if conn is None:
        raise TaskError("verify consistency output has no 'connection' check")
    return {
        "status": conn.get("status"),
        "checked": conn.get("checked"),
        "violations": result.get("total_violations"),
    }


# ---------------------------------------------------------------------------
# Expected specs: which `expected` keys each kind accepts, and how they are
# compared. Unknown keys are an error (no silent pass on typos).
# ---------------------------------------------------------------------------

# key -> (observed key, comparison)
#   "eq"   exact equality
#   "gte"  observed >= expected
#   "contains"  substring of observed text
EXPECTED_SPECS: dict[str, dict[str, tuple[str, str]]] = {
    "direct_neighbors": {
        "driver_count": ("driver_count", "eq"),
        "count": ("count", "eq"),
    },
    "directed_path": {
        "found": ("found", "eq"),
        "hop_count": ("hop_count", "eq"),
        "candidate_count": ("candidate_count", "eq"),
    },
    "verify_path": {
        "status": ("status", "eq"),
    },
    "verify_driver": {
        "status": ("status", "eq"),
    },
    "frontier": {
        "frontier_count_gte": ("frontier_count", "gte"),
    },
    "unknown": {
        "ok": ("ok", "eq"),
        "error_contains": ("error_text", "contains"),
    },
    "consistency_connection": {
        "status": ("status", "eq"),
        "checked": ("checked", "eq"),
        "violations": ("violations", "eq"),
    },
}


def _cmp_eq(actual: Any, expected: Any, key: str) -> str | None:
    if actual != expected:
        return f"{key}: expected {expected!r}, got {actual!r}"
    return None


def _cmp_gte(actual: Any, expected: Any, key: str) -> str | None:
    if actual is None:
        return f"{key}: expected >= {expected!r}, got None"
    if actual < expected:
        return f"{key}: expected >= {expected!r}, got {actual!r}"
    return None


def _cmp_contains(actual: Any, expected: Any, key: str) -> str | None:
    if not isinstance(actual, str):
        return f"{key}: expected text field, got {actual!r}"
    if expected not in actual:
        return f"{key}: expected text containing {expected!r}, got {actual!r}"
    return None


_COMPARATORS = {"eq": _cmp_eq, "gte": _cmp_gte, "contains": _cmp_contains}


def _compare(expected: dict, observed: dict, spec: dict[str, tuple[str, str]]) -> list[str]:
    """Return a list of failure messages (empty == pass)."""
    failures: list[str] = []
    unknown = sorted(set(expected) - set(spec))
    if unknown:
        failures.append(f"unknown expected key(s) for this kind: {unknown}; "
                        f"allowed: {sorted(spec)}")
    for key, value in expected.items():
        if key not in spec:
            continue
        obs_key, mode = spec[key]
        if obs_key not in observed:
            failures.append(f"{key}: observed field '{obs_key}' missing from CLI output")
            continue
        comparator = _COMPARATORS.get(mode)
        if comparator is None:  # pragma: no cover - guarded by EXPECTED_SPECS
            raise TaskError(f"unknown comparison mode {mode!r}")
        failure = comparator(observed[obs_key], value, key)
        if failure:
            failures.append(failure)
    return failures


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _fmt_command(argv: list[str]) -> str:
    """Render a CLI argv as a copy-pasteable command (shell-quoted)."""
    return " ".join(shlex.quote(a) for a in argv)


def _run_cli(args: list[str], env: dict, timeout: int) -> tuple[dict | None, str]:
    try:
        proc = subprocess.run(
            [sys.executable, str(CLI), *args, "--json"],
            capture_output=True, text=True, cwd=ROOT, env=env, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, f"timeout after {timeout}s"
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None, (f"non-JSON output (rc={proc.returncode}): "
                      f"{proc.stdout[-300:]} {proc.stderr[-300:]}")
    return data, ""


def _validate_task(task: dict) -> None:
    if not isinstance(task, dict):
        raise TaskError(f"task is not an object: {task!r}")
    tid = task.get("id")
    if not isinstance(tid, str) or not tid:
        raise TaskError("task missing a non-empty string 'id'")
    kind = task.get("kind")
    if kind not in EXPECTED_SPECS:
        raise TaskError(f"{tid}: unknown kind {kind!r}; "
                        f"known kinds: {sorted(EXPECTED_SPECS)}")
    expected = task.get("expected")
    if not isinstance(expected, dict) or not expected:
        raise TaskError(f"{tid}: missing or empty 'expected' object")
    unknown = sorted(set(expected) - set(EXPECTED_SPECS[kind]))
    if unknown:
        raise TaskError(f"{tid}: unknown expected key(s) {unknown} for kind {kind!r}; "
                        f"allowed: {sorted(EXPECTED_SPECS[kind])}")


# kind -> (argv builder, extractor) for the kinds that need one CLI call.
_SINGLE_COMMAND_KINDS: dict[str, tuple[Any, Any]] = {
    "directed_path": (_paths_argv, _extract_paths),
    "verify_path": (_verify_claim_argv, _extract_verify_claim),
    "verify_driver": (_verify_claim_argv, _extract_verify_claim),
    "frontier": (_frontier_argv, _extract_frontier),
    "unknown": (_unknown_argv, _extract_unknown),
    "consistency_connection": (_consistency_argv, _extract_consistency),
}


def _run_direct_neighbors(task: dict, snapshot: str, env: dict,
                          timeout: int) -> tuple[dict, list[str], str]:
    """`direct_neighbors` needs two calls (drivers + loads)."""
    d_argv = _drivers_argv(task, snapshot)
    l_argv = _loads_argv(task, snapshot)
    d_payload, derr = _run_cli(d_argv, env, timeout)
    l_payload, lerr = _run_cli(l_argv, env, timeout)
    if derr or lerr:
        raise TaskError(f"CLI failed: {derr or lerr}")
    observed = {**_extract_drivers(d_payload), **_extract_loads(l_payload)}
    return observed, [_fmt_command(d_argv), _fmt_command(l_argv)], ""


def _run_single_command(task: dict, snapshot: str, env: dict,
                        timeout: int) -> tuple[dict, list[str], str]:
    kind = task["kind"]
    builder, extract = _SINGLE_COMMAND_KINDS[kind]
    argv = builder(task, snapshot)
    payload, err = _run_cli(argv, env, timeout)
    if err:
        raise TaskError(f"CLI failed: {err}")
    return extract(payload), [_fmt_command(argv)], ""


def run_task(task: dict, snapshot: str, env: dict, timeout: int) -> dict:
    """Run one task; return a result dict. Never raises for task-level errors."""
    tid = task.get("id", "<no-id>")
    result: dict[str, Any] = {"id": tid, "kind": task.get("kind"), "passed": False}
    try:
        _validate_task(task)
    except TaskError as e:
        result["error"] = f"malformed task: {e}"
        return result

    kind = task["kind"]
    expected = task["expected"]
    try:
        if kind == "direct_neighbors":
            observed, commands, err = _run_direct_neighbors(task, snapshot, env, timeout)
        else:
            observed, commands, err = _run_single_command(task, snapshot, env, timeout)
    except TaskError as e:
        result["error"] = f"malformed task: {e}"
        return result
    if err:
        result["error"] = err
        return result

    failures = _compare(expected, observed, EXPECTED_SPECS[kind])
    result["commands"] = commands
    result["expected"] = expected
    result["observed"] = observed
    if failures:
        result["error"] = "; ".join(failures)
        result["failures"] = failures
        return result
    result["passed"] = True
    return result


def load_corpus(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise TaskError(f"corpus file not found: {path}") from e
    except json.JSONDecodeError as e:
        raise TaskError(f"corpus file is not valid JSON: {path}: {e}") from e
    if not isinstance(data, dict) or not isinstance(data.get("tasks"), list):
        raise TaskError(f"corpus {path} has no 'tasks' list")
    return data


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the SPI task corpus (P158.4).")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--corpus", default=str(CORPUS), help="corpus JSON path")
    ap.add_argument("--snapshot-dir", default=None,
                    help="snapshot dir (default: $SVQ_SNAPSHOT_DIR)")
    ap.add_argument("--snapshot-tag", default=None,
                    help="snapshot tag (default: corpus meta.snapshot)")
    ap.add_argument("--task", action="append", default=None,
                    help="run only this task id (repeatable)")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                    help="per-CLI-invocation timeout in seconds")
    args = ap.parse_args()

    try:
        corpus = load_corpus(Path(args.corpus))
    except TaskError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    meta = corpus.get("meta") or {}
    tag = args.snapshot_tag or meta.get("snapshot")
    if not tag:
        print("ERROR: no snapshot tag (--snapshot-tag or corpus meta.snapshot)",
              file=sys.stderr)
        return 2

    snap_dir = args.snapshot_dir or os.environ.get("SVQ_SNAPSHOT_DIR") or meta.get("snapshot_dir")
    if not snap_dir:
        print("ERROR: no snapshot dir (--snapshot-dir, $SVQ_SNAPSHOT_DIR or "
              "corpus meta.snapshot_dir)", file=sys.stderr)
        return 2
    snap_path = Path(snap_dir) / f"{tag}.json"
    if not snap_path.exists():
        print(f"ERROR: snapshot not found: {snap_path}", file=sys.stderr)
        return 2

    env = {**os.environ, "SVQ_SNAPSHOT_DIR": str(snap_dir)}

    tasks = corpus["tasks"]
    if args.task:
        wanted = set(args.task)
        tasks = [t for t in tasks if isinstance(t, dict) and t.get("id") in wanted]
        if not tasks:
            print(f"ERROR: no task matched {sorted(wanted)}", file=sys.stderr)
            return 2

    results = []
    for task in tasks:
        results.append(run_task(task, tag, env, args.timeout))

    passed = sum(1 for r in results if r["passed"])
    payload = {
        "corpus": str(args.corpus),
        "snapshot_tag": tag,
        "snapshot_dir": str(snap_dir),
        "tasks": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"{passed}/{len(results)} tasks passed "
              f"(snapshot={tag} dir={snap_dir})")
        for r in results:
            mark = "PASS" if r["passed"] else "FAIL"
            print(f"  {mark} {r['id']} ({r.get('kind')})")
            if not r["passed"]:
                print(f"       error: {r.get('error', '')}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
