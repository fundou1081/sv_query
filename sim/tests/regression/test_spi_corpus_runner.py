"""P158.4 — the SPI task corpus is executable.

Three layers, all in one file so the runner contract is covered end to end:

1. **Runner self-tests** (no external project): the runner really runs the
   public CLI, a wrong `expected` fails, and a malformed task fails instead
   of being skipped.
2. **Synthetic-corpus regression**: a temp snapshot built from a small
   in-repo fixture exercises every `kind` the corpus uses.
3. **Real-corpus regression** (`opensource` + `real-corpus`): the actual
   `opentitan_spi_tasks.json` against the external SPI snapshot. Skips with
   an explicit reason **only** when the snapshot directory is absent — there
   is no permanent canonical skip.

The runner is the only implementation of "map a task kind to a CLI call";
these tests must not re-implement it.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CLI = ROOT / "run_cli.py"
RUNNER = ROOT / "tools" / "agent" / "run_spi_corpus.py"
CORPUS = ROOT / "tools" / "agent" / "task_corpora" / "opentitan_spi_tasks.json"
FIXTURE = ROOT / "sim" / "tests" / "fixtures" / "spi_corpus_fixture.sv"

# The real SPI snapshot lives outside the repo (see the corpus meta and
# docs/validation/P152_SPI_CORPUS_2026-11-10.md). Both locations are tried.
REAL_SNAPSHOT_DIRS = [
    Path("/private/tmp/opentitan_svq_spi/snapshots"),
    Path("/tmp/opentitan_svq_spi/snapshots"),
]
REAL_SNAPSHOT_TAG = "opentitan_spi"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _run_cli(args: list[str], env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), *args, "--json"],
        capture_output=True, text=True, cwd=ROOT, env=env, timeout=300,
    )


def _run_runner(corpus: Path, snapshot_dir: Path, tag: str,
                extra: list[str] | None = None) -> subprocess.CompletedProcess:
    argv = [
        sys.executable, str(RUNNER),
        "--corpus", str(corpus),
        "--snapshot-dir", str(snapshot_dir),
        "--snapshot-tag", tag,
        *(extra or []),
    ]
    return subprocess.run(argv, capture_output=True, text=True, cwd=ROOT,
                          timeout=600)

def _write_corpus(path: Path, tasks: list[dict], meta: dict | None = None) -> Path:
    path.write_text(json.dumps({"meta": meta or {}, "tasks": tasks}, indent=2),
                     encoding="utf-8")
    return path


def _make_snapshot(snapshot_dir: Path, tag: str, source: Path) -> None:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "SVQ_SNAPSHOT_DIR": str(snapshot_dir)}
    proc = _run_cli(["snapshot", "save", str(source), "--tag", tag], env)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert (snapshot_dir / f"{tag}.json").exists()


# ---------------------------------------------------------------------------
# 1. Runner self-tests (synthetic, always run)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def synthetic_snapshot(tmp_path_factory):
    """A temp snapshot built from the in-repo fixture."""
    snap_dir = tmp_path_factory.mktemp("spi_corpus_snaps")
    tag = "synthetic_spi"
    _make_snapshot(snap_dir, tag, FIXTURE)
    return snap_dir, tag


def test_runner_module_imports_and_exposes_contract():
    """The runner must be importable and expose its expected-value specs."""
    sys.path.insert(0, str(ROOT / "tools" / "agent"))
    try:
        import run_spi_corpus as runner  # noqa: PLC0415
    finally:
        sys.path.pop(0)
    assert set(runner.EXPECTED_SPECS) == {
        "direct_neighbors", "directed_path", "verify_path", "verify_driver",
        "frontier", "unknown", "consistency_connection",
    }


def test_runner_passes_on_synthetic_corpus(tmp_path, synthetic_snapshot):
    """Every corpus kind works end to end on the synthetic snapshot."""
    snap_dir, tag = synthetic_snapshot
    corpus = _write_corpus(tmp_path / "corpus.json", [
        {
            "id": "SYN-T1",
            "kind": "direct_neighbors",
            "signal": "top.u0.b",
            "expected": {"driver_count": 1, "count": 3},
        },
        {
            "id": "SYN-T2",
            "kind": "directed_path",
            "mode": "canonical",
            "from": "top.x",
            "to": "top.z",
            "expected": {"found": True, "hop_count": 5, "candidate_count": 2},
        },
        {
            "id": "SYN-T3",
            "kind": "verify_path",
            "claim_type": "path",
            "from": "top.x",
            "to": "top.z",
            "expected": {"status": "verified"},
        },
        {
            "id": "SYN-T4",
            "kind": "verify_driver",
            "claim_type": "driver",
            "signal": "top.z",
            "driver": "top.q",
            "expected": {"status": "verified"},
        },
        {
            "id": "SYN-T5",
            "kind": "frontier",
            "signal": "top.u0.b",
            "expected": {"frontier_count_gte": 2},
        },
        {
            "id": "SYN-T6",
            "kind": "unknown",
            "signal": "top.no_such_signal",
            "expected": {"ok": False, "error_contains": "not found"},
        },
        {
            "id": "SYN-T7",
            "kind": "consistency_connection",
            "expected": {"status": "pass", "checked": 2, "violations": 0},
        },
    ])
    proc = _run_runner(corpus, snap_dir, tag)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    # human-readable output is the default; check the summary line
    assert "7/7 tasks passed" in proc.stdout, proc.stdout


def test_runner_fails_on_wrong_expected(tmp_path, synthetic_snapshot):
    """[mutation] A wrong expected value must FAIL the task.

    This is the false-positive guard: if the runner ignored `expected`, a
    mutated corpus would still pass.
    """
    snap_dir, tag = synthetic_snapshot
    corpus = _write_corpus(tmp_path / "bad_corpus.json", [
        {
            "id": "SYN-BAD",
            "kind": "direct_neighbors",
            "signal": "top.u0.b",
            # deliberately wrong: the fixture has 1 driver and 3 loads
            "expected": {"driver_count": 99, "count": 3},
        },
    ])
    proc = _run_runner(corpus, snap_dir, tag)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "FAIL SYN-BAD" in proc.stdout, proc.stdout
    assert "driver_count" in proc.stdout, proc.stdout


def test_runner_json_output_names_the_mismatch(tmp_path, synthetic_snapshot):
    """[mutation] --json output must expose expected vs observed.

    Proves the failure is a real value comparison (and not, say, a crash
    or an empty result that is silently accepted).
    """
    snap_dir, tag = synthetic_snapshot
    corpus = _write_corpus(tmp_path / "bad_corpus.json", [
        {
            "id": "SYN-BAD",
            "kind": "direct_neighbors",
            "signal": "top.u0.b",
            "expected": {"driver_count": 99, "count": 3},
        },
    ])
    proc = _run_runner(corpus, snap_dir, tag, extra=["--json"])
    assert proc.returncode == 1, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["failed"] == 1
    assert payload["passed"] == 0
    result = payload["results"][0]
    assert result["passed"] is False
    assert result["expected"]["driver_count"] == 99
    assert result["observed"]["driver_count"] == 1
    assert result["observed"]["count"] == 3
    assert "driver_count" in result["error"]


def test_runner_fails_on_wrong_status_expected(tmp_path, synthetic_snapshot):
    """A wrong `status` expected value must fail too (not just counts)."""
    snap_dir, tag = synthetic_snapshot
    corpus = _write_corpus(tmp_path / "bad_status.json", [
        {
            "id": "SYN-BAD-STATUS",
            "kind": "verify_path",
            "claim_type": "path",
            "from": "top.x",
            "to": "top.z",
            "expected": {"status": "contradicted"},
        },
    ])
    proc = _run_runner(corpus, snap_dir, tag)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "SYN-BAD-STATUS" in proc.stdout, proc.stdout


def test_runner_records_the_cli_invocations(tmp_path, synthetic_snapshot):
    """The runner must record the exact CLI argv it ran (copy-pasteable)."""
    snap_dir, tag = synthetic_snapshot
    corpus = _write_corpus(tmp_path / "c.json", [
        {
            "id": "SYN-CMD",
            "kind": "directed_path",
            "mode": "canonical",
            "from": "top.x",
            "to": "top.z",
            "expected": {"found": True, "hop_count": 5, "candidate_count": 2},
        },
    ])
    proc = _run_runner(corpus, snap_dir, tag, extra=["--json"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)["results"][0]
    assert len(result["commands"]) == 1
    cmd = result["commands"][0]
    assert cmd.startswith("paths top.x top.z --directed --canonical")
    assert f"--from-snapshot {tag}" in cmd


def test_runner_unknown_kind_fails_when_signal_exists(tmp_path, synthetic_snapshot):
    """A `kind=unknown` task on an EXISTING signal must fail.

    Proves the unknown-kind task really asserts the "not found" outcome and
    is not satisfied by "the command exited 0".
    """
    snap_dir, tag = synthetic_snapshot
    corpus = _write_corpus(tmp_path / "unknown_existing.json", [
        {
            "id": "SYN-UNKNOWN-EXISTS",
            "kind": "unknown",
            "signal": "top.u0.b",  # this signal DOES exist
            "expected": {"ok": False, "error_contains": "not found"},
        },
    ])
    proc = _run_runner(corpus, snap_dir, tag)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "FAIL SYN-UNKNOWN-EXISTS" in proc.stdout, proc.stdout


def test_runner_rejects_malformed_task_without_skipping(tmp_path, synthetic_snapshot):
    """Malformed tasks are hard failures — never a silent skip."""
    snap_dir, tag = synthetic_snapshot
    corpus = _write_corpus(tmp_path / "malformed.json", [
        {"id": "SYN-UNKNOWN-KIND", "kind": "no_such_kind", "expected": {"x": 1}},
        {"id": "SYN-NO-SIGNAL", "kind": "direct_neighbors", "expected": {"count": 1}},
        {"id": "SYN-BAD-KEY", "kind": "frontier", "signal": "top.u0.b",
         "expected": {"not_a_real_field": 1}},
    ])
    proc = _run_runner(corpus, snap_dir, tag)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    for tid in ("SYN-UNKNOWN-KIND", "SYN-NO-SIGNAL", "SYN-BAD-KEY"):
        assert f"FAIL {tid}" in proc.stdout, proc.stdout
    # a malformed task must not be reported as passed
    assert "3/3 tasks passed" not in proc.stdout, proc.stdout


def test_runner_reports_missing_snapshot(tmp_path):
    """A missing snapshot is an explicit error (exit 2), not a pass."""
    corpus = _write_corpus(tmp_path / "c.json", [
        {"id": "SYN-X", "kind": "frontier", "signal": "top.u0.b",
         "expected": {"frontier_count_gte": 1}},
    ])
    proc = _run_runner(corpus, tmp_path / "nope", "no_such_tag")
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "snapshot not found" in (proc.stdout + proc.stderr).lower()


# ---------------------------------------------------------------------------
# 2. Corpus JSON shape (no external project needed)
# ---------------------------------------------------------------------------


def test_real_corpus_json_is_well_formed():
    """The corpus file itself must parse and declare 9 tasks."""
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    tasks = data["tasks"]
    assert len(tasks) == 9
    ids = [t["id"] for t in tasks]
    assert ids == [f"SPI-T{i}" for i in range(1, 10)]
    for task in tasks:
        assert task["expected"], task["id"]
        assert "oracle" in task, f"{task['id']} must carry an independent oracle"
    # the runner's expected-spec must cover every key used by the corpus
    sys.path.insert(0, str(ROOT / "tools" / "agent"))
    try:
        import run_spi_corpus as runner  # noqa: PLC0415
    finally:
        sys.path.pop(0)
    for task in tasks:
        spec = runner.EXPECTED_SPECS[task["kind"]]
        unknown = sorted(set(task["expected"]) - set(spec))
        assert not unknown, f"{task['id']}: unknown expected keys {unknown}"


def test_real_corpus_uses_contract_fields_not_invented_ones():
    """`load_count` is not a CLI field — the corpus must use `count`.

    Regression for the P158.4 finding that `loads` reports `count`, while
    only `drivers` reports `driver_count`.
    """
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    for task in data["tasks"]:
        if task["kind"] == "direct_neighbors":
            assert "load_count" not in task["expected"], task["id"]
            assert task["expected"]["count"] > 0, task["id"]
            assert task["expected"]["driver_count"] > 0, task["id"]


# ---------------------------------------------------------------------------
# 3. Real corpus against the external SPI snapshot
# ---------------------------------------------------------------------------


def _find_real_snapshot_dir() -> Path | None:
    for candidate in REAL_SNAPSHOT_DIRS:
        if (candidate / f"{REAL_SNAPSHOT_TAG}.json").exists():
            return candidate
    return None


@pytest.mark.opensource
@pytest.mark.real_corpus
def test_real_spi_corpus_passes():
    """[real-corpus] All 9 SPI tasks must pass against the external snapshot.

    Skips **only** when the external snapshot directory is absent (the
    snapshot is an external fixture — see
    docs/validation/P152_SPI_CORPUS_2026-11-10.md §4). There is no
    permanent canonical skip: when the snapshot exists this test runs all
    9 tasks.
    """
    snap_dir = _find_real_snapshot_dir()
    if snap_dir is None:
        pytest.skip(
            "SPI snapshot not available: expected "
            f"{REAL_SNAPSHOT_TAG}.json under one of "
            f"{[str(p) for p in REAL_SNAPSHOT_DIRS]}. "
            "The snapshot is an external fixture (P152 §4); this is an "
            "environment skip, not a canonical skip."
        )
    proc = _run_runner(CORPUS, snap_dir, REAL_SNAPSHOT_TAG)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "9/9 tasks passed" in proc.stdout, proc.stdout


@pytest.mark.opensource
@pytest.mark.real_corpus
def test_real_spi_corpus_fails_on_mutated_expected(tmp_path):
    """[real-corpus][mutation] The real corpus must be able to go red.

    Proves the 9/9 pass above is a real assertion, not a no-op: one
    expected value is mutated and the runner must reject it.
    """
    snap_dir = _find_real_snapshot_dir()
    if snap_dir is None:
        pytest.skip("SPI snapshot not available (external fixture, P152 §4)")
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    task = next(t for t in data["tasks"] if t["id"] == "SPI-T1")
    task["expected"]["driver_count"] = task["expected"]["driver_count"] + 1
    corpus = _write_corpus(tmp_path / "mutated.json", [task],
                           meta=data.get("meta"))
    proc = _run_runner(corpus, snap_dir, REAL_SNAPSHOT_TAG)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "FAIL SPI-T1" in proc.stdout, proc.stdout
