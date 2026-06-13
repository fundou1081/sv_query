"""Test golden diff infrastructure (VIZ_GOLDEN_PLAN 2026-06-13)

Verifies:
- diff.py correctly identifies missing/extra nodes
- diff.py correctly identifies missing/extra edges
- diff.py handles attribute mismatches
- diff.py exit code 0 = match, 1 = diff, 2 = error
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DIFF_TOOL = PROJECT_ROOT / "tools" / "golden" / "diff.py"


def _run_diff(golden: dict, actual: dict) -> tuple[int, str, str]:
    """Run diff.py with given dicts (write to temp files), return (rc, stdout, stderr)."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as gf:
        json.dump(golden, gf)
        gpath = gf.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as af:
        json.dump(actual, af)
        apath = af.name
    result = subprocess.run(
        [sys.executable, str(DIFF_TOOL), "--golden", gpath, "--actual", apath],
        capture_output=True, text=True, timeout=10,
    )
    return result.returncode, result.stdout, result.stderr


# ---- Pure Python diff tests (faster) ----

def test_perfect_match():
    golden = {"module": "x", "view": "v", "level": 1, "nodes": [{"id": "n1"}], "edges": []}
    actual = {"module": "x", "view": "v", "level": 1, "nodes": [{"id": "n1"}], "edges": []}
    rc, out, err = _run_diff(golden, actual)
    assert rc == 0
    assert "Match" in out


def test_missing_node_detected():
    golden = {"module": "x", "view": "v", "level": 1,
              "nodes": [{"id": "n1"}, {"id": "n2"}], "edges": []}
    actual = {"module": "x", "view": "v", "level": 1,
              "nodes": [{"id": "n1"}], "edges": []}
    rc, out, _ = _run_diff(golden, actual)
    assert rc == 1
    assert "missing: n2" in out


def test_extra_node_detected():
    golden = {"module": "x", "view": "v", "level": 1,
              "nodes": [{"id": "n1"}], "edges": []}
    actual = {"module": "x", "view": "v", "level": 1,
              "nodes": [{"id": "n1"}, {"id": "extra"}], "edges": []}
    rc, out, _ = _run_diff(golden, actual)
    assert rc == 1
    assert "extra: extra" in out


def test_node_attribute_mismatch():
    """Same node id, but kind/cluster differs"""
    golden = {"module": "x", "view": "v", "level": 1,
              "nodes": [{"id": "n1", "kind": "module", "cluster": "shared"}], "edges": []}
    actual = {"module": "x", "view": "v", "level": 1,
              "nodes": [{"id": "n1", "kind": "reg", "cluster": "data"}], "edges": []}
    rc, out, _ = _run_diff(golden, actual)
    assert rc == 1
    assert "n1.kind" in out
    assert "n1.cluster" in out


def test_missing_edge():
    golden = {"module": "x", "view": "v", "level": 1,
              "nodes": [{"id": "a"}, {"id": "b"}],
              "edges": [{"from": "a", "to": "b", "kind": "data"}]}
    actual = {"module": "x", "view": "v", "level": 1,
              "nodes": [{"id": "a"}, {"id": "b"}],
              "edges": []}
    rc, out, _ = _run_diff(golden, actual)
    assert rc == 1
    assert "missing: a -> b (data)" in out


def test_extra_edge():
    golden = {"module": "x", "view": "v", "level": 1,
              "nodes": [{"id": "a"}, {"id": "b"}],
              "edges": []}
    actual = {"module": "x", "view": "v", "level": 1,
              "nodes": [{"id": "a"}, {"id": "b"}],
              "edges": [{"from": "a", "to": "b", "kind": "data"}]}
    rc, out, _ = _run_diff(golden, actual)
    assert rc == 1
    assert "extra: a -> b (data)" in out


def test_meta_mismatch():
    golden = {"module": "x", "view": "v", "level": 1, "nodes": [], "edges": []}
    actual = {"module": "y", "view": "v", "level": 1, "nodes": [], "edges": []}
    rc, out, _ = _run_diff(golden, actual)
    assert rc == 1
    assert "[meta] module" in out


def test_missing_file_returns_error_code_2():
    result = subprocess.run(
        [sys.executable, str(DIFF_TOOL),
         "--golden", "/nonexistent.json", "--actual", "/tmp/actual.json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 2


def test_invalid_json_returns_error_code_2(tmp_path):
    gpath = tmp_path / "g.json"
    gpath.write_text("not valid json {{{")
    apath = tmp_path / "a.json"
    apath.write_text("{}")
    result = subprocess.run(
        [sys.executable, str(DIFF_TOOL),
         "--golden", str(gpath), "--actual", str(apath)],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 2


def test_cluster_mismatch():
    golden = {"module": "x", "view": "v", "level": 1, "nodes": [],
              "edges": [], "clusters": [{"id": "c1"}]}
    actual = {"module": "x", "view": "v", "level": 1, "nodes": [],
              "edges": [], "clusters": [{"id": "c2"}]}
    rc, out, _ = _run_diff(golden, actual)
    assert rc == 1
    assert "cluster" in out


def test_skip_in_diff_node_excluded():
    """[PR1 2026-06-13] aspirational 黄金: skip_in_diff=true 节点不算差异"""
    golden = {"module": "x", "view": "v", "level": 1,
              "nodes": [
                  {"id": "real", "kind": "module"},
                  {"id": "aspirational", "kind": "module", "skip_in_diff": True}
              ], "edges": []}
    actual = {"module": "x", "view": "v", "level": 1,
              "nodes": [{"id": "real", "kind": "module"}], "edges": []}
    rc, out, _ = _run_diff(golden, actual)
    # real 一致, aspirational 被跳过 → 完美匹配
    assert rc == 0
    assert "Match" in out


def test_skip_in_diff_edge_excluded():
    golden = {"module": "x", "view": "v", "level": 1,
              "nodes": [{"id": "a"}, {"id": "b"}],
              "edges": [
                  {"from": "a", "to": "b", "kind": "data"},
                  {"from": "a", "to": "b", "kind": "aspirational", "skip_in_diff": True}
              ]}
    actual = {"module": "x", "view": "v", "level": 1,
              "nodes": [{"id": "a"}, {"id": "b"}],
              "edges": [{"from": "a", "to": "b", "kind": "data"}]}
    rc, out, _ = _run_diff(golden, actual)
    assert rc == 0


def test_skip_in_diff_does_not_skip_extras():
    """[PR1] 实际有多余节点时, 仍要报 extra (skip_in_diff 只跳过黄金, 实际多出的不是)"""
    golden = {"module": "x", "view": "v", "level": 1,
              "nodes": [{"id": "a"}], "edges": []}
    actual = {"module": "x", "view": "v", "level": 1,
              "nodes": [{"id": "a"}, {"id": "extra"}], "edges": []}
    rc, out, _ = _run_diff(golden, actual)
    assert rc == 1
    assert "extra: extra" in out
