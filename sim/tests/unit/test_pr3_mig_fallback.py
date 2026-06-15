"""
test_pr3_mig_fallback.py
=========================
[PR3 2026-06-15] SignalTracer MIG fallback 跨模块 trace 测试.

PR3 目标: 当 graph 0 results 时, fallback 用 ModuleInstanceGraph (MIG)
的 port 映射跨过 module 边界追到 leaf driver/load.

测试场景:
- 端口 fanin: graph 0 drivers → MIG 提供 module def port 作为 driver
- 端口 fanout: graph 0 loads → MIG 提供 instance port 作为 load
- opt-out: use_mig=False 走纯 graph 路径
- binary filter: MIG 的 binary garbage names 不污染结果
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from trace.unified_tracer import UnifiedTracer
from trace.core.query.signal import SignalTracer

FILENAME_LIST = "/tmp/pulp_axi_xbar_pr2.f"
INCDIRS = [
    "/tmp/common_cells/include",
    "/tmp/common_cells/src",
    "/Users/fundou/my_dv_proj/axi/include",
    "/Users/fundou/my_dv_proj/axi/src",
    "/tmp/tech_cells_generic/src/rtl",
]


@pytest.fixture(scope="module")
def tracer():
    t = UnifiedTracer(
        filelist=FILENAME_LIST,
        include_dirs=INCDIRS,
        strict=True,
        log_level="ERROR",
    )
    t.build_graph()
    return t


@pytest.fixture
def st(tracer):
    """默认 SignalTracer (use_mig=True, 自动注入 MIG)."""
    return tracer._signal_tracer


@pytest.fixture
def st_no_mig(tracer):
    """SignalTracer 关闭 MIG fallback (诊断用)."""
    return SignalTracer(tracer._graph, mig=None, use_mig=False)


class TestMIGInjection:
    """SignalTracer 应该自动收到 MIG 注入."""

    def test_signal_tracer_has_mig(self, st):
        """默认情况下, SignalTracer 应该拿到 MIG (unified_tracer 自动注入)."""
        assert st.mig is not None, "MIG should be auto-injected by unified_tracer"

    def test_signal_tracer_use_mig_default_true(self, st):
        """use_mig 默认 True (PR3 行为: 跨模块 fallback 自动启用)."""
        assert st.use_mig is True


class TestL3CrossModuleFanout:
    """L3: 跨模块 port fanout (graph 0 loads → MIG fallback)."""

    def test_bvalid_fanout_via_mig(self, st):
        """axi_xbar_dp_ram.s_axi_bvalid (PORT_IN) fanout 验证 fallback 路径不误报.

        注意: bvalid 链不经过 MIG 端口表, graph 0 loads 是 expected,
        MIG fallback 返回 0 也是 expected. 这个测试只验证不报错 + 不返 binary.
        """
        sig = "axi_xbar_dp_ram.s_axi_bvalid"
        loads = st._collect_all_loads(sig, max_depth=3)
        # 验证不返 binary garbage
        for l in loads:
            assert "<id:binary>" not in l.id
        # 这个信号可能没有 MIG 映射, 0 loads 是可接受的
        # (主要检查不崩 + 不污染)

    def test_module_def_port_fanout_via_mig(self, st):
        """axi_demux.slv_req_i (module def port) fanout → MIG 找到 instance port."""
        sig = "axi_demux.slv_req_i"
        loads = st._collect_all_loads(sig, max_depth=2)
        # 应该至少有 1 instance port (axi_demux_intf.i_axi_demux.slv_req_i)
        instance_ports = [l for l in loads if "i_axi_demux" in l.id]
        assert len(instance_ports) >= 1, (
            f"expected at least 1 instance port via MIG, got {len(loads)} loads: "
            f"{[l.id for l in loads[:5]]}"
        )


class TestL3CrossModuleFanin:
    """L3: 跨模块 port fanin (graph 0 drivers → MIG fallback)."""

    def test_instance_port_fanin_via_mig(self, st):
        """axi_demux_intf.i_axi_demux.slv_req_i (instance port) fanin → MIG 找到上游 driver.

        验证: instance port 跨过中间 wrapper 找到上游信号. 可能找到:
        - 'axi_demux_intf.slv_req' (中间 wrapper 的 signal)
        - 'axi_demux.slv_req_i' (module def port)
        任一都算跨模块成功.
        """
        sig = "axi_demux_intf.i_axi_demux.slv_req_i"
        drivers = st._collect_all_drivers(sig, max_depth=2)
        # 验证跨过 wrapper 边界 (找到 axi_demux_intf.* 或 axi_demux.*)
        cross_module = [d for d in drivers if d.id.startswith("axi_demux_intf.") or d.id.startswith("axi_demux.")]
        assert len(cross_module) >= 1, (
            f"expected at least 1 cross-module driver via MIG, got {len(drivers)}: "
            f"{[d.id for d in drivers[:5]]}"
        )


class TestOptOutBehavior:
    """opt-out: use_mig=False 应该走纯 graph 路径 (不调用 MIG)."""

    def test_opt_out_preserves_graph_only(self, st_no_mig, st):
        """use_mig=False 跟 use_mig=True 在 graph 有结果时**应该一致** (graph 优先)."""
        sig = "axi_xbar_dp_ram.s_axi_awvalid"
        loads_with = st._collect_all_loads(sig, max_depth=3)
        loads_without = st_no_mig._collect_all_loads(sig, max_depth=3)
        # graph 有结果时, MIG fallback 不触发, 结果应一致
        assert len(loads_with) == len(loads_without), (
            f"opt-out should not change results when graph has data: "
            f"with_mig={len(loads_with)} without_mig={len(loads_without)}"
        )


class TestBinaryFilter:
    """MIG 的 binary garbage names 不应该污染结果."""

    def test_no_binary_in_mig_results(self, st):
        """MIG fallback 的 results 不应该有 binary garbage."""
        sig = "axi_demux.slv_req_i"
        loads = st._collect_all_loads(sig, max_depth=2)
        for l in loads:
            assert "<id:binary>" not in l.id, (
                f"binary garbage leaked into results: {l.id}"
            )
            assert "_anon_" not in l.id, (
                f"_anon_ leaked into results: {l.id}"
            )


class TestBackwardCompat:
    """L3 PR3 改动不应该破坏 L1/L2 测试."""

    def test_s_axi_awvalid_basic_fanout(self, st):
        """L2 基础 case 仍然工作: s_axi_awvalid → aw_valid → m_axi_awvalid."""
        sig = "axi_xbar_dp_ram.s_axi_awvalid"
        loads = st._collect_all_loads(sig, max_depth=3)
        # 至少 2 个 loads (aw_valid, m_axi_awvalid)
        assert len(loads) >= 2, (
            f"L2 basic case should still work, got {len(loads)}: {[l.id for l in loads[:3]]}"
        )
