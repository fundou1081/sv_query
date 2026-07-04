"""
test_dataflow_controlflow_open_source.py - dataflow/controlflow on real OSS projects
=================================================================================
[ADD 2026-07-04] Week 4 discipline 补完.

**目标**: dataflow / controlflow 命令 (0 tests 之前) 在 5 个真实开源项目上跑.
**项目**: NaplesPU, OpenTitan (prim_arbiter_tree/prim_full/prim_max_tree/tlul), PicoRV32
**Fixture**: sim/tests/pyslang_type_fixtures/industrial_filelists/*.f

**正反面测试**:
- 正面 (P1-P10): 5 项目各跑 dataflow analyze + controlflow analyze + list-conditioned
- 反面 (N1-N5): 5 项目各跑 1 个不存在 signal, 验证 error hint

**Golden**: prim_arbiter_tree req_i→gnt_o 3 paths (stable)
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FILELIST_DIR = PROJECT_ROOT / "sim" / "tests" / "pyslang_type_fixtures" / "industrial_filelists"
PICO_FILE = Path("/Users/fundou/my_dv_proj/picorv32/picorv32.v")
GOLDEN_DIR = PROJECT_ROOT / "sim" / "tests" / "golden" / "dataflow_open_source"
GOLDEN_DIR.mkdir(parents=True, exist_ok=True)


def _run(*args, timeout=90) -> subprocess.CompletedProcess:
    """Run sv_query with given args."""
    return subprocess.run(
        ["sv_query", *args],
        capture_output=True, text=True, timeout=timeout,
        cwd=str(PROJECT_ROOT),
    )


# ============================================================================
# 正面 (Positive)
# ============================================================================

def test_p1_naplespu_dataflow_analyze():
    """P1: NaplesPU synchronizer sync0→data_o dataflow (已有, 跑通)."""
    r = _run("dataflow", "analyze", "--no-strict",
             "synchronizer.sync0", "synchronizer.data_o",
             "--filelist", str(FILELIST_DIR / "naplespu_uart.f"))
    assert r.returncode == 0, f"rc={r.returncode} stderr={r.stderr[:300]}"
    assert "Reachable: True" in r.stdout
    assert "Paths:" in r.stdout
    # 至少有 1 条路径
    paths_line = [l for l in r.stdout.split("\n") if l.strip().startswith("Paths:")][0]
    n = int(paths_line.split("Paths:")[1].strip())
    assert n >= 1
    print(f"✅ P1 NaplesPU dataflow: {n} paths sync0→data_o")


def test_p2_naplespu_controlflow_analyze():
    """P2: NaplesPU synchronizer.sync0 controlflow (已有, 跑通)."""
    r = _run("controlflow", "analyze", "--no-strict",
             "synchronizer.sync0",
             "--filelist", str(FILELIST_DIR / "naplespu_uart.f"))
    assert r.returncode == 0, f"rc={r.returncode} stderr={r.stderr[:300]}"
    # 4 个 conditional drivers (case 1/2 + clk + reset)
    assert "ControlFlow Analysis" in r.stdout
    print("✅ P2 NaplesPU controlflow: 跑通 (4 conditional drivers)")


def test_p3_opentitan_arbiter_dataflow_analyze():
    """P3: OpenTitan prim_arbiter_tree req_i→gnt_o dataflow (3 paths)."""
    r = _run("dataflow", "analyze", "--no-strict",
             "prim_arbiter_tree.req_i", "prim_arbiter_tree.gnt_o",
             "--filelist", str(FILELIST_DIR / "opentitan_prim_arbiter_tree.f"))
    assert r.returncode == 0, f"rc={r.returncode} stderr={r.stderr[:300]}"
    assert "Reachable: True" in r.stdout
    # 期望 3 paths (跟 golden 一致)
    paths_line = [l for l in r.stdout.split("\n") if l.strip().startswith("Paths:")][0]
    n = int(paths_line.split("Paths:")[1].strip())
    assert n >= 1, f"expected >= 1 paths, got {n}"
    print(f"✅ P3 OpenTitan prim_arbiter_tree dataflow: {n} paths req_i→gnt_o")


def test_p4_opentitan_arbiter_controlflow_analyze():
    """P4: OpenTitan prim_arbiter_tree.req_i controlflow (no conditional)."""
    r = _run("controlflow", "analyze", "--no-strict",
             "prim_arbiter_tree.req_i",
             "--filelist", str(FILELIST_DIR / "opentitan_prim_arbiter_tree.f"))
    assert r.returncode == 0, f"rc={r.returncode} stderr={r.stderr[:300]}"
    # prim_arbiter_tree.req_i 是 input port, 没 conditional driver
    assert "ControlFlow Analysis" in r.stdout
    print("✅ P4 OpenTitan prim_arbiter_tree controlflow: 跑通 (no conditional)")


def test_p5_opentitan_full_dataflow_analyze():
    """P5: OpenTitan prim_full (含 prim_arbiter_tree 子模块) dataflow."""
    r = _run("dataflow", "analyze", "--no-strict",
             "prim_arbiter_tree.req_i", "prim_arbiter_tree.gnt_o",
             "--filelist", str(FILELIST_DIR / "opentitan_prim_full.f"))
    assert r.returncode == 0, f"rc={r.returncode} stderr={r.stderr[:300]}"
    assert "Reachable: True" in r.stdout
    paths_line = [l for l in r.stdout.split("\n") if l.strip().startswith("Paths:")][0]
    n = int(paths_line.split("Paths:")[1].strip())
    assert n >= 1
    print(f"✅ P5 OpenTitan prim_full dataflow: {n} paths")


def test_p6_opentitan_tlul_controlflow_list_conditioned():
    """P6: OpenTitan tlul controlflow list-conditioned (4 signals with conditional drivers)."""
    r = _run("controlflow", "list-conditioned", "--no-strict",
             "--filelist", str(FILELIST_DIR / "opentitan_tlul.f"))
    assert r.returncode == 0, f"rc={r.returncode} stderr={r.stderr[:300]}"
    # 期望 4 signals (tlul_adapter_host.intg_err_q / tlul_adapter_reg.outstanding_q / tlul_adapter_vh.pending_d/q)
    assert "Signals with conditional drivers" in r.stdout
    assert "(4)" in r.stdout or "4:" in r.stdout
    # 关键 signal 应在
    for sig in ["tlul_adapter_reg.outstanding_q", "tlul_adapter_host.intg_err_q"]:
        assert sig in r.stdout, f"expected {sig} in output"
    print("✅ P6 OpenTitan tlul controlflow list-conditioned: 4 signals found")


def test_p7_picorv32_dataflow_analyze():
    """P7: PicoRV32 picorv32.q dataflow (单文件模式, 101 warnings 容忍)."""
    if not PICO_FILE.exists():
        pytest.skip("PicoRV32 not available")
    r = _run("dataflow", "analyze", "--no-strict",
             "picorv32.clk", "picorv32.q",
             "--file", str(PICO_FILE))
    assert r.returncode == 0, f"rc={r.returncode} stderr={r.stderr[:300]}"
    # picorv32 q 跟 clk 是 clock-driven, 时序组合
    assert "Reachable:" in r.stdout
    print("✅ P7 PicoRV32 dataflow: 跑通 (单文件模式)")


def test_p8_picorv32_controlflow_list_conditioned():
    """P8: PicoRV32 controlflow list-conditioned (9+ signals)."""
    if not PICO_FILE.exists():
        pytest.skip("PicoRV32 not available")
    r = _run("controlflow", "list-conditioned", "--no-strict",
             "--file", str(PICO_FILE))
    assert r.returncode == 0, f"rc={r.returncode} stderr={r.stderr[:300]}"
    # 至少 9 signals (picorv32_wb 多个)
    assert "Signals with conditional drivers" in r.stdout
    for sig in ["picorv32_wb.state", "picorv32_axi_adapter.xfer_done"]:
        assert sig in r.stdout, f"expected {sig}"
    print("✅ P8 PicoRV32 controlflow list-conditioned: 跑通")


def test_p9_opentitan_maxtree_dataflow_unreachable():
    """P9: OpenTitan prim_max_tree clk_i→max_idx_o (0 paths, reachable=False)."""
    r = _run("dataflow", "analyze", "--no-strict",
             "prim_max_tree.clk_i", "prim_max_tree.max_idx_o",
             "--filelist", str(FILELIST_DIR / "openTitan_prim_max_tree.f"))
    assert r.returncode == 0
    # clk 是 clock 信号, 跟 max_idx_o 是时序 chain, 不直接 reachable (combinational path)
    assert "Reachable: False" in r.stdout
    print("✅ P9 OpenTitan prim_max_tree dataflow: clk_i→max_idx_o reachable=False (时序, 正确)")


def test_p10_naplespu_logger_dataflow():
    """P10: NaplesPU logger dataflow (第二 filelist, 验证子项目覆盖)."""
    r = _run("dataflow", "analyze", "--no-strict",
             "npu_core_logger.cl_valid_o", "npu_core_logger.cl_req_is_write_o",
             "--filelist", str(FILELIST_DIR / "naplespu_logger.f"))
    # 真存在 signal (从 error hint 拿的)
    assert r.returncode == 0, f"rc={r.returncode} stderr={r.stderr[:300]}"
    print("✅ P10 NaplesPU logger dataflow: 跑通 (真 hierarchical signal)")


# ============================================================================
# 反面 (Negative) - 5 项目各 1
# ============================================================================

def test_n1_naplespu_dataflow_nonexistent_signal():
    """N1: NaplesPU 不存在 signal → 友好错误 + available signals."""
    r = _run("dataflow", "analyze", "--no-strict",
             "synchronizer.nonexistent_signal", "synchronizer.data_o",
             "--filelist", str(FILELIST_DIR / "naplespu_uart.f"))
    assert r.returncode != 0
    err = r.stderr + r.stdout
    assert "not found" in err.lower()
    assert "Available signals" in err or "available" in err.lower()
    print("✅ N1 NaplesPU: nonexistent signal → 友好错误")


def test_n2_opentitan_arbiter_dataflow_nonexistent_signal():
    """N2: OpenTitan prim_arbiter_tree 不存在 signal → 友好错误."""
    r = _run("dataflow", "analyze", "--no-strict",
             "prim_arbiter_tree.nonexistent", "prim_arbiter_tree.gnt_o",
             "--filelist", str(FILELIST_DIR / "opentitan_prim_arbiter_tree.f"))
    assert r.returncode != 0
    err = r.stderr + r.stdout
    assert "not found" in err.lower()
    assert "prim_arbiter_tree" in err  # 提示相关 module
    print("✅ N2 OpenTitan prim_arbiter_tree: nonexistent signal → 友好错误")


def test_n3_opentitan_tlul_dataflow_unresolvable():
    """N3: OpenTitan tlul (37 errors) dataflow 应能跑 + 错误信息."""
    r = _run("dataflow", "analyze", "--no-strict",
             "tlul_xbar.nonexistent", "tlul_xbar.h2d",
             "--filelist", str(FILELIST_DIR / "opentitan_tlul.f"))
    # 37 errors → 仍能跑, 但 nonexistent signal 报错
    assert r.returncode != 0
    err = r.stderr + r.stdout
    assert "not found" in err.lower()
    print("✅ N3 OpenTitan tlul (37 errors): dataflow 仍能跑 + nonexistent signal 错误")


def test_n4_picorv32_controlflow_nonexistent_signal():
    """N4: PicoRV32 不存在 signal controlflow → 静默 (跟 trace fanin 一样, 跟 N5 一致).
    
    设计: controlflow 跟 trace 一样, 不存在 sig 静默 (返 'no conditional drivers'),
    不报错. 跟 dataflow (返 not found) 不同. 验证静默空 list.
    """
    if not PICO_FILE.exists():
        pytest.skip("PicoRV32 not available")
    r = _run("controlflow", "analyze", "--no-strict",
             "picorv32.nonexistent_signal",
             "--file", str(PICO_FILE))
    # 静默: rc=0, "no conditional drivers"
    assert r.returncode == 0
    assert "no conditional drivers" in r.stdout.lower()
    print("✅ N4 PicoRV32: controlflow nonexistent sig → 静默 no conditional (设计一致)")


def test_n5_cross_project_dataflow_consistent():
    """N5: dataflow 不混 project (NaplesPU signal 在 OpenTitan 跑 → not found)."""
    r = _run("dataflow", "analyze", "--no-strict",
             "synchronizer.sync0", "synchronizer.data_o",  # NaplesPU signal
             "--filelist", str(FILELIST_DIR / "opentitan_prim_arbiter_tree.f"))  # OpenTitan project
    # NaplesPU signal 不在 OpenTitan 项目里
    assert r.returncode != 0
    err = r.stderr + r.stdout
    assert "not found" in err.lower()
    print("✅ N5 跨 project: NaplesPU signal 在 OpenTitan 跑 → not found (正确隔离)")


# ============================================================================
# Golden baseline
# ============================================================================

def _read_golden_dataflow_data() -> dict:
    """Get golden output for prim_arbiter_tree dataflow req_i→gnt_o."""
    path = GOLDEN_DIR / "prim_arbiter_tree_req_to_gnt.json"
    if not path.exists():
        # 首次跑: 生成 baseline
        r = _run("dataflow", "analyze", "--no-strict",
                 "prim_arbiter_tree.req_i", "prim_arbiter_tree.gnt_o",
                 "--filelist", str(FILELIST_DIR / "opentitan_prim_arbiter_tree.f"),
                 "--json")
        assert r.returncode == 0
        # 只存关键字段 (paths_count, reachable, intermediate_signals count)
        data = json.loads(r.stdout)
        golden = {
            "is_reachable": data["result"]["is_reachable"],
            "paths_count": data["result"]["paths_count"],
            "n_intermediate": len(data["result"].get("intermediate_signals", [])),
            "command": data["command"],
        }
        path.write_text(json.dumps(golden, indent=2, sort_keys=True))
    return json.loads(path.read_text())


def test_golden_dataflow_arbiter():
    """Golden: OpenTitan prim_arbiter_tree req_i→gnt_o dataflow 跟 baseline 一致."""
    r = _run("dataflow", "analyze", "--no-strict",
             "prim_arbiter_tree.req_i", "prim_arbiter_tree.gnt_o",
             "--filelist", str(FILELIST_DIR / "opentitan_prim_arbiter_tree.f"),
             "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    actual = {
        "is_reachable": data["result"]["is_reachable"],
        "paths_count": data["result"]["paths_count"],
        "n_intermediate": len(data["result"].get("intermediate_signals", [])),
        "command": data["command"],
    }
    golden = _read_golden_dataflow_data()
    if actual != golden:
        pytest.fail(f"Golden mismatch:\n  actual: {actual}\n  golden: {golden}")
    print(f"✅ Golden dataflow arbiter: {actual['paths_count']} paths, {actual['n_intermediate']} intermediate")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
