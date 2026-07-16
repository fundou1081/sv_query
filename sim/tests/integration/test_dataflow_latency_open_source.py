# ==============================================================================
# test_dataflow_latency_open_source.py
# [ADD 2026-07-04] 验证 dataflow analyze 的 latency 字段在 5+ 真项目上正确
#
# 核心测试:
# - 同步 sync FIFO: 2 cycle latency (write + read)
# - OpenTitan prim_arbiter_tree: 0 cycle (纯组合 arbiter)
# - CVA6 alu: 0 cycle (组合 ALU)
# - darkriscv IDATA2 → XIDATA: 1 cycle (ID/EX pipeline REG)
# - two_flop_sync: null latency (async crossing)
# - sync_fifo stage_breakdown: 验证 stage 标注
#
# 严格金标准: 每个 test 都用真项目 + 已知 latency ground truth
# ==============================================================================

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Test fixtures
SYNC_FIFO = "/tmp/cdc_test/sync_fifo.sv"
TWO_FLOP_SYNC = "/tmp/cdc_test/two_flop_sync.sv"
PRIM_ARBITER = "/Users/fundou/my_dv_proj/opentitan/hw/ip/prim/rtl/prim_arbiter_tree.sv"
CVA6_FILELIST = "/Users/fundou/my_dv_proj/cva6/Flist.ariane"
DARKRISCV = "/Users/fundou/my_dv_proj/darkriscv/rtl/darkriscv.v"
STRICT_UART_FILELIST = "/Users/fundou/my_dv_proj/sv_query/sim/tests/fixtures/strict_uart/filelist.f"

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent  # sv_query/ root (from sim/tests/integration/)


def _run_dataflow(from_signal, to_signal, file_path=None, filelist=None):
    """跑 dataflow analyze 命令, 返回 parsed JSON"""
    cmd = [
        "sv_query", "-q", "dataflow", "analyze",
        from_signal, to_signal,
        "--no-strict",
    ]
    if filelist:
        cmd += ["--filelist", filelist]
    else:
        cmd += ["--file", file_path]
    cmd += ["--json"]

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=60,
        cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        return {"ok": False, "stderr": result.stderr, "stdout": result.stdout}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"JSON decode error: {e}", "stderr": result.stderr}


# ==============================================================================
# Positive tests: 真项目 + 已知 latency ground truth
# ==============================================================================


def test_p1_latency_sync_fifo_2_cycle_push_to_pop():
    """sync_fifo: push_data_i → pop_data_o 应该 2 cycle latency (写 + 读 各 1 cycle)."""
    d = _run_dataflow("sync_fifo.push_data_i", "sync_fifo.pop_data_o", file_path=SYNC_FIFO)
    assert d.get("ok"), f"dataflow failed: {d.get('stderr', d.get('error'))}"

    r = d["result"]
    assert r["is_reachable"], "sync_fifo push → pop should be reachable"
    assert r["primary_latency_cycles"] == 2, (
        f"sync_fifo push → pop should be 2 cycle (write 1 + read 1), "
        f"got {r['primary_latency_cycles']}"
    )
    assert r["primary_is_async"] is False

    p = r["paths"][0]
    assert p["latency_cycles"] == 2
    assert p["is_async_crossing"] is False
    assert "2 sync stages" in p["latency_note"]
    print(f"✅ P1 sync_fifo: latency=2 cycle ({p['latency_note']})")


def test_p2_latency_prim_arbiter_tree_0_cycle_combinational():
    """OpenTitan prim_arbiter_tree: req_i → gnt_o 应该 0 cycle (纯组合 arbiter)."""
    d = _run_dataflow(
        "prim_arbiter_tree.req_i", "prim_arbiter_tree.gnt_o",
        file_path=PRIM_ARBITER,
    )
    assert d.get("ok"), f"dataflow failed: {d.get('stderr', d.get('error'))}"

    r = d["result"]
    assert r["is_reachable"]
    assert r["primary_latency_cycles"] == 0, (
        f"prim_arbiter_tree should be 0 cycle (combinational), "
        f"got {r['primary_latency_cycles']}"
    )

    p = r["paths"][0]
    assert p["latency_cycles"] == 0
    assert p["is_async_crossing"] is False
    assert "no register boundary" in p["latency_note"]
    print(f"✅ P2 prim_arbiter_tree: latency=0 cycle ({p['latency_note']})")


