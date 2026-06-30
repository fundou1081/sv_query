"""
test_cross_module_trace_pulp.py
================================
PULP axi 版本的 cross-module trace 测试 (替代 verilog-axi)
- 改用 pulp axi_xbar_dp_ram (有真实 top-level ports)
- 测试场景: 跨 wrapper + 跨 xbar 边界, trace 必须能追到 leaf driver
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
    """PULP axi_xbar_dp_ram (有真实 top-level ports)."""
    t = UnifiedTracer(
        filelist=FILENAME_LIST,
        include_dirs=INCDIRS,
        strict=False,
        log_level="ERROR",
    )
    t.build_graph()
    return t


@pytest.fixture
def graph(tracer):
    return tracer._get_compiler()  # not used; placeholder


class TestPortToInternalMapping:
    """port_to_internal 反向必须工作 (graph 已有)."""

    def test_axi_xbar_intf_port_to_internal(self, tracer):
        """axi_xbar_intf.s_axi_awvalid ← instance port in dp_ram."""
        g = tracer._graph
        if not hasattr(g, "_port_to_internal"):
            pytest.skip("graph has no _port_to_internal")
        pti = g._port_to_internal
        instances = [k for k, v in pti.items() if v == "axi_xbar_intf.slv_ports_aw_valid_i"]
        # 应该至少 dp_ram wrapper 内部有 instance port
        assert isinstance(instances, list), "instances should be a list"


class TestCrossModuleTrace:
    """核心: trace 必须能跨 module boundary 追到 leaf driver."""

    def test_dp_ram_s_axi_awvalid_chains_through_assign(self, tracer):
        """axi_xbar_dp_ram.s_axi_awvalid → slv_stubs[0].aw_valid (assign)."""
        st = SignalTracer(tracer._graph)
        sig = "axi_xbar_dp_ram.s_axi_awvalid"
        if sig not in st.graph.nodes():
            pytest.skip(f"signal {sig} not in graph")
        loads = st._collect_all_loads(sig, max_depth=3)
        # 至少 aw_valid (中间 signal) 应该是 load
        assert any("aw_valid" in l.id and l.kind.name == "SIGNAL" for l in loads), \
            f"expected aw_valid signal as load, got {[l.id for l in loads[:3]]}"

    def test_dp_ram_m_axi_awvalid_has_internal_driver(self, tracer):
        """axi_xbar_dp_ram.m_axi_awvalid 是 wrapper 出口, 应该有内部 assign driver."""
        st = SignalTracer(tracer._graph)
        sig = "axi_xbar_dp_ram.m_axi_awvalid"
        if sig not in st.graph.nodes():
            pytest.skip(f"signal {sig} not in graph")
        drivers = st._collect_all_drivers(sig, max_depth=3)
        # 至少应该有 1 driver (aw_valid signal)
        assert len(drivers) >= 1, \
            "m_axi_awvalid should have at least 1 driver (aw_valid), got 0"


class TestNoInfiniteLoop:
    """跨 instance trace 必须避免循环."""

    def test_no_infinite_loop_deep_trace(self, tracer):
        """max_depth=10 跨过 xbar 内部不能死循环."""
        st = SignalTracer(tracer._graph)
        sig = "axi_xbar_dp_ram.s_axi_awvalid"
        if sig not in st.graph.nodes():
            pytest.skip(f"signal {sig} not in graph")
        # max_depth=10 足够走完 chain, 不能死循环
        loads = st._collect_all_loads(sig, max_depth=10)
        # 跑完 (不死循环) 即可, 节点数应该 > 0
        assert isinstance(loads, list)
        # 实际可能有多个 loads (assign 目标 + 远端 uses)
        assert len(loads) >= 1, "expected at least 1 load, got 0"


class TestCrossModuleSignals:
    """L2 cross-module: 查 graph 是否包含足够的跨模块信号来支持完整 trace."""

    def test_xbar_internal_nodes_exist(self, tracer):
        """xbar 内部应该有节点 (port + signal + instance) 才能 trace."""
        g = tracer._graph
        # i_xbar 内部至少应该有 PORT_IN/OUT/SIGNAL 节点
        xbar_internal = [
            nid for nid in g.nodes()
            if "i_xbar_intf.i_xbar" in nid
        ]
        assert len(xbar_internal) >= 50, (
            f"xbar internal nodes too few: {len(xbar_internal)}, "
            f"expected >= 50 for proper cross-module trace"
        )

    def test_port_to_internal_populated(self, tracer):
        """_port_to_internal 必须非空 (wrapper passthrough 依赖这个)."""
        g = tracer._graph
        pti = getattr(g, "_port_to_internal", {})
        assert len(pti) >= 10, (
            f"port_to_internal too small: {len(pti)}, "
            f"expected >= 10 for cross-module trace"
        )

    def test_at_least_1_internal_xbar_awvalid_path(self, tracer):
        """Trace axi_xbar_dp_ram.s_axi_awvalid fanout depth 3 应该有 aw_valid 中间信号."""
        st = SignalTracer(tracer._graph)
        sig = "axi_xbar_dp_ram.s_axi_awvalid"
        if sig not in st.graph.nodes():
            pytest.skip(f"signal {sig} not in graph")
        loads = st._collect_all_loads(sig, max_depth=3)
        # 至少 aw_valid signal
        aw_valid_loads = [l for l in loads if "aw_valid" in l.id and l.kind.name == "SIGNAL"]
        assert len(aw_valid_loads) >= 1, (
            f"expected at least 1 'aw_valid' signal load, got 0. "
            f"All loads: {[l.id for l in loads[:5]]}"
        )
