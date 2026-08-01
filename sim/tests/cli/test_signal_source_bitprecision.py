"""test_signal_source_bitprecision.py — [V6.5] 验证 SignalSource 结构化驱动源

测试目标:
1. SignalSource dataclass 正确创建 (signal/bit_start/bit_end/op/operand_side/casts)
2. 分解后的 binary operator 边缘携带正确的 SignalSource
3. bit range 解析正确 (int 而非字符串)
4. $signed/$unsigned cast 检测
5. 向后兼容: expression/bit_slice 字符串字段仍然可用
"""



# --- Helper ---


def _build_graph(src: str, target: str | None = None):
    """编译 SV 源码并提取 graph, 返回 SignalGraph"""
    from trace.unified_tracer import UnifiedTracer

    fname = f"_test_ds_{hash(src) & 0xFFFFFFFF}.sv"
    tracer = UnifiedTracer(sources={fname: src}, strict=False)
    if target:
        tracer.trace_module(target)
    else:
        # trace all
        tracer.build_graph()
    return tracer.get_graph()


def _get_driver_edges(graph, dst_signal: str) -> list:
    """获取目标信号的所有 DRIVER 边"""
    edges = []
    for src, dst in graph.edges():
        for e in graph.get_edges(src, dst):
            if e.kind.name == "DRIVER" and dst.endswith(f".{dst_signal}"):
                edges.append(e)
    return edges


# --- Fixtures ---

SIMPLE_BINARY = """
module test_binary(input [7:0] a, b, output [7:0] y);
    assign y = a + b;
endmodule
"""

BITRANGE_BINARY = """
module test_binary_br(input [15:0] a, b, output [7:0] y);
    assign y = a[7:0] + b[3:0];
endmodule
"""

SIGNED_BINARY = """
module test_signed(input signed [7:0] a, b, output [7:0] y);
    assign y = $signed(a) >>> b;
endmodule
"""

MIXED_OPS = """
module test_mixed(input [7:0] a, b, c, output [7:0] y);
    assign y = (a & b) | c;
endmodule
"""



class TestSignalSourceBasic:
    """SignalSource 基本功能: 创建和属性"""

    def test_source_creation(self):
        """SignalSource dataclass 正确创建"""
        from trace.core.graph.models import SignalSource

        ds = SignalSource(
            signal="a",
            bit_start=7,
            bit_end=0,
            full_expression="a[7:0] + b[3:0]",
            op="+",
            operand_side="left",
            is_decomposed=True,
        )
        assert ds.signal == "a"
        assert ds.bit_start == 7
        assert ds.bit_end == 0
        assert ds.op == "+"
        assert ds.operand_side == "left"
        assert ds.bit_slice == "[7:0]"  # property
        assert ds.is_decomposed is True

    def test_source_single_bit(self):
        """SignalSource 单 bit 选择"""
        from trace.core.graph.models import SignalSource

        ds = SignalSource(signal="data", bit_start=3, bit_end=3)
        assert ds.bit_slice == "[3]"

    def test_source_no_bit(self):
        """SignalSource 无 bit 选择时 bit_slice 为空"""
        from trace.core.graph.models import SignalSource

        ds = SignalSource(signal="data")
        assert ds.bit_slice == ""