def test_p3_latency_cva6_alu_0_cycle_combinational():
    """CVA6 alu: operand_a → result_o 应该 0 cycle (组合 ALU)."""
    d = _run_dataflow(
        "alu.operand_a", "alu.result_o",
        filelist=CVA6_FILELIST,
    )
    assert d.get("ok"), f"dataflow failed: {d.get('stderr', d.get('error'))}"

    r = d["result"]
    assert r["is_reachable"]
    assert r["primary_latency_cycles"] == 0, (
        f"CVA6 ALU should be 0 cycle (combinational), "
        f"got {r['primary_latency_cycles']}"
    )

    p = r["paths"][0]
    assert p["latency_cycles"] == 0
    assert p["is_async_crossing"] is False
    assert "no register boundary" in p["latency_note"]
    print(f"✅ P3 CVA6 ALU: latency=0 cycle ({p['latency_note']})")


def test_p4_latency_darkriscv_1_cycle_id_ex():
    """darkriscv: IDATA2 → XIDATA 应该 1 cycle latency (ID/EX pipeline REG)."""
    d = _run_dataflow(
        "darkriscv.IDATA2", "darkriscv.XIDATA",
        file_path=DARKRISCV,
    )
    assert d.get("ok"), f"dataflow failed: {d.get('stderr', d.get('error'))}"

    r = d["result"]
    assert r["is_reachable"]
    assert r["primary_latency_cycles"] == 1, (
        f"darkriscv IDATA2 → XIDATA should be 1 cycle (ID/EX REG), "
        f"got {r['primary_latency_cycles']}"
    )

    p = r["paths"][0]
    assert p["latency_cycles"] == 1
    assert p["is_async_crossing"] is False
    assert "1 sync stages" in p["latency_note"]
    print(f"✅ P4 darkriscv: latency=1 cycle ({p['latency_note']})")


def test_p5_latency_stage_breakdown_sync_fifo():
    """sync_fifo stage_breakdown: 验证每个 segment 标 stage_id + is_reg_boundary."""
    d = _run_dataflow("sync_fifo.push_data_i", "sync_fifo.pop_data_o", file_path=SYNC_FIFO)
    assert d.get("ok")

    p = d["result"]["paths"][0]
    sb = p["stage_breakdown"]
    assert len(sb) == 2, f"sync_fifo should have 2 segment breakdown, got {len(sb)}"

    # Segment 0: push_data_i (PORT_IN) → mem (REG)
    s0 = sb[0]
    assert s0["is_reg_boundary"] is True, "mem[] write is REG boundary"
    assert s0["to_kind"] == "REG"
    assert s0["from_kind"] == "PORT_IN"

    # Segment 1: mem (REG) → pop_data_o (REG)
    s1 = sb[1]
    assert s1["is_reg_boundary"] is True, "pop_data_o is REG"
    assert s1["to_kind"] == "REG"

    print(f"✅ P5 stage_breakdown: {len(sb)} segments, both REG boundaries")


# ==============================================================================
# Negative / edge case tests
# ==============================================================================


def test_n1_latency_two_flop_sync_async_crossing():
    """two_flop_sync: sub_a.data_a_i → sub_b.data_b_o 应该 null latency (跨 clk)."""
    d = _run_dataflow(
        "sub_a.data_a_i", "sub_b.data_b_o",
        file_path=TWO_FLOP_SYNC,
    )
    assert d.get("ok"), f"dataflow failed: {d.get('stderr', d.get('error'))}"

    r = d["result"]
    assert r["is_reachable"]
    assert r["primary_latency_cycles"] is None, (
        f"async crossing should be null latency, got {r['primary_latency_cycles']}"
    )
    assert r["primary_is_async"] is True

    p = r["paths"][0]
    assert p["latency_cycles"] is None
    assert p["is_async_crossing"] is True
    assert "async crossing" in p["latency_note"]
    assert "2 clk domains" in p["latency_note"]
    print(f"✅ N1 two_flop_sync: latency=None ({p['latency_note']})")


def test_n2_latency_nonexistent_signal_error():
    """不存在的 signal 应该 ValueError (dataflow 自己会报)."""
    d = _run_dataflow("top.nothing", "top.nothing2", file_path=SYNC_FIFO)
    # dataflow 失败时返 stderr 没 JSON
    assert not d.get("ok") or d.get("result", {}).get("is_reachable") is False
    print("✅ N2 nonexistent signal handled correctly")


# ==============================================================================
# Golden regression test
# ==============================================================================


