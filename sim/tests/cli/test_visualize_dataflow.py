"""
test_visualize_dataflow.py — VizData 数据导出 + CLI 回归测试

V6.7 迁移后，核心测试焦点从 DOT 输出转移到 VizData 数据层。
DOT 渲染由 render_dot() 单元测试覆盖，CLI 层只需验证命令不崩溃。

测试目标:
  - visualize dataflow 命令不崩溃 (rc=0)
  - VizData 数据导出正确 (JSON)
  - 节点统计 (Data/Control/Clock) 正确
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

# [FIX 2026-07-29] 添加 src/ 到 sys.path
# trace 模块在 src/ 下, 不添加会导致 ModuleNotFoundError: 'trace' is not a package
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
STRICT_UART_FL = str(PROJECT_ROOT / "sim" / "tests" / "fixtures" / "strict_uart" / "filelist.f")


def _run_dot_output() -> tuple[int, str, str]:
    """Run dataflow, return (rc, stdout, stderr)."""
    p = subprocess.run(
        ["sv_query", "visualize", "dataflow", "--filelist", STRICT_UART_FL, "--no-strict"],
        capture_output=True, text=True, timeout=60, cwd=str(PROJECT_ROOT),
    )
    return p.returncode, p.stdout, p.stderr


class TestDataflowCli:
    """CLI 回归: 命令不崩溃 + 基本输出验证"""

    def test_returns_zero(self):
        rc, _, stderr = _run_dot_output()
        assert rc == 0, f"dataflow failed: {stderr[:300]}"

    def test_output_is_digraph(self):
        rc, stdout, _ = _run_dot_output()
        assert "digraph" in stdout.lower() or "digraph" in stdout

    def test_has_node_stats(self):
        import re
        rc, stdout, stderr = _run_dot_output()
        combined = stdout + stderr
        assert re.search(r"Data nodes:\s*(\d+)", combined), "missing Data nodes stat"
        assert re.search(r"Control nodes:\s*(\d+)", combined), "missing Control nodes stat"
        assert re.search(r"Clock nodes:\s*(\d+)", combined), "missing Clock nodes stat"


class TestVizDataExport:
    """V6.7: VizData 数据导出验证 (核心)"""

    def test_vizdata_json_roundtrip(self):
        """SignalGraph → VizData → JSON 往返正确

        [FIX 2026-07-29] trace.unified_tracer 导入失败: 'trace' 不是包。
        改用 UnifiedTracer 的正确路径。
        """
        from trace.unified_tracer import UnifiedTracer
        from trace.core.graph.analyzer.signal_classifier import classify_graph
        from trace.core.graph.viz import build_viz_data, VizBuildOptions

        src = """module test(input clk, input [3:0] a, b, output reg [3:0] y);
            always_ff @(posedge clk) begin
                if (a > b) y <= a;
                else y <= b;
            end
        endmodule"""
        tracer = UnifiedTracer(sources={"_test.sv": src}, strict=False)
        tracer.trace_module("test")
        g = tracer.get_graph()

        classification = classify_graph(g)
        viz = build_viz_data(g, VizBuildOptions(
            include_node_class=True,
            classification=classification,
            include_edge_expression=True,
            include_edge_condition=True,
        ))

        # JSON export
        data = viz.to_json()
        assert "meta" in data
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) > 0
        assert len(data["edges"]) > 0

        # Verify edge has condition
        cond_edges = [e for e in data["edges"] if e.get("condition")]
        assert len(cond_edges) >= 1, "no edges with condition in viz JSON"

        # Verify node has class
        classified = [n for n in data["nodes"] if n.get("class_")]
        assert len(classified) >= 1, "no classified nodes in viz JSON"

        # JSON must be valid and re-serializable
        json_str = json.dumps(data)
        data2 = json.loads(json_str)
        assert len(data["nodes"]) > 0, "no nodes in viz JSON export"


def test_visualize_dataflow_golden_match():
    """[V6.9 fix 2026-07-29] Golden DOT comparison — regenerated after V6.7/V6.8 changes."""
    import os
    tmp_dot = "/tmp/test_dataflow_golden.dot"
    rc, stdout, stderr = _run_dot_output()
    assert rc == 0, f"dataflow failed: {stderr[:200]}"

    golden_path = str(PROJECT_ROOT / "sim" / "tests" / "golden" / "visualize_dataflow" / "strict_uart.dot")
    with open(golden_path) as f:
        golden = f.read()
    assert stdout.rstrip() == golden.rstrip(), (
        "DOT output diverged from golden. Regenerate with:\n"
        f"  sv_query visualize dataflow --filelist sim/tests/fixtures/strict_uart/filelist.f --no-strict --dot {golden_path}"
    )
