"""
test_trace_batch.py - Tests for trace batch mode (--batch, --batch-file)
========================================================================
[ADD 2026-07-03 B1] trace fanin/fanout/impact/evidence 加 batch mode.

**正反面测试** (项目纪律):
- 正面 (positive): 有效输入 → 正确输出
  - P1: 单 signal (向后兼容, 仍走 batch schema)
  - P2: --batch "sig1,sig2" 多 signal inline
  - P3: --batch-file (含注释 + 空行 + 重复 dedup)
  - P4: positional + --batch 混合 (3 signals)
- 反面 (negative): 无效输入 → 友好错误
  - N1: 没 signal/batch/batch-file → ValueError
  - N2: --batch-file 不存在 → ValueError 含路径
  - N3: --batch-file 空 (只有注释) → ValueError
  - N4: --batch "" (空字符串) → ValueError
  - N5: 不存在的 signal → 静默空 drivers (不报错)

**Golden 机制**: 用 sim/tests/fixtures/strict_uart/filelist.f (3 SV, 自洽).
不依赖外部项目, 跨平台稳定.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
STRICT_UART_FILELIST = str(PROJECT_ROOT / "sim" / "tests" / "fixtures" / "strict_uart" / "filelist.f")
GOLDEN_DIR = PROJECT_ROOT / "sim" / "tests" / "golden" / "trace_batch"
GOLDEN_DIR.mkdir(parents=True, exist_ok=True)


def _run(*args, timeout=60) -> subprocess.CompletedProcess:
    """Run sv_query trace with given args."""
    return subprocess.run(
        ["sv_query", "trace", *args],
        capture_output=True, text=True, timeout=timeout,
        cwd=str(PROJECT_ROOT),
    )


# ============================================================================
# 正面测试 (Positive)
# ============================================================================

def test_p1_single_signal_backward_compat():
    """P1: 单 signal (向后兼容, 仍走 batch schema)."""
    r = _run("fanin", "uart_top.rx_data_o", "--filelist", STRICT_UART_FILELIST, "--json")
    assert r.returncode == 0, f"rc={r.returncode} stderr={r.stderr[:300]}"
    data = json.loads(r.stdout)
    # Batch schema: 1-signal 也走 signals[]
    assert data["ok"]
    assert data["command"] == "trace_fanin"
    signals = data["result"]["signals"]
    assert len(signals) == 1
    assert signals[0]["signal"] == "uart_top.rx_data_o"
    assert signals[0]["count"] >= 1
    print(f"✅ P1 single signal: 1 sig, {signals[0]['count']} drivers")


def test_p2_batch_inline_multiple_signals():
    """P2: --batch inline 多 signal."""
    r = _run(
        "fanin",
        "--batch", "uart_top.rx_data_o,sync_fifo.count_q",
        "--filelist", STRICT_UART_FILELIST,
        "--json",
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["ok"]
    signals = data["result"]["signals"]
    assert len(signals) == 2
    assert signals[0]["signal"] == "uart_top.rx_data_o"
    assert signals[1]["signal"] == "sync_fifo.count_q"
    print(f"✅ P2 --batch inline: 2 signals")


def test_p3_batch_file_with_comments_and_dedup():
    """P3: --batch-file 含注释/空行/重复 sig (dedup)."""
    batch_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, prefix="batch_p3_"
    )
    try:
        batch_file.write("""
# This is a comment, should be skipped
uart_top.rx_data_o

# Another comment
sync_fifo.count_q