def test_golden_latency_sync_fifo():
    """[Golden] sync_fifo 完整 latency output 应跟 baseline 一致."""
    golden_path = PROJECT_ROOT / "sim/tests/golden/dataflow_latency_open_source/sync_fifo.json"
    d = _run_dataflow("sync_fifo.push_data_i", "sync_fifo.pop_data_o", file_path=SYNC_FIFO)
    assert d.get("ok")

    if not golden_path.exists():
        # 第一次跑, 创建 golden
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        # 提取稳定字段 (去掉 file path, params)
        stable = {
            "primary_latency_cycles": d["result"]["primary_latency_cycles"],
            "primary_is_async": d["result"]["primary_is_async"],
            "path_0": {
                "latency_cycles": d["result"]["paths"][0]["latency_cycles"],
                "is_async_crossing": d["result"]["paths"][0]["is_async_crossing"],
                "latency_note": d["result"]["paths"][0]["latency_note"],
                "stage_breakdown_count": len(d["result"]["paths"][0]["stage_breakdown"]),
            }
        }
        golden_path.write_text(json.dumps(stable, indent=2))
        pytest.skip(f"Golden created at {golden_path}, re-run to verify")

    golden = json.loads(golden_path.read_text())
    assert d["result"]["primary_latency_cycles"] == golden["primary_latency_cycles"]
    assert d["result"]["primary_is_async"] == golden["primary_is_async"]
    p = d["result"]["paths"][0]
    assert p["latency_cycles"] == golden["path_0"]["latency_cycles"]
    assert p["is_async_crossing"] == golden["path_0"]["is_async_crossing"]
    print("✅ Golden sync_fifo matches baseline")


# ==============================================================================
# 真实项目扩展测试 (2026-07-04 added after C 方案)
# ==============================================================================


def test_real_darkriscv_ifpc_to_iaddr_combinational():
    """[Real] darkriscv: IFPC → IADDR 0 cycle (combinational assign)."""
    d = _run_dataflow("darkriscv.IFPC", "darkriscv.IADDR", file_path=DARKRISCV)
    assert d.get("ok")
    r = d["result"]
    assert r["is_reachable"]
    assert r["primary_latency_cycles"] == 0
    assert r["primary_is_async"] is False
    assert "no register boundary" in r["paths"][0]["latency_note"]
    print(f"✅ darkriscv IFPC→IADDR: 0 cycle (combinational)")


def test_real_darkriscv_idata1_to_idata2_id_stage():
    """[Real] darkriscv: IDATA1 → IDATA2 1 cycle (ID stage REG)."""
    d = _run_dataflow("darkriscv.IDATA1", "darkriscv.IDATA2", file_path=DARKRISCV)
    assert d.get("ok")
    r = d["result"]
    assert r["is_reachable"]
    assert r["primary_latency_cycles"] == 1
    assert r["primary_is_async"] is False
    assert "1 sync stages" in r["paths"][0]["latency_note"]
    print(f"✅ darkriscv IDATA1→IDATA2: 1 cycle (ID stage)")


def test_real_darkriscv_idata2_to_xidata_id_ex():
    """[Real] darkriscv: IDATA2 → XIDATA 1 cycle (ID/EX REG)."""
    d = _run_dataflow("darkriscv.IDATA2", "darkriscv.XIDATA", file_path=DARKRISCV)
    assert d.get("ok")
    r = d["result"]
    assert r["is_reachable"]
    assert r["primary_latency_cycles"] == 1
    print(f"✅ darkriscv IDATA2→XIDATA: 1 cycle (ID/EX)")


def test_real_opentitan_prim_arbiter_combinational():
    """[Real] OpenTitan prim_arbiter_tree: req → gnt 0 cycle (combinational 4 hops)."""
    d = _run_dataflow(
        "prim_arbiter_tree.req_i", "prim_arbiter_tree.gnt_o",
        file_path=PRIM_ARBITER,
    )
    assert d.get("ok")
    r = d["result"]
    assert r["is_reachable"]
    assert r["primary_latency_cycles"] == 0
    print(f"✅ OpenTitan prim_arbiter: 0 cycle (combinational)")


def test_real_opentitan_prim_fifo_sync_passthrough():
    """[Real] OpenTitan prim_fifo_sync: wdata_i → rdata_o 0 cycle (look-ahead pass-through).

    关键发现: prim_fifo_sync 默认 'Pass=1', fifo_empty + wvalid 时 wdata_i 直接透传 (combinational).
    这就是 FWFT (First Word Fall Through) FIFO 特性. 工具报 0 cycle 是**正确的**, 反映设计.
    """
    d = _run_dataflow(
        "prim_fifo_sync.wdata_i", "prim_fifo_sync.rdata_o",
        file_path="/Users/fundou/my_dv_proj/opentitan/hw/ip/prim/rtl/prim_fifo_sync.sv",
    )
    assert d.get("ok")
    r = d["result"]
    assert r["is_reachable"]
    assert r["primary_latency_cycles"] == 0  # pass-through 模式 0 cycle (look-ahead)
    print(f"✅ OpenTitan prim_fifo_sync: 0 cycle (FWFT pass-through, 设计特性)")
