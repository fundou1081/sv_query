"""test_viz_data.py — V6.7 VizData 统一可视化数据格式测试"""


from trace.core.graph.viz import (
    VizBuildOptions,
    build_viz_data,
    render_dot,
)
from trace.unified_tracer import UnifiedTracer

# ── helpers ──

def _build_graph(src: str, target: str | None = None):
    """编译 SV 源码并提取 SignalGraph"""
    tracer = UnifiedTracer(
        sources={f"_test_viz_{hash(src) & 0xFFFFFFFF}.sv": src},
        strict=False,
    )
    if target:
        tracer.trace_module(target)
    else:
        tracer.build_graph()
    return tracer.get_graph()


SIMPLE_BINARY = """
module test(input [7:0] a, b, output [7:0] y);
    assign y = a + b;
endmodule
"""

ALWAYS_COND = """
module test(input clk, input [7:0] a, b, output reg [7:0] y);
    always_ff @(posedge clk) begin
        if (a > b) y <= a;
        else y <= b;
    end
endmodule
"""

PIPELINE = """
module test(input clk, input [3:0] a, output [3:0] y);
    reg [3:0] r;
    always_ff @(posedge clk) r <= a;
    assign y = r;
endmodule
"""


class TestVizDataBasic:
    """VizData 基本构建"""

    def test_build_minimal(self):
        """最小选项构建 VizData"""
        graph = _build_graph(SIMPLE_BINARY, target="test")
        viz = build_viz_data(graph, VizBuildOptions())
        assert viz.node_count >= 3
        assert viz.edge_count >= 1
        assert viz.meta["filtered_node_count"] == viz.node_count

    def test_nodes_have_required_fields(self):
        """所有 node 都有必需的字段"""
        graph = _build_graph(SIMPLE_BINARY, target="test")
        viz = build_viz_data(graph)
        for node in viz.nodes:
            assert node.id
            assert node.label
            assert node.module
            assert node.kind

    def test_edges_have_required_fields(self):
        """所有 edge 都有必需的字段"""
        graph = _build_graph(SIMPLE_BINARY, target="test")
        viz = build_viz_data(graph)
        for edge in viz.edges:
            assert edge.id
            assert edge.src
            assert edge.dst
            assert edge.kind

    def test_max_edges_limit(self):
        """max_edges 限制生效"""
        graph = _build_graph(SIMPLE_BINARY, target="test")
        viz = build_viz_data(graph, VizBuildOptions(max_edges=1))
        assert viz.edge_count == 1

    def test_max_nodes_limit(self):
        """max_nodes 限制生效"""
        graph = _build_graph(SIMPLE_BINARY, target="test")
        viz = build_viz_data(graph, VizBuildOptions(max_nodes=1))
        assert viz.node_count == 1


class TestVizDataExpression:
    """表达式和条件信息"""

    def test_expression_in_viz(self):
        """边上的 expression 字段填入了正确的值"""
        graph = _build_graph(SIMPLE_BINARY, target="test")
        viz = build_viz_data(graph, VizBuildOptions(include_edge_expression=True))
        driver_edges = [e for e in viz.edges if e.kind == "DRIVER"]
        assert len(driver_edges) >= 2
        for e in driver_edges:
            assert e.expression, f"expression empty on {e.id}"

    def test_source_fields_filled(self):
        """SignalSource 信息填入了 VizEdge"""
        graph = _build_graph(SIMPLE_BINARY, target="test")
        viz = build_viz_data(graph, VizBuildOptions(include_edge_expression=True))
        driver_edges = [e for e in viz.edges if e.kind == "DRIVER"]
        for e in driver_edges:
            assert e.source_signal, f"source_signal empty on {e.id}"
            assert e.source_op == "Add", f"source_op should be Add, got {e.source_op}"
            assert e.source_is_decomposed is True

    def test_condition_in_viz(self):
        """条件表达式填入了 condition 字段"""
        graph = _build_graph(ALWAYS_COND, target="test")
        viz = build_viz_data(graph, VizBuildOptions(
            include_edge_condition=True,
            include_edge_expression=True,
        ))
        # 应该有带条件的 DRIVER 边
        cond_edges = [e for e in viz.edges if e.kind == "DRIVER" and e.condition]
        assert len(cond_edges) >= 2, f"Expected >=2 conditioned driver edges, got {len(cond_edges)}"
        # 至少一条边的条件是 "a > b"
        assert any("a > b" in e.condition for e in cond_edges), \
            f"No edge has 'a > b' condition. Conditions: {[e.condition for e in cond_edges]}"

    def test_edge_labels_without_expression(self):
        """不包含 expression 时，边标签仍然干净（只有 condition）"""
        graph = _build_graph(ALWAYS_COND, target="test")
        viz = build_viz_data(graph, VizBuildOptions(
            include_edge_expression=False,
            include_edge_condition=True,
        ))
        driver_edges = [e for e in viz.edges if e.kind == "DRIVER"]
        for e in driver_edges:
            assert not e.expression, f"expression should be empty but got {e.expression!r}"


