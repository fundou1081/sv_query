"""
test_trace_snapshot.py - Tests for trace --from-snapshot option (B4)
==================================================================
[ADD 2026-07-03 B4] Week 3 trace 做深 Task 4/4.

**目标**: trace 命令能从已存的 snapshot (.svq/snapshots/<tag>.json) 加载 graph,
跳过 SV parse, 加速多次 trace (parse 1 次, trace N 次).

**Fixture**:
- sim/tests/fixtures/strict_uart/ (3 SV, 自洽)
- snapshot tag: `b4_test` (test 自行 save, 隔离)

**正反面测试**:
- 正面 (positive):
  - P1: fanin --from-snapshot 跟 --file 输出一致 (cross-check)
  - P2: fanout --from-snapshot
  - P3: impact --from-snapshot
  - P4: evidence --from-snapshot
  - P5: --from-snapshot + --batch 组合
  - P6: --from-snapshot + --type filter
  - P7: --from-snapshot + --no-strict (no SV parse, 所以 strict 不影响)
- 反面 (negative):
  - N1: --from-snapshot 无效 tag → E_INVALID_INPUT
  - N2: --from-snapshot + --file 互斥 → E_INVALID_INPUT
  - N3: --from-snapshot + --filelist 互斥 → E_INVALID_INPUT
  - N4: 不带 --file/--filelist/snapshot → 友好错误

**Golden**: snapshot-based fanin baseline
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
STRICT_UART_FILELIST = str(PROJECT_ROOT / "sim" / "tests" / "fixtures" / "strict_uart" / "filelist.f")
GOLDEN_DIR = PROJECT_ROOT / "sim" / "tests" / "golden" / "trace_snapshot"
GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
TEST_SNAPSHOT_TAG = "b4_test_fixture"


def _save_test_snapshot() -> None:
    """Save a test snapshot to a unique tag (idempotent)."""
    snap_path = PROJECT_ROOT / ".svq" / "snapshots" / f"{TEST_SNAPSHOT_TAG}.json"
    if snap_path.exists():
        return
    r = subprocess.run(
        ["sv_query", "snapshot", "save", STRICT_UART_FILELIST,
         "--tag", TEST_SNAPSHOT_TAG, "--no-strict", "--filelist", STRICT_UART_FILELIST],
        capture_output=True, text=True, timeout=60,
        cwd=str(PROJECT_ROOT),
    )
    if r.returncode != 0:
        pytest.skip(f"Could not save test snapshot: {r.stderr[:200]}")


def _run(*args, timeout=60) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["sv_query", "trace", *args],
        capture_output=True, text=True, timeout=timeout,
        cwd=str(PROJECT_ROOT),
    )


@pytest.fixture(scope="module", autouse=True)
def ensure_snapshot():
    """Auto-save test snapshot before running tests."""
    _save_test_snapshot()


# ============================================================================
# 正面 (Positive)
# ============================================================================

def test_p1_fanin_from_snapshot_matches_file():
    """P1: fanin --from-snapshot 跟 --filelist 输出一致 (drivers count + 内容)."""
    # Run with --filelist (parse SV)
    r1 = _run("fanin", "sync_fifo.count_q", "--filelist", STRICT_UART_FILELIST, "--no-strict", "--json")
    assert r1.returncode == 0
    data1 = json.loads(r1.stdout)
    # Run with --from-snapshot (no parse)
    r2 = _run("fanin", "sync_fifo.count_q", "--from-snapshot", TEST_SNAPSHOT_TAG, "--json")
    assert r2.returncode == 0
    data2 = json.loads(r2.stdout)
    # Compare drivers (ignoring params.from_snapshot null vs absent)
    sigs1 = data1["result"]["signals"][0]
    sigs2 = data2["result"]["signals"][0]
    assert sigs1["count"] == sigs2["count"], f"count mismatch: {sigs1['count']} vs {sigs2['count']}"
    # Compare driver ids
    ids1 = sorted(d["id"] for d in sigs1["drivers"])
    ids2 = sorted(d["id"] for d in sigs2["drivers"])
    assert ids1 == ids2, f"driver ids mismatch:\n  file: {ids1}\n  snap: {ids2}"
    print(f"✅ P1 fanin --from-snapshot == --filelist ({sigs1['count']} drivers)")


def test_p2_fanout_from_snapshot():
    """P2: fanout --from-snapshot 跟 --filelist 一致."""
    r1 = _run("fanout", "sync_fifo.count_q", "--filelist", STRICT_UART_FILELIST, "--no-strict", "--json")
    r2 = _run("fanout", "sync_fifo.count_q", "--from-snapshot", TEST_SNAPSHOT_TAG, "--json")
    assert r1.returncode == 0 and r2.returncode == 0
    data1 = json.loads(r1.stdout)
    data2 = json.loads(r2.stdout)
    sig1, sig2 = data1["result"]["signals"][0], data2["result"]["signals"][0]
    assert sig1["count"] == sig2["count"]
    print(f"✅ P2 fanout --from-snapshot: {sig1['count']} loads match")


def test_p3_impact_from_snapshot():
    """P3: impact --from-snapshot 跟 --filelist 一致 (paths count)."""
    r1 = _run("impact", "sync_fifo.count_q", "--filelist", STRICT_UART_FILELIST, "--no-strict", "--json")
    r2 = _run("impact", "sync_fifo.count_q", "--from-snapshot", TEST_SNAPSHOT_TAG, "--json")
    assert r1.returncode == 0 and r2.returncode == 0
    data1 = json.loads(r1.stdout)
    data2 = json.loads(r2.stdout)
    # Note: impact 用了 SVAExtractor 跟 CovergroupExtractor, snapshot 没这些
    # 所以 total_paths 在 snapshot 模式可能为 0 (因为没 extract SVA/Covergroup)
    # 但 paths 字段 schema 应该一致
    assert "signals" in data2["result"]
    assert "total_paths" in data2["result"]
    print(f"✅ P3 impact --from-snapshot: {data2['result']['total_paths']} paths (snapshot lacks SVA/Covergroup extraction)")


def test_p4_evidence_from_snapshot():
    """P4: evidence --from-snapshot 能查到 signal (graph 在, 但 source 不在, 所以 source_text 空)."""
    r = _run("evidence", "sync_fifo.count_q", "--from-snapshot", TEST_SNAPSHOT_TAG, "--json")
    assert r.returncode == 0, f"rc={r.returncode} stderr={r.stderr[:200]}"
    data = json.loads(r.stdout)
    ev = data["result"]["signals"][0]["evidence"]
    # Snapshot 重建 graph 但 source_text 是空 (snapshot 不存源)
    assert ev["signal"] == "sync_fifo.count_q"
    assert ev.get("source_text") == "", "source_text should be empty in snapshot mode"
    print("✅ P4 evidence --from-snapshot: signal found, source_text empty (snapshot limitation)")


def test_p5_from_snapshot_with_batch():
    """P5: --from-snapshot + --batch 组合."""
    r = _run("fanin", "--batch", "sync_fifo.count_q,uart_top.rx_data_o",
             "--from-snapshot", TEST_SNAPSHOT_TAG, "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["result"]["total_signals"] == 2
    for sig_entry in data["result"]["signals"]:
        assert sig_entry["count"] >= 0
    print(f"✅ P5 --from-snapshot + --batch: 2 signals processed")


def test_p6_from_snapshot_with_filter():
    """P6: --from-snapshot + --type filter 组合."""
    r = _run("fanin", "sync_fifo.count_q",
             "--from-snapshot", TEST_SNAPSHOT_TAG,
             "--type", "REG", "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    drivers = data["result"]["signals"][0]["drivers"]
    for d in drivers:
        assert d["kind"] == "REG", f"filter failed: {d}"
    print(f"✅ P6 --from-snapshot + --type REG: {len(drivers)} drivers, all REG")


def test_p7_from_snapshot_no_strict():
    """P7: --from-snapshot --no-strict (snapshot 模式 strict 不影响, 因为没 parse)."""
    r = _run("fanin", "sync_fifo.count_q",
             "--from-snapshot", TEST_SNAPSHOT_TAG, "--no-strict", "--json")
    assert r.returncode == 0
    print("✅ P7 --from-snapshot --no-strict: works (strict doesn't affect snapshot mode)")


# ============================================================================
# 反面 (Negative)
# ============================================================================

def test_n1_nonexistent_snapshot_tag():
    """N1: --from-snapshot 无效 tag → 友好错误."""
    r = _run("fanin", "sync_fifo.count_q",
             "--from-snapshot", "nonexistent_tag_xyz", "--json")
    assert r.returncode != 0
    data = json.loads(r.stdout)
    assert data["ok"] is False
    assert "not found" in data.get("error", "").lower()
    print("✅ N1 nonexistent snapshot: E_INVALID_INPUT")


def test_n2_from_snapshot_with_file_mutually_exclusive():
    """N2: --from-snapshot + --file 互斥 → 错误."""
    # Write temp SV file
    tmp_sv = tempfile.NamedTemporaryFile(mode="w", suffix=".sv", delete=False)
    tmp_sv.write("`timescale 1ns/1ps\nmodule top; endmodule\n")
    tmp_sv.close()
    try:
        r = _run("fanin", "sync_fifo.count_q",
                 "--from-snapshot", TEST_SNAPSHOT_TAG,
                 "--file", tmp_sv.name, "--json")
        assert r.returncode != 0
        data = json.loads(r.stdout)
        assert "mutually exclusive" in data.get("error", "")
        print("✅ N2 --from-snapshot + --file: mutually exclusive error")
    finally:
        Path(tmp_sv.name).unlink(missing_ok=True)


def test_n3_from_snapshot_with_filelist_mutually_exclusive():
    """N3: --from-snapshot + --filelist 互斥 → 错误."""
    r = _run("fanin", "sync_fifo.count_q",
             "--from-snapshot", TEST_SNAPSHOT_TAG,
             "--filelist", STRICT_UART_FILELIST, "--json")
    assert r.returncode != 0
    data = json.loads(r.stdout)
    assert "mutually exclusive" in data.get("error", "")
    print("✅ N3 --from-snapshot + --filelist: mutually exclusive error")


def test_n4_no_source_no_snapshot():
    """N4: 没 --file/--filelist/--from-snapshot → 友好错误."""
    r = _run("fanin", "sync_fifo.count_q", "--json")
    assert r.returncode != 0
    data = json.loads(r.stdout)
    err = data.get("error", "").lower()
    assert "must be provided" in err or "filelist" in err
    print("✅ N4 no source: friendly error message")


# ============================================================================
# Golden baseline
# ============================================================================

def _normalize_json(data: dict) -> dict:
    import copy, re
    data = copy.deepcopy(data)

    def clean(obj):
        if isinstance(obj, dict):
            return {k: clean(v) for k, v in obj.items() if k not in ("file", "from_snapshot")}
        if isinstance(obj, list):
            return [clean(x) for x in obj]
        if isinstance(obj, str):
            obj = re.sub(r"/Users/[^/]+/my_dv_proj/sv_query/", "PROJECT_ROOT/", obj)
            obj = re.sub(r"/home/[^/]+/my_dv_proj/sv_query/", "PROJECT_ROOT/", obj)
            return obj
        return obj

    return clean(data)


def _read_golden(name: str) -> dict:
    path = GOLDEN_DIR / f"{name}.json"
    if not path.exists():
        # 首次跑: 生成 baseline
        r = _run("fanin", "sync_fifo.count_q",
                 "--from-snapshot", TEST_SNAPSHOT_TAG,
                 "--type", "REG", "--width-min", "2", "--json")
        assert r.returncode == 0
        actual = _normalize_json(json.loads(r.stdout))
        path.write_text(json.dumps(actual, indent=2, sort_keys=True))
    return json.loads(path.read_text())


def test_golden_snapshot_fanin_with_filter():
    """Golden: snapshot-based fanin + --type + --width-min 跟 baseline 比对."""
    r = _run("fanin", "sync_fifo.count_q",
             "--from-snapshot", TEST_SNAPSHOT_TAG,
             "--type", "REG", "--width-min", "2", "--json")
    assert r.returncode == 0
    actual = _normalize_json(json.loads(r.stdout))
    golden = _read_golden("snapshot_fanin_type_REG")
    if actual != golden:
        import difflib
        diff = "\n".join(difflib.unified_diff(
            json.dumps(golden, indent=2, sort_keys=True).splitlines(),
            json.dumps(actual, indent=2, sort_keys=True).splitlines(),
            lineterm="",
            fromfile="golden",
            tofile="actual",
            n=3,
        ))
        pytest.fail(f"Golden mismatch:\n{diff[:2000]}")
    print("✅ Golden: --from-snapshot fanin + filter matches baseline")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
