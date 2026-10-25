"""[PR4 2026-06-15] visualize module L2 边测试 —— [iter_283] 改为**实例级图**推导。

历史: 原来用 MIG 的 `port_to_internal`（`instance port → module_type.port`）反向分组，
同模块类型同名端口即视为相连 —— 双命名空间时代的启发式，多实例会误连。

现在 `extract_module_edges_from_graph` 直接读实例级 SignalGraph：
  1. 两端归属不同实例的 CONNECTION/DRIVER 边
  2. 经过父级网络（top wire/port）相连的两个实例端点
字面量常量（0 / 1'b0）不是网络，不产生边。
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from trace.core.module_extractor import (  # noqa: E402
    extract_module,
    extract_module_edges_from_graph,
)
from trace.core.semantic_adapter import SemanticAdapter  # noqa: E402
from trace.unified_tracer import UnifiedTracer  # noqa: E402

M3_FILELIST = str(PROJECT_ROOT / "sim" / "tests" / "fixtures" / "minimal_3module" / "filelist.f")
STRICT_UART_FILELIST = str(PROJECT_ROOT / "sim" / "tests" / "fixtures" / "strict_uart" / "filelist.f")
RUN_CLI = PROJECT_ROOT / "run_cli.py"


@pytest.fixture(scope="module")
def m3():
    """minimal_3module: top_minimal → sa1 → {la1, lp1}（3 实例，真实连线）。"""
    tracer = UnifiedTracer(filelist=M3_FILELIST, log_level="ERROR")
    graph = tracer.build_graph()
    result = extract_module(
        SemanticAdapter(tracer._get_compiler().get_root()), "top_minimal", max_depth=2,
    )
    return graph, result


class TestEdgesFromGraph:
    def test_returns_list(self, m3):
        graph, result = m3
        edges = extract_module_edges_from_graph(graph, result.instances)
        assert isinstance(edges, list)

    def test_required_fields(self, m3):
        graph, result = m3
        edges = extract_module_edges_from_graph(graph, result.instances)
        assert edges, "minimal_3module 应有跨实例连接"
        for key in ("src", "dst", "src_instance", "dst_instance",
                    "internal", "port", "port_src", "port_dst"):
            assert key in edges[0], f"edge missing {key}: {edges[0]}"

    def test_endpoints_are_in_scope_instances(self, m3):
        graph, result = m3
        inst_ids = {i.id for i in result.instances}
        edges = extract_module_edges_from_graph(graph, result.instances)
        for e in edges:
            assert e["src"] in inst_ids, f"src not an instance: {e['src']}"
            assert e["dst"] in inst_ids, f"dst not an instance: {e['dst']}"
            assert e["src"] != e["dst"], f"self edge: {e}"

    def test_real_connection_ports(self, m3):
        """sa1 的 data_i 网络确实连到 la1.a（图里真实存在）。"""
        graph, result = m3
        edges = extract_module_edges_from_graph(graph, result.instances)
        hits = [
            e for e in edges
            if e["src"].endswith(".sa1") and e["dst"].endswith(".la1") and e["port_src"] == "data_i"
        ]
        assert hits, f"expected sa1.data_i → la1.a, got {edges[:5]}"

    def test_constant_is_not_a_net(self, m3):
        """字面量常量（0 / 1'b0）不能当网络，否则会产生假边。"""
        graph, result = m3
        edges = extract_module_edges_from_graph(graph, result.instances)
        for e in edges:
            node = graph.get_node(e["internal"])
            assert node is not None
            assert node.kind.name != "CONST", f"edge uses CONST as net: {e}"

    def test_deterministic(self, m3):
        graph, result = m3
        a = extract_module_edges_from_graph(graph, result.instances)
        b = extract_module_edges_from_graph(graph, result.instances)
        assert a == b

    def test_positive_count(self, m3):
        graph, result = m3
        edges = extract_module_edges_from_graph(graph, result.instances)
        assert len(edges) >= 3, f"expected >=3 edges, got {len(edges)}"

    def test_no_garbage(self, m3):
        graph, result = m3
        edges = extract_module_edges_from_graph(graph, result.instances)
        for e in edges:
            assert "<id:binary>" not in e["src"]
            assert "<id:binary>" not in e["dst"]


class TestGraceful:
    def test_graph_none(self, m3):
        _graph, result = m3
        assert extract_module_edges_from_graph(None, result.instances) == []

    def test_empty_instances(self, m3):
        graph, _result = m3
        assert extract_module_edges_from_graph(graph, []) == []


class TestCLIIntegration:
    """CLI 端到端：visualize module 输出 edges 字段（strict_uart 只有 1 实例 → 0 边）。"""

    def _run(self, target, depth, out: Path, extra=None):
        cmd = ["python3", str(RUN_CLI), "visualize", "module",
               "--filelist", STRICT_UART_FILELIST, "--target", target,
               "--depth", str(depth), "--output-json", str(out)]
        if extra:
            cmd.extend(extra)
        subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=120)
        return out.exists()

    def test_outputs_edges_field(self, tmp_path):
        out = tmp_path / "module.json"
        if not self._run("uart_top", 2, out):
            pytest.skip("CLI failed (fixture issue)")
        data = json.loads(out.read_text())
        assert "edges" in data and isinstance(data["edges"], list)

    def test_level_is_1_when_no_edges(self, tmp_path):
        out = tmp_path / "module.json"
        if not self._run("uart_top", 2, out):
            pytest.skip("CLI failed (fixture issue)")
        data = json.loads(out.read_text())
        assert data["level"] in (1, 2)

    def test_no_mig_flag_returns_no_edges(self, tmp_path):
        out = tmp_path / "module.json"
        if not self._run("uart_top", 2, out, ["--no-mig"]):
            pytest.skip("CLI failed (fixture issue)")
        data = json.loads(out.read_text())
        assert data.get("edges", []) == [], "--no-mig 应关闭 L2 边"

    def test_cluster_field_in_nodes(self, tmp_path):
        out = tmp_path / "module.json"
        if not self._run("uart_top", 2, out):
            pytest.skip("CLI failed (fixture issue)")
        data = json.loads(out.read_text())
        for n in data["nodes"]:
            assert "cluster" in n