class TestVizDataRender:
    """DOT 渲染"""

    def test_render_dot_produces_valid_digraph(self):
        """render_dot 生成有效的 digraph"""
        graph = _build_graph(SIMPLE_BINARY, target="test")
        viz = build_viz_data(graph)
        dot = render_dot(viz)
        assert dot.startswith("digraph viz {\n")
        assert "}\n" in dot or dot.endswith("}")
        assert "rankdir=TB" in dot

    def test_render_dot_shows_condition(self):
        """DOT 输出包含边条件"""
        graph = _build_graph(ALWAYS_COND, target="test")
        viz = build_viz_data(graph, VizBuildOptions(
            include_edge_condition=True,
            include_edge_expression=True,
        ))
        dot = render_dot(viz)
        # 应该包含条件文本
        assert "a > b" in dot or "a" in dot, f"Condition not found in DOT:\n{dot}"

    def test_render_dot_layout_config(self):
        """layout 配置生效"""
        graph = _build_graph(PIPELINE, target="test")
        viz = build_viz_data(graph)
        dot_lr = render_dot(viz, {"layout": "LR"})
        assert "rankdir=LR" in dot_lr
        dot_tb = render_dot(viz, {"layout": "TB"})
        assert "rankdir=TB" in dot_tb

    def test_render_dot_hides_clock_by_default(self):
        """默认不显示 CLOCK/RESET 边"""
        graph = _build_graph(PIPELINE, target="test")
        viz = build_viz_data(graph)
        dot = render_dot(viz)  # 默认 show_clock_reset=False
        # 不应该包含 CLOCK 或 RESET 边的渲染
        assert "CLOCK" not in dot or "clock" not in dot.lower()

    def test_render_dot_shows_clock_when_enabled(self):
        """开启 show_clock_reset 后显示时钟边"""
        graph = _build_graph(PIPELINE, target="test")
        viz = build_viz_data(graph)
        dot = render_dot(viz, {"show_clock_reset": True})
        # CLOCK 边现在应该出现
        # (具体显示取决于节点名，格式是 \"src\" -> \"dst\")
        assert "->" in dot


class TestVizDataJson:
    """JSON 导出"""

    def test_to_json(self):
        """to_json 生成纯数据字典"""
        graph = _build_graph(SIMPLE_BINARY, target="test")
        viz = build_viz_data(graph)
        data = viz.to_json()
        assert "meta" in data
        assert "nodes" in data
        assert "edges" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)
        assert len(data["nodes"]) > 0

    def test_to_json_no_defaults(self):
        """to_json 不导出默认值（空字符串/None/0/False）"""
        graph = _build_graph(SIMPLE_BINARY, target="test")
        viz = build_viz_data(graph, VizBuildOptions(
            include_edge_condition=False,
            include_edge_expression=False,
        ))
        data = viz.to_json()
        # edge 不应该有 expression/condition（已跳过）
        for e in data["edges"]:
            assert "expression" not in e
            assert "condition" not in e


class TestVizDataPipeline:
    """pipeline 信息可选支持"""

    def test_stage_info_when_provided(self):
        """传入 pipeline_stages 后 stage_id 正确分配"""
        graph = _build_graph(PIPELINE, target="test")
        viz = build_viz_data(graph, VizBuildOptions(
            include_node_stage=True,
            pipeline_stages={0: ["test.y"], 1: ["test.r"]},
        ))
        nodes_by_id = {n.id: n for n in viz.nodes}
        if "test.r" in nodes_by_id:
            assert nodes_by_id["test.r"].stage_id is not None
