"""test_viz_data.py — V6.7 VizData 统一可视化数据格式测试"""


from trace.core.graph.viz import (
    VizBuildOptions,
    build_viz_data,
)
from trace.core.graph.viz.elk_bridge import viz_to_elk
from trace.unified_tracer import UnifiedTracer

# ── helpers ──

def _build_graph(src: str, target: str | None = None):
    """编译 SV 源码并提取 SignalGraph"""
    tracer = UnifiedTracer(
        sources={f"_test_viz_{hash(src) & 0xFFFFFFFF}.sv": src},
        
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


class TestVizDataToElk:
    """VizData → ELK 布局输入

    [iter_245] 原 `TestVizDataRender` 测的是 `_archived_dot/viz_dot_renderer.render_dot`。
    该渲染器已随 A1 归档出 `src/`（V6.7 起唯一渲染路径是 VizData → ELK → SVG），
    所以改为锁定**活路径**的结构不变式，而不是删掉覆盖。
    """

    def test_viz_to_elk_structure(self):
        """ELK 输入必须是 compound graph: id + children + edges"""
        viz = build_viz_data(_build_graph(SIMPLE_BINARY, target="test"))
        elk = viz_to_elk(viz)
        assert isinstance(elk, dict)
        assert {"id", "children", "edges"} <= set(elk), f"缺字段: {sorted(elk)}"
        assert len(elk["children"]) >= 3
        for child in elk["children"]:
            assert "id" in child, f"child 缺 id: {child}"
            assert "labels" in child, f"child 缺 labels: {child}"

    def test_viz_to_elk_ids_are_dot_safe(self):
        """ELK 节点 id 不得包含 '.' —— 它会进 SVG/DOM id 与选择器"""
        viz = build_viz_data(_build_graph(SIMPLE_BINARY, target="test"))
        elk = viz_to_elk(viz)
        for child in elk["children"]:
            assert "." not in child["id"], f"id 含 '.': {child['id']}"

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
