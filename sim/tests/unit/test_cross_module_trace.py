"""
test_cross_module_trace.py
=============================
修复: filelist 跨模块 trace 找不到 deep drivers

Bug: 实际 SV 实战 (verilog-axi axi_dp_ram) 跑 backpressure analyze 时,
     95 边里 56 边是 UNKNOWN, 11 节点是 UNUSED. 根因是 graph 跨模块 trace 失败.

症状链:
  axi_dp_ram.s_axi_a_awready (top port)
    → driver: axi_dp_ram.a_if.s_axi_awready (instance port)  ✅
  axi_dp_ram.a_if.s_axi_awready (instance port, kind=PORT_OUT)
    → driver: axi_ram_wr_rd_if.s_axi_awready (via port_to_internal)  ✅
  axi_ram_wr_rd_if.s_axi_awready (wrapper module def, no internal assign)
    → driver: 0  ❌  (应该有: axi_ram_wr_if.s_axi_awready_reg via port mapping)

根因: SignalTracer._trace_drivers_recursive 当 target 是 module def PORT_OUT 且
      0 driver edge 时停止, 没反向查 port_to_internal 找 instance port 继续 trace.

修复: 在 _trace_drivers_recursive 末尾, 如果当前 signal 是 PORT_OUT 且 0 driver
      找到, 查 port_to_internal 反向找所有 instance port, 递归追它们的 driver.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from applications.bus.sv_extractor import SVSignalExtractor
from trace.core.query.signal import SignalTracer


@pytest.fixture(scope="module")
def verilog_axi_extractor():
    """verilog-axi filelist (52 模块, 多层 wrapper, 经典 backpressure 测试)."""
    ext = SVSignalExtractor.from_filelist('/tmp/verilog-axi.f')
    ext.extract_all_modules()
    return ext


@pytest.fixture(scope="module")
def graph(verilog_axi_extractor):
    tracer = verilog_axi_extractor._get_tracer()
    return tracer.build_graph()


@pytest.fixture(scope="module")
def tracer(graph):
    return SignalTracer(graph)


class TestPortToInternalMapping:
    """基础: port_to_internal 反向必须工作 (graph 已有)."""

    def test_module_def_to_instance_port(self, graph):
        """axi_ram_wr_rd_if.s_axi_awready ← 它的 instance ports."""
        pti = graph._port_to_internal
        instances = [k for k, v in pti.items() if v == "axi_ram_wr_rd_if.s_axi_awready"]
        assert len(instances) >= 1, "port_to_internal reverse 应该有 1+ instance"
        assert "axi_dp_ram.a_if.s_axi_awready" in instances
        assert "axi_dp_ram.b_if.s_axi_awready" in instances

    def test_leaf_module_to_instance_port(self, graph):
        """axi_ram_wr_if.s_axi_awready ← 它的 instance port."""
        pti = graph._port_to_internal
        instances = [k for k, v in pti.items() if v == "axi_ram_wr_if.s_axi_awready"]
        # axi_ram_wr_if 被 axi_dp_ram.b_if 实例化
        assert any("axi_ram_wr_if" in k for k in instances)


class TestCrossModuleTrace:
    """核心测试: trace 必须能跨 module boundary 追到 leaf module 的 driver."""

    def test_wrapper_module_def_awready_finds_driver(self, tracer):
        """axi_ram_wr_rd_if.s_axi_awready (wrapper, 0 internal assign)
        应该有 driver (跨 instance 追到 axi_ram_wr_if.s_axi_awready_reg)."""
        sig = "axi_ram_wr_rd_if.s_axi_awready"
        assert sig in tracer.graph.nodes()
        drivers = tracer._collect_all_drivers(sig, max_depth=5)
        # 跨 instance 应该能找到 driver
        assert len(drivers) > 0, (
            f"❌ trace 跨 module boundary 失败! "
            f"axi_ram_wr_rd_if.s_axi_awready 是 wrapper, 应该有 driver "
            f"(来自 axi_ram_wr_if instance). "
            f"实际 0 driver → handshake detector 返 UNKNOWN/UNUSED."
        )

    def test_deep_hierarchy_top_port_finds_leaf_reg(self, tracer):
        """axi_dp_ram.s_axi_a_awready (top, 2 层 instance 嵌套) 
        跨 trace 找到 axi_ram_wr_if.s_axi_awready_reg."""
        sig = "axi_dp_ram.s_axi_a_awready"
        assert sig in tracer.graph.nodes()
        drivers = tracer._collect_all_drivers(sig, max_depth=10)
        # 找 leaf reg
        reg_drivers = [d for d in drivers if d.kind.name == "REG"]
        assert len(reg_drivers) > 0, (
            f"❌ deep trace 应该找到 leaf REG driver (axi_ram_wr_if.s_axi_awready_reg), "
            f"实际找到 {len(drivers)} drivers: {[d.id for d in drivers[:5]]}"
        )

    def test_crossbar_awvalid_finds_master_driver(self, tracer):
        """axi_interconnect.m_axi_awvalid 应该跨过 crossbar 找到 axi_cdma 之类的 master driver."""
        sig = "axi_interconnect.m_axi_awvalid"
        assert sig in tracer.graph.nodes()
        drivers = tracer._collect_all_drivers(sig, max_depth=10)
        # interconnect 内部 reg/assign 应该是 driver
        assert len(drivers) > 0, (
            f"❌ interconnect 的 m_axi_awvalid 应该有 driver (内部 reg or 上游 master)"
        )


class TestNoInfiniteLoop:
    """跨 instance trace 必须避免循环 (axi_ram_wr_rd_if ↔ axi_dp_ram.a_if)."""

    def test_no_infinite_loop_on_cyclic_instance(self, tracer):
        """axi_ram_wr_rd_if.s_axi_awready 跨到 axi_dp_ram.a_if.s_axi_awready,
        不能再跨回 axi_ram_wr_rd_if (否则死循环)."""
        sig = "axi_ram_wr_rd_if.s_axi_awready"
        # max_depth=10 足够走完 chain (不能死循环)
        drivers = tracer._collect_all_drivers(sig, max_depth=10)
        # 应该能在有限 steps 找到 leaf reg (证明没死循环)
        reg_ids = [d.id for d in drivers if d.kind.name == "REG"]
        assert any("axi_ram_wr_if" in r for r in reg_ids), (
            f"❌ 应该找到 axi_ram_wr_if.s_axi_awready_reg, 实际: {reg_ids}"
        )
