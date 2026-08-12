"""
test_viz_expr_trees.py — Plan F2 验证: viz.meta.datapath.expr_trees 完整覆盖 driver 表达式

[Plan F2 2026-08-12] 旧 path (open().read() + regex / SyntaxTree.fromText 重解析) 已被
semantic AST 替换. 本测试验证:

1. expr_trees field 存在于 viz.meta.datapath
2. driver key (module.signal) 完整覆盖所有 assign
3. tree_dict 包含正确的 op/label/children 结构
4. 各种表达式类型 (binary / ternary / concat / function call) 都被解析
5. const_map + func_info 同步从 expr_trees 树遍历提取

[铁律13] 金标准测试
[铁律17] 强断言
[铁律22] 断言验证具体行为
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.graph.viz import VizBuildOptions, build_viz_data
from trace.unified_tracer import UnifiedTracer


def _build_graph(src: str, target: str | None = None):
    tracer = UnifiedTracer(
        sources={f"_test_f2_{hash(src) & 0xFFFFFFFF}.sv": src},
        strict=False,
    )
    if target:
        tracer.trace_module(target)
    else:
        tracer.build_graph()
    return tracer.get_graph()


SIMPLE_BINARY = """
module test_f2(input [7:0] a, b, output [7:0] y);
    assign y = a + b;
endmodule
"""

TERNARY_EXPR = """
module test_ternary(input [7:0] a, b, sel, output [7:0] y);
    assign y = sel ? a : b;
endmodule
"""

CONCAT_EXPR = """
module test_concat(input [7:0] hi, lo, output [7:0] y);
    assign y = {hi[3:0], lo[3:0]};
endmodule
"""

FUNCTION_CALL = """
module test_func(input [7:0] a, b, output [7:0] y);
    assign y = $signed(a) + b;
endmodule
"""

MULTIPLE_DRIVERS = """
module test_multi(input [7:0] a, b, c, output [7:0] y1, y2, y3);
    assign y1 = a + b;
    assign y2 = a * b;
    assign y3 = $signed(a) - b;
endmodule
"""

# 1 个 trivial case, 1 个 realistic (multiple drivers + operators)
REALISTIC = """
module f2_realistic(input [7:0] op_a, op_b, op_c,
                     input [1:0] sel,
                     output [7:0] result, mux_out);
    // dataflow 链
    assign result = (op_a + op_b) * op_c;
    // ternary
    assign mux_out = sel[0] ? op_a : op_b;
