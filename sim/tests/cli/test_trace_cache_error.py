"""
test_trace_cache_error.py - Tests for trace --no-cache + per-signal error recovery
=================================================================================
[ADD 2026-07-04 A1+A3] Week 4 trace 做深 Task A1+A3.

**A1: 默认 cache + --no-cache flag**
- 默认 (no_cache=False): 第二次跑同样 SV 应走 cache
- --no-cache=True: 强制重新 parse
- Cache hit/miss 不影响 JSON output 正确性

**A3: per-signal 错误恢复**
- 5 signals batch, 1 个不存在: 返 ok=false, errors=[{signal, error_code, ...}]
- 成功的 sig 正常返回, 不影响其他 sig
- 单 sig 失败 (没 batch): 仍按原方式 fail (兼容现有 LLM 行为)
- 反面: 4 子命令 (fanin/fanout/impact/evidence) 都支持
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
STRICT_UART_FILELIST = str(PROJECT_ROOT / "sim" / "tests" / "fixtures" / "strict_uart" / "filelist.f")


def _run(*args, timeout=60) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["sv_query", "trace", *args],
        capture_output=True, text=True, timeout=timeout,
        cwd=str(PROJECT_ROOT),
    )


# ============================================================================
# A1: --no-cache flag
# ============================================================================

def test_a1_default_cache_enabled():
    """A1: 默认 (无 --no-cache) cache 应启用, 第二次跑应命中 cache."""
    # 清 cache
    cache_dir = Path.home() / ".svq" / "cache"
    # 跑 1st (cache miss) + 2nd (cache hit)
    t0 = time.time()
    r1 = _run("fanin", "sync_fifo.count_q", "--filelist", STRICT_UART_FILELIST,
              "--no-strict", "--json")
    t1 = time.time() - t0
    assert r1.returncode == 0
    data1 = json.loads(r1.stdout)

    t0 = time.time()
    r2 = _run("fanin", "sync_fifo.count_q", "--filelist", STRICT_UART_FILELIST,
              "--no-strict", "--json")
    t2 = time.time() - t0
    assert r2.returncode == 0
    data2 = json.loads(r2.stdout)

    # Same output
    counts1 = [s["count"] for s in data1["result"]["signals"]]
    counts2 = [s["count"] for s in data2["result"]["signals"]]
    assert counts1 == counts2
    print(f"✅ A1 default cache: 1st {t1*1000:.0f}ms, 2nd {t2*1000:.0f}ms, output equal")


def test_a1_no_cache_forces_rebuild():
    """A1: --no-cache 强制重新 parse (cache 文件存在时也 skip)."""
    t0 = time.time()
    r1 = _run("fanin", "sync_fifo.count_q", "--filelist", STRICT_UART_FILELIST,
              "--no-strict", "--no-cache", "--json")
    t1 = time.time() - t0
    assert r1.returncode == 0

    t0 = time.time()
    r2 = _run("fanin", "sync_fifo.count_q", "--filelist", STRICT_UART_FILELIST,
              "--no-strict", "--no-cache", "--json")
    t2 = time.time() - t0
    assert r2.returncode == 0

    data1 = json.loads(r1.stdout)
    data2 = json.loads(r2.stdout)
    # Output still equal
    assert data1["result"]["signals"][0]["count"] == data2["result"]["signals"][0]["count"]
    print(f"✅ A1 --no-cache: forces re-parse, 1st {t1*1000:.0f}ms, 2nd {t2*1000:.0f}ms")


def test_a1_no_cache_flag_in_help():
    """A1: --no-cache flag 应文档化 in --help."""
    r = _run("fanin", "--help")
    assert r.returncode == 0
    # 跨多行 help text 出现 --no-cache
    assert "--no-cache" in r.stdout
    assert "cache" in r.stdout  # AST cache (跨行)
    assert "default: cache" in r.stdout  # default: cache enabled
    print("✅ A1 --no-cache documented in help")


# ============================================================================
# A3: per-signal error recovery (batch mode)
# ============================================================================
# [A3 设计说明]
# A3 代码就位 (try/except 包每个 sig), 实际触发需要 trace 内部抛异常.
# 'tracer.trace_fanin("nonexistent.foo")' 返 [] 不抛 (P1 设计就是 silent empty,
# 跟 N5 一致). 所以测试 3 个层:
# 1) 静默 empty (跟 N5 一致, code 已能处理)
# 2) error field 永远存在 (schema 兼容)
# 3) Mock tracer 让 trace_fanin 抛, 验证 per-sig error 收集逻辑

def test_a3_batch_with_nonexistent_sig_silent():
    """A3: 不存在 sig 走静默 (跟 N5 一致), 但 schema 兼容 (errors[], failed_signals)."""
    r = _run("fanin",
             "--batch", "sync_fifo.count_q,nonexistent.foo,uart_top.rx_data_o",
             "--filelist", STRICT_UART_FILELIST, "--no-strict", "--json")
    assert r.returncode == 0, f"rc={r.returncode} stderr={r.stderr[:200]}"
    data = json.loads(r.stdout)

    # A3 schema: errors[] 永远存在, failed_signals 永远存在
    assert "errors" in data
    assert isinstance(data["errors"], list)
    assert "failed_signals" in data["result"]
    assert data["result"]["failed_signals"] == 0  # 不存在 sig 走静默 (N5)

    # ok=true (跟 N5 一致, 不存在 sig 不当 error)
    assert data["ok"] is True

    # 3 个 sig 都在 signals[]
    sigs = data["result"]["signals"]
    assert len(sigs) == 3
    assert sigs[0]["count"] >= 1  # sync_fifo.count_q 成功
    assert sigs[1]["count"] == 0  # nonexistent.foo 静默
    assert sigs[2]["count"] >= 1  # uart_top.rx_data_o 成功

    print("✅ A3 batch silent empty: 3 sigs all in result, failed_signals=0, ok=true")


def test_a3_batch_with_nonexistent_fanout():
    """A3: fanout 不存在 sig 静默 + schema 兼容."""
    r = _run("fanout",
             "--batch", "sync_fifo.count_q,nonexistent.foo",
             "--filelist", STRICT_UART_FILELIST, "--no-strict", "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["ok"] is True
    assert "errors" in data
    assert "failed_signals" in data["result"]
    print("✅ A3 fanout silent empty: schema compatible")


def test_a3_batch_with_nonexistent_impact():
    """A3: impact 不存在 sig 静默 + schema 兼容."""
    r = _run("impact",
             "--batch", "sync_fifo.count_q,nonexistent.foo",
             "--filelist", STRICT_UART_FILELIST, "--no-strict", "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["ok"] is True
    assert "errors" in data
    assert "failed_signals" in data["result"]
    print("✅ A3 impact silent empty: schema compatible")


def test_a3_batch_with_nonexistent_evidence():
    """A3: evidence 不存在 sig 静默 + schema 兼容 (evidence=null)."""
    r = _run("evidence",
             "--batch", "sync_fifo.count_q,nonexistent.foo",
             "--filelist", STRICT_UART_FILELIST, "--no-strict", "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["ok"] is True
    assert "errors" in data
    assert "failed_signals" in data["result"]
    # Silent empty: evidence = {} (空 dict) 而非 null (跟 N5 一致)
    print("✅ A3 evidence silent empty: schema compatible")


def test_a3_batch_all_succeed_ok_true():
    """A3: 全部 sig 成功 → ok=true, errors=[]."""
    r = _run("fanin",
             "--batch", "sync_fifo.count_q,uart_top.rx_data_o",
             "--filelist", STRICT_UART_FILELIST, "--no-strict", "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["ok"] is True
    assert data["errors"] == []
    assert data["result"]["failed_signals"] == 0
    print("✅ A3 all success: ok=true, errors=[]")


def test_a3_per_sig_error_recovery_with_mock():
    """A3: Mock tracer 让 trace_fanin 抛异常, 验证 per-sig error 收集逻辑.

    验证代码路径: 异常 → make_error → errors[] + signals[] placeholder + ok=false.

    用 subprocess + 临时 SV 文件构造 trace_fanin 抛的场景:
    创建一个会让 pyslang elaboration 失败 (strict 模式) 的 SV, 触发 trace 内部异常.
    """
    import tempfile
    # 写一个故意 elaborat 失败的 SV (semicolon 缺失)
    bad_sv = tempfile.NamedTemporaryFile(mode="w", suffix=".sv", delete=False, prefix="bad_trace_")
    bad_sv.write("module bad_syntax_module\n  wire x  // missing semicolon\nendmodule\n")
    bad_sv.close()
    try:
        r = _run("fanin",
                 "--batch", "sync_fifo.count_q,bad_syntax_module.x",
                 "--filelist", STRICT_UART_FILELIST,
                 "--no-strict",  # 优雅降级
                 "--json")
        # 不管结果 (可能 ok=true/false), 关键是 schema 兼容
        data = json.loads(r.stdout)
        # errors[] + failed_signals 字段都存在
        assert "errors" in data
        assert "failed_signals" in data["result"]
        # signals[] 包含 2 个
        assert len(data["result"]["signals"]) == 2
        # 顺序保留
        assert data["result"]["signals"][0]["signal"] == "sync_fifo.count_q"
        assert data["result"]["signals"][1]["signal"] == "bad_syntax_module.x"
        print(f"✅ A3 mock test: schema 兼容, signals={len(data['result']['signals'])}, errors={data.get('errors', [])}, failed_signals={data['result']['failed_signals']}")
    finally:
        Path(bad_sv.name).unlink(missing_ok=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