# Duplicate of first
uart_top.rx_data_o
""")
        batch_file.close()
        r = _run(
            "fanin",
            "--batch-file", batch_file.name,
            "--filelist", STRICT_UART_FILELIST,
            "--json",
        )
        assert r.returncode == 0
        data = json.loads(r.stdout)
        signals = data["result"]["signals"]
        # 3 行 content, 1 重复 → 实际 2 unique
        assert len(signals) == 2, f"expected 2 dedup'd, got {len(signals)}"
        sig_names = [s["signal"] for s in signals]
        assert sig_names[0] == "uart_top.rx_data_o", f"order: {sig_names}"
        assert sig_names[1] == "sync_fifo.count_q"
        print(f"✅ P3 --batch-file: 3 lines + 1 dup → 2 dedup'd, comment+blank skipped")
    finally:
        Path(batch_file.name).unlink(missing_ok=True)


def test_p4_positional_plus_batch_mix():
    """P4: positional + --batch 混合."""
    r = _run(
        "fanin", "uart_top.rx_data_o",  # positional
        "--batch", "sync_fifo.count_q,sync_fifo.wr_ptr_q",  # inline batch
        "--filelist", STRICT_UART_FILELIST,
        "--json",
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    signals = data["result"]["signals"]
    # 1 positional + 2 inline = 3 total
    assert len(signals) == 3
    assert signals[0]["signal"] == "uart_top.rx_data_o"
    assert signals[1]["signal"] == "sync_fifo.count_q"
    assert signals[2]["signal"] == "sync_fifo.wr_ptr_q"
    print("✅ P4 mixed: 1 positional + 2 inline → 3 total")


def test_p5_text_output_batch_header():
    """P5: text mode batch 输出应带 'signal N/M:' header."""
    r = _run(
        "fanin",
        "--batch", "uart_top.rx_data_o,sync_fifo.count_q",
        "--filelist", STRICT_UART_FILELIST,
    )
    assert r.returncode == 0
    # 应有 2 个 signal header
    assert "signal 1/2: uart_top.rx_data_o" in r.stdout
    assert "signal 2/2: sync_fifo.count_q" in r.stdout
    print("✅ P5 text mode: 'signal 1/2:' + 'signal 2/2:' headers present")


def test_p6_all_4_subcommands_support_batch():
    """P6: 4 子命令 (fanin/fanout/impact/evidence) 都支持 batch."""
    for cmd in ["fanin", "fanout", "impact", "evidence"]:
        r = _run(
            cmd,
            "--batch", "uart_top.rx_data_o",
            "--filelist", STRICT_UART_FILELIST,
            "--json",
        )
        assert r.returncode == 0, f"{cmd} failed: {r.stderr[:200]}"
        data = json.loads(r.stdout)
        assert data["ok"], f"{cmd} data not ok"
        assert "signals" in data["result"], f"{cmd} missing result.signals"
        assert len(data["result"]["signals"]) == 1
        print(f"✅ P6 {cmd}: batch support confirmed")


# ============================================================================
# 反面测试 (Negative)
# ============================================================================

def test_n1_no_signal_any_source():
    """N1: 没 signal/batch/batch-file → 友好错误."""
    r = _run("fanin", "--filelist", STRICT_UART_FILELIST)
    assert r.returncode != 0, f"expected non-zero rc, got {r.returncode}"
    assert "No signals" in r.stderr or "No signals" in r.stdout
    print("✅ N1 no signals: ValueError 'No signals'")


def test_n2_batch_file_not_found():
    """N2: --batch-file 路径不存在 → 友好错误含路径."""
    r = _run(
        "fanin",
        "--batch-file", "/tmp/nonexistent_batch_xyz.txt",
        "--filelist", STRICT_UART_FILELIST,
    )
    assert r.returncode != 0
    err = r.stderr + r.stdout
    assert "batch file not found" in err
    assert "/tmp/nonexistent_batch_xyz.txt" in err
    print("✅ N2 batch file missing: error includes path")


def test_n3_batch_file_only_comments():
    """N3: --batch-file 只有注释/空行 → 'No signals' 错误."""
    batch_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, prefix="batch_n3_"
    )
    try:
        batch_file.write("""