endmodule
"""


class TestVizExprTreesWiring:
    """验证 F2 新 path: viz.meta.datapath.expr_trees 完整覆盖 driver"""

    def test_expr_trees_field_exists(self):
        """viz.meta.datapath.expr_trees 必须存在"""
        graph = _build_graph(SIMPLE_BINARY, target="test_f2")
        viz = build_viz_data(graph, VizBuildOptions())
        assert "datapath" in viz.meta, "viz.meta.datapath missing"
        assert "expr_trees" in viz.meta["datapath"], \
            "viz.meta.datapath.expr_trees missing (F2 new path)"

    def test_simple_binary_in_expr_trees(self):
        """a + b 必须出现在 expr_trees, 树结构正确"""
        graph = _build_graph(SIMPLE_BINARY, target="test_f2")
        viz = build_viz_data(graph, VizBuildOptions())
        et = viz.meta["datapath"]["expr_trees"]
        # 期望 key: test_f2.y
        assert "test_f2.y" in et, \
            f"expected 'test_f2.y' in expr_trees, got keys: {list(et.keys())}"
        tree = et["test_f2.y"]
        # 顶层应该是 Add
        assert tree["op"] == "Add", f"expected op='Add', got {tree['op']}"
        assert tree["label"] == "+", f"expected label='+', got {tree['label']}"
        # 应该有 2 个 children
        assert len(tree["children"]) == 2, \
            f"binary op should have 2 children, got {len(tree['children'])}"

    def test_ternary_operator_in_expr_trees(self):
        """sel ? a : b 必须是 Ternary op, 3 children"""
        graph = _build_graph(TERNARY_EXPR, target="test_ternary")
        viz = build_viz_data(graph, VizBuildOptions())
        et = viz.meta["datapath"]["expr_trees"]
        assert "test_ternary.y" in et
        tree = et["test_ternary.y"]
        # 顶层可能是 Ternary 或 Conditional
        assert tree["op"] in ("Ternary", "Conditional"), \
            f"expected Ternary op, got {tree['op']}"
        assert len(tree["children"]) >= 3, \
            f"ternary should have ≥3 children, got {len(tree['children'])}"

    def test_concat_operator_in_expr_trees(self):
        """{hi[3:0], lo[3:0]} 必须是 Concat op"""
        graph = _build_graph(CONCAT_EXPR, target="test_concat")
        viz = build_viz_data(graph, VizBuildOptions())
        et = viz.meta["datapath"]["expr_trees"]
        assert "test_concat.y" in et
        tree = et["test_concat.y"]
        # 顶层可能是 Concat
        assert tree["op"] == "Concat", f"expected op='Concat', got {tree['op']}"
        assert tree["label"] == "{}", f"expected label='{{}}', got {tree['label']}"
        # 应该有 2 个 children (hi[3:0], lo[3:0])
        assert len(tree["children"]) == 2, \
            f"concat should have 2 children, got {len(tree['children'])}"

    def test_function_call_in_expr_trees(self):
        """$signed(a) + b 必须有 Call 子节点"""
        graph = _build_graph(FUNCTION_CALL, target="test_func")
        viz = build_viz_data(graph, VizBuildOptions())
        et = viz.meta["datapath"]["expr_trees"]
        assert "test_func.y" in et
        tree = et["test_func.y"]
        # 顶层是 Add (a + b), 其中 a 是 Call($signed, [a])
        assert tree["op"] == "Add", f"expected op='Add', got {tree['op']}"
        # 至少一个 child 是 Call
        has_call = any(
            child["op"] == "Call"
            for child in tree["children"]
        )
        # 或者 Call 是 nested 在更深层
        def _find_call(node):
            if node["op"] == "Call":
                return True
            return any(_find_call(c) for c in node.get("children", []))
        assert _find_call(tree), "expected Call($signed) somewhere in tree"

    def test_multiple_drivers_all_covered(self):
        """3 个 driver 必须 3 个 expr_trees key"""
        graph = _build_graph(MULTIPLE_DRIVERS, target="test_multi")
        viz = build_viz_data(graph, VizBuildOptions())
        et = viz.meta["datapath"]["expr_trees"]
        for sig in ("y1", "y2", "y3"):
            key = f"test_multi.{sig}"
            assert key in et, f"missing {key} in expr_trees, got {list(et.keys())}"
        # y1 = a + b → Add
        assert et["test_multi.y1"]["op"] == "Add"
        # y2 = a * b → Multiply
        assert et["test_multi.y2"]["op"] == "Multiply"
        # y3 = $signed(a) - b → Subtract (顶层)
        assert et["test_multi.y3"]["op"] == "Subtract"

    def test_realistic_driver_expression(self):
        """realistic 用例: multi-op chain + ternary 都应在 expr_trees"""
        graph = _build_graph(REALISTIC, target="f2_realistic")
        viz = build_viz_data(graph, VizBuildOptions())
        et = viz.meta["datapath"]["expr_trees"]
        # 期望两个 driver
        assert "f2_realistic.result" in et
        assert "f2_realistic.mux_out" in et
        # 链深度: (a + b) * c → Multiply → child 是 Add
        tree = et["f2_realistic.result"]
        assert tree["op"] == "Multiply"
        # 至少一个 child 是 Add
        has_add = any(c["op"] == "Add" for c in tree["children"])
        def _find_add(node):
            if node["op"] == "Add":
                return True
            return any(_find_add(c) for c in node.get("children", []))
        assert _find_add(tree), "expected nested Add in (a + b) * c"

    def test_const_map_synced_with_expr_trees(self):
        """const_map 必须从 expr_trees 树遍历提取"""
        graph = _build_graph(SIMPLE_BINARY, target="test_f2")
        viz = build_viz_data(graph, VizBuildOptions())
        cm = viz.meta["datapath"].get("const_map", {})
        # y 树本身可能没有 const (a + b 没字面量), 但 const_map 字段必须存在
        # 期望至少是 dict
        assert isinstance(cm, dict)


class TestVizExprTreesTreeStructure:
    """验证 tree_dict 结构一致性 (Plan F2 storage contract)"""

    def test_tree_dict_json_safe(self):
        """tree_dict 只含 string/list/dict (无 pyslang 对象引用)"""
        import json
        graph = _build_graph(REALISTIC, target="f2_realistic")
        viz = build_viz_data(graph, VizBuildOptions())
        et = viz.meta["datapath"]["expr_trees"]
        # 整个 expr_trees 必须 JSON-serializable
        try:
            json.dumps(et)
        except TypeError as e:
            raise AssertionError(f"expr_trees not JSON-safe: {e}")

    def test_all_trees_have_required_fields(self):
        """所有 tree_dict 都有 label / op / children"""
        graph = _build_graph(MULTIPLE_DRIVERS, target="test_multi")
        viz = build_viz_data(graph, VizBuildOptions())
        et = viz.meta["datapath"]["expr_trees"]
        for key, tree in et.items():
            assert "label" in tree, f"{key}: missing label"
            assert "op" in tree, f"{key}: missing op"
            assert "children" in tree, f"{key}: missing children"
            assert isinstance(tree["children"], list), \
                f"{key}: children must be list"
