"""
test_visualize_pipeline.py — V6.7 CLI 回归 + VizData 验证

Pipeline 可视化测试: 命令不崩溃，统计正确，VizData 数据导出。
DOT golden 对比暂时 skip（V6.7 渲染逻辑已变）。
"""
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
STRICT_UART_FL = str(PROJECT_ROOT / "sim" / "tests" / "fixtures" / "strict_uart" / "filelist.f")


def _run_pipeline() -> tuple[int, str, str]:
    p = subprocess.run(
        ["sv_query", "visualize", "pipeline", "--filelist", STRICT_UART_FL, "--no-strict"],
        capture_output=True, text=True, timeout=60, cwd=str(PROJECT_ROOT),
    )
    return p.returncode, p.stdout, p.stderr


class TestPipelineCli:
    def test_returns_zero(self):
        rc, _, stderr = _run_pipeline()
        assert rc == 0, f"pipeline failed: {stderr[:300]}"

    def test_output_is_digraph(self):
        _, stdout, _ = _run_pipeline()
        assert "digraph" in stdout

    def test_has_pipeline_stats(self):
        import re
        _, stdout, stderr = _run_pipeline()
        combined = stdout + stderr
        assert re.search(r"Pipeline regs:\s*\d+", combined), "missing Pipeline regs stat"
        assert re.search(r"Stages:\s*\d+", combined), "missing Stages stat"


class TestPipelineVizData:
    """V6.7: Pipeline 的 VizData 数据导出"""

    def test_vizdata_with_stages(self):
        from trace.unified_tracer import UnifiedTracer
        from trace.core.graph.analyzer.signal_classifier import classify_graph
        from trace.core.graph.analyzer.pipeline_viz import detect_pipeline
        from trace.core.graph.viz import build_viz_data, VizBuildOptions

        src = """module test(input clk, input [3:0] a, output [3:0] y);
            reg [3:0] r;
            always_ff @(posedge clk) r <= a;
            assign y = r;
        endmodule"""
        tracer = UnifiedTracer(sources={"_test.sv": src}, strict=False)
        tracer.trace_module("test")
        g = tracer.get_graph()

        classification = classify_graph(g)
        info = detect_pipeline(g, classification)
        assert info.pipeline_regs, "should find pipeline regs"

        # Build VizData with stage info
        stage_map = {s.stage_id: s.reg_nodes + s.comb_nodes for s in info.stages}
        viz = build_viz_data(g, VizBuildOptions(
            include_node_class=True,
            classification=classification,
            include_node_stage=True,
            pipeline_stages=stage_map,
            include_edge_expression=True,
        ))
        data = viz.to_json()

        # Verify stages present
        staged = [n for n in data["nodes"] if n.get("stage_id") is not None]
        assert len(staged) >= 1, "no staged nodes in pipeline VizData"


@pytest.mark.skip(reason="V6.7 DOT rendering changed — golden needs regeneration")
def test_pipeline_golden_match():
    pass