# Only comments here
# nothing else
""")
        batch_file.close()
        r = _run(
            "fanin",
            "--batch-file", batch_file.name,
            "--filelist", STRICT_UART_FILELIST,
        )
        assert r.returncode != 0
        assert "No signals" in r.stderr or "No signals" in r.stdout
        print("✅ N3 batch file empty (comments only): 'No signals' error")
    finally:
        Path(batch_file.name).unlink(missing_ok=True)


def test_n4_batch_empty_string():
    """N4: --batch '' (空字符串) → 'No signals' 错误."""
    r = _run("fanin", "--batch", "", "--filelist", STRICT_UART_FILELIST)
    assert r.returncode != 0
    assert "No signals" in r.stderr or "No signals" in r.stdout
    print("✅ N4 batch empty string: 'No signals' error")


def test_n5_nonexistent_signal_silent():
    """N5: 不存在的 signal → 静默空 drivers (不报错)."""
    r = _run(
        "fanin",
        "--batch", "uart_top.nonexistent_sig,uart_top.rx_data_o",
        "--filelist", STRICT_UART_FILELIST,
        "--json",
    )
    # 不存在 sig 应不报错, 静默返回空 drivers
    assert r.returncode == 0
    data = json.loads(r.stdout)
    signals = data["result"]["signals"]
    assert len(signals) == 2
    # 第 1 个: 0 drivers (不存在的 sig)
    assert signals[0]["signal"] == "uart_top.nonexistent_sig"
    assert signals[0]["count"] == 0
    # 第 2 个: 正常
    assert signals[1]["signal"] == "uart_top.rx_data_o"
    assert signals[1]["count"] >= 1
    print("✅ N5 nonexistent signal: silent empty drivers, not error")


# ============================================================================
# Golden baseline (正面 baseline)
# ============================================================================

def _normalize_json(data: dict) -> dict:
    """Normalize JSON for golden comparison.

    - 去掉 path (绝对路径 → 占位符)
    - 保留 structure (signal names, counts, kinds)
    """
    import copy
    data = copy.deepcopy(data)

    def clean(obj):
        if isinstance(obj, dict):
            return {k: clean(v) for k, v in obj.items() if k != "file"}
        if isinstance(obj, list):
            return [clean(x) for x in obj]
        if isinstance(obj, str):
            # 绝对路径 → PROJECT_ROOT/
            import re
            obj = re.sub(r"/Users/[^/]+/my_dv_proj/sv_query/", "PROJECT_ROOT/", obj)
            obj = re.sub(r"/home/[^/]+/my_dv_proj/sv_query/", "PROJECT_ROOT/", obj)
            return obj
        return obj

    return clean(data)


def _read_golden(name: str) -> dict:
    """Read golden JSON. Auto-create on first run."""
    path = GOLDEN_DIR / f"{name}.json"
    if not path.exists():
        # 首次跑: 生成 baseline
        # 用 2-signal inline batch
        r = _run(
            "fanin",
            "--batch", "uart_top.rx_data_o,sync_fifo.count_q",
            "--filelist", STRICT_UART_FILELIST,
            "--json",
        )
        assert r.returncode == 0, f"baseline gen failed: {r.stderr[:200]}"
        actual = _normalize_json(json.loads(r.stdout))
        path.write_text(json.dumps(actual, indent=2, sort_keys=True))
    return json.loads(path.read_text())


def test_golden_batch_fanin_2_signals():
    """Golden: 2-signal inline batch 跟 baseline 一致."""
    r = _run(
        "fanin",
        "--batch", "uart_top.rx_data_o,sync_fifo.count_q",
        "--filelist", STRICT_UART_FILELIST,
        "--json",
    )
    assert r.returncode == 0
    actual = _normalize_json(json.loads(r.stdout))
    golden = _read_golden("fanin_2signals")
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
    print("✅ Golden batch fanin: 2 signals match baseline")


if __name__ == "__main__":
    tests = [
        # Positive
        test_p1_single_signal_backward_compat,
        test_p2_batch_inline_multiple_signals,
        test_p3_batch_file_with_comments_and_dedup,
        test_p4_positional_plus_batch_mix,
        test_p5_text_output_batch_header,
        test_p6_all_4_subcommands_support_batch,
        # Negative
        test_n1_no_signal_any_source,
        test_n2_batch_file_not_found,
        test_n3_batch_file_only_comments,
        test_n4_batch_empty_string,
        test_n5_nonexistent_signal_silent,
        # Golden
        test_golden_batch_fanin_2_signals,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"❌ {t.__name__}: {e}")
            sys.exit(1)
    print(f"\n🎉 All {len(tests)} batch tests passed!")