class TestSignalSourceOnEdges:
    """验证分解后的边携带 SignalSource"""

    def test_binary_op_source(self):
        """a + b 分解后每条边有 SignalSource.op='+' 和 operand_side"""
        graph = _build_graph(SIMPLE_BINARY, target="test_binary")
        edges = _get_driver_edges(graph, "y")

        # 应该有 2 条 DRIVER 边: a->y, b->y
        assert len(edges) >= 2, f"Expected >=2 edges, got {len(edges)}"

        for e in edges:
            assert e.source is not None, f"Edge {e.src}->{e.dst} missing source"
            ds = e.source
            assert ds.op == "Add", f"Expected op='Add', got '{ds.op}'"
            assert ds.operand_side in ("left", "right"), f"operand_side must be left/right, got '{ds.operand_side}'"
            assert ds.is_decomposed is True
            # full_expression 来自 str(rhs_expr), pyslang AST repr
            assert "a" in ds.full_expression and "b" in ds.full_expression
            assert "+" in ds.full_expression

        # 验证左右操作数
        sides = {e.source.operand_side for e in edges}
        assert sides == {"left", "right"}, f"Expected both left and right, got {sides}"

    def test_source_parse_bitrange(self):
        """a[7:0] + b[3:0] 正确解析 bit_start/bit_end 为 int"""
        graph = _build_graph(BITRANGE_BINARY, target="test_binary_br")
        edges = _get_driver_edges(graph, "y")

        assert len(edges) >= 2

        for e in edges:
            assert e.source is not None
            ds = e.source
            assert ds.op == "Add"
            assert ds.is_decomposed is True
            # Verify bit range is int, not string
            if ds.operand_side == "left":
                assert ds.bit_start == 7, f"a left bit_start: expected 7, got {ds.bit_start}"
                assert ds.bit_end == 0, f"a left bit_end: expected 0, got {ds.bit_end}"
            elif ds.operand_side == "right":
                assert ds.bit_start == 3, f"b right bit_start: expected 3, got {ds.bit_start}"
                assert ds.bit_end == 0, f"b right bit_end: expected 0, got {ds.bit_end}"

    def test_signed_cast_detection(self):
        """$signed(a) >>> b 检测 casts=['$signed']"""
        graph = _build_graph(SIGNED_BINARY, target="test_signed")
        edges = _get_driver_edges(graph, "y")

        assert len(edges) >= 2

        # 左侧操作数 a 应检测到 $signed cast
        left_edge = next((e for e in edges if e.source.operand_side == "left"), None)
        assert left_edge is not None
        ds = left_edge.source
        assert "$signed" in ds.casts, f"Expected $signed in casts, got {ds.casts}"
        assert ds.op == "LogicalShift" or "Shift" in ds.op, f"Expected shift op, got '{ds.op}'"

    def test_mixed_ops_have_op(self):
        """(a & b) | c 每条边有正确的 op"""
        graph = _build_graph(MIXED_OPS, target="test_mixed")
        edges = _get_driver_edges(graph, "y")

        assert len(edges) >= 3  # a, b, c

        # 每个边缘都应携带 op
        for e in edges:
            assert e.source is not None
            assert e.source.op, f"Missing op on {e.src} edge"


class TestSignalSourceBackwardCompat:
    """向后兼容: expression/bit_slice 字符串字段仍然正确"""

    def test_expression_still_available(self):
        """expression 字符串字段仍然正确填充"""
        graph = _build_graph(SIMPLE_BINARY, target="test_binary")
        edges = _get_driver_edges(graph, "y")

        for e in edges:
            assert e.source is not None
            # expression 字段向后兼容, 可能为 leaf name (visit 输出) 或完整形式
            # 关键是它非空
            assert e.expression, f"expression is empty on edge {e.src}->{e.dst}"

    def test_bit_slice_still_available(self):
        """bit_slice 字符串字段仍然正确填充"""
        graph = _build_graph(BITRANGE_BINARY, target="test_binary_br")
        edges = _get_driver_edges(graph, "y")

        for e in edges:
            assert e.source is not None
            # bit_slice should match source.bit_slice
            assert e.bit_slice == e.source.bit_slice


class TestSignalSourceNotOnSimple:
    """简单赋值 (无分解) 不产生 source"""

    def test_simple_assign_no_source(self):
        """简单连续赋值 assign y = a 不产生 SignalSource (无需分解)"""
        src = """
module test_simple(input [7:0] a, output [7:0] y);
    assign y = a;
endmodule
"""
        graph = _build_graph(src, target="test_simple")
        edges = _get_driver_edges(graph, "y")

        assert len(edges) == 1
        # 简单赋值不产生 SignalSource (没有分解动作)
        # _build_source 只对分解路径添加, 简单路径不产生
        if edges[0].source is not None:
            # 如果有, 那应该是 is_decomposed=False
            assert edges[0].source.is_decomposed is False


class TestParseBitRange:
    """DriverExtractor._parse_bit_range 静态方法验证"""

    def test_parse_bit_range(self):
        """检查静态方法是否正确解析 bit range"""
        from trace.core.driver_extractor import DriverExtractor

        # 范围选择
        sig, hi, lo = DriverExtractor._parse_bit_range("a[7:0]")
        assert sig == "a"
        assert hi == 7
        assert lo == 0

        # 单 bit
        sig, hi, lo = DriverExtractor._parse_bit_range("data[3]")
        assert sig == "data"
        assert hi == 3
        assert lo == 3

        # 无位选择
        sig, hi, lo = DriverExtractor._parse_bit_range("my_signal")
        assert sig == "my_signal"
        assert hi is None
        assert lo is None

        # 空值
        sig, hi, lo = DriverExtractor._parse_bit_range("")
        assert sig is None
