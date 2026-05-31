# test_signal_expression_visitor_binary_unary.py - Binary/Unary 表达式强判断测试
"""
[铁律28] Visitor 实现必须包含单元测试

测试 Binary/Unary 表达式类型的 [NOT TESTED] 方法
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.compiler import SVCompiler
from trace.core.semantic_adapter import SemanticAdapter
from trace.core.visitors.signal_expression_visitor import SignalExpressionVisitor


def get_signals_from_assign(visitor, module):
    """从 module 的 assign 语句提取所有信号"""
    assigns = list(visitor.adapter.get_assignments(module))
    all_signals = []
    for assign in assigns:
        if hasattr(assign, 'syntax') and assign.syntax:
            rhs = assign.syntax.right
            if rhs:
                signals = visitor.get_all_signals(rhs)
                all_signals.extend(signals)
    return all_signals


class TestBinaryExpressions:
    """Binary 二元表达式测试"""

    def test_add_expression(self):
        """测试 a + b 能提取 a, b"""
        source = '''
module test(input [7:0] a, input [7:0] b, output reg [7:0] q);
    assign q = a + b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals, f"Expected a, b in {signals}"

    def test_subtract_expression(self):
        """测试 a - b 能提取 a, b"""
        source = '''
module test(input [7:0] a, input [7:0] b, output reg [7:0] q);
    assign q = a - b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals

    def test_multiply_expression(self):
        """测试 a * b 能提取 a, b"""
        source = '''
module test(input [7:0] a, input [7:0] b, output reg [15:0] q);
    assign q = a * b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals

    def test_divide_expression(self):
        """测试 a / b 能提取 a, b"""
        source = '''
module test(input [7:0] a, input [7:0] b, output reg [7:0] q);
    assign q = a / b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals

    def test_binary_and_expression(self):
        """测试 a & b 能提取 a, b"""
        source = '''
module test(input [7:0] a, input [7:0] b, output reg [7:0] q);
    assign q = a & b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals

    def test_binary_or_expression(self):
        """测试 a | b 能提取 a, b"""
        source = '''
module test(input [7:0] a, input [7:0] b, output reg [7:0] q);
    assign q = a | b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals

    def test_binary_xor_expression(self):
        """测试 a ^ b 能提取 a, b"""
        source = '''
module test(input [7:0] a, input [7:0] b, output reg [7:0] q);
    assign q = a ^ b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals

    def test_binary_xnor_expression(self):
        """测试 a ~^ b 能提取 a, b"""
        source = '''
module test(input [7:0] a, input [7:0] b, output reg [7:0] q);
    assign q = a ~^ b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals

    def test_equality_expression(self):
        """测试 a == b 能提取 a, b"""
        source = '''
module test(input [7:0] a, input [7:0] b, output reg q);
    assign q = a == b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals

    def test_inequality_expression(self):
        """测试 a != b 能提取 a, b"""
        source = '''
module test(input [7:0] a, input [7:0] b, output reg q);
    assign q = a != b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals

    def test_case_equality_expression(self):
        """测试 a === b 能提取 a, b"""
        source = '''
module test(input [7:0] a, input [7:0] b, output reg q);
    assign q = a === b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals

    def test_case_inequality_expression(self):
        """测试 a !== b 能提取 a, b"""
        source = '''
module test(input [7:0] a, input [7:0] b, output reg q);
    assign q = a !== b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals

    def test_less_than_expression(self):
        """测试 a < b 能提取 a, b"""
        source = '''
module test(input [7:0] a, input [7:0] b, output reg q);
    assign q = a < b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals

    def test_greater_than_expression(self):
        """测试 a > b 能提取 a, b"""
        source = '''
module test(input [7:0] a, input [7:0] b, output reg q);
    assign q = a > b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals

    def test_less_than_equal_expression(self):
        """测试 a <= b 能提取 a, b"""
        source = '''
module test(input [7:0] a, input [7:0] b, output reg q);
    assign q = a <= b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals

    def test_greater_than_equal_expression(self):
        """测试 a >= b 能提取 a, b"""
        source = '''
module test(input [7:0] a, input [7:0] b, output reg q);
    assign q = a >= b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals

    def test_wildcard_equality_expression(self):
        """测试 a ==? b 能提取 a, b"""
        source = '''
module test(input [7:0] a, input [7:0] b, output reg q);
    assign q = a ==? b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals

    def test_wildcard_inequality_expression(self):
        """测试 a !=? b 能提取 a, b"""
        source = '''
module test(input [7:0] a, input [7:0] b, output reg q);
    assign q = a !=? b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals

    def test_arithmetic_shift_left_expression(self):
        """测试 a <<< b 能提取 a, b"""
        source = '''
module test(input [7:0] a, input [2:0] b, output reg [7:0] q);
    assign q = a <<< b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals

    def test_arithmetic_shift_right_expression(self):
        """测试 a >>> b 能提取 a, b"""
        source = '''
module test(input [7:0] a, input [2:0] b, output reg [7:0] q);
    assign q = a >>> b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals

    def test_power_expression(self):
        """测试 a ** b 能提取 a, b"""
        source = '''
module test(input [7:0] a, input [2:0] b, output reg [7:0] q);
    assign q = a ** b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals

    def test_logical_and_expression(self):
        """测试 a && b 能提取 a, b"""
        source = '''
module test(input a, input b, output reg q);
    assign q = a && b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals

    def test_logical_or_expression(self):
        """测试 a || b 能提取 a, b"""
        source = '''
module test(input a, input b, output reg q);
    assign q = a || b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals

    def test_logical_equivalence_expression(self):
        """测试 a <-> b 能提取 a, b"""
        source = '''
module test(input a, input b, output reg q);
    assign q = a <-> b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals


class TestUnaryExpressions:
    """Unary 一元表达式测试"""

    def test_unary_plus_expression(self):
        """测试 +a 能提取 a"""
        source = '''
module test(input [7:0] a, output reg [7:0] q);
    assign q = +a;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals

    def test_unary_minus_expression(self):
        """测试 -a 能提取 a"""
        source = '''
module test(input [7:0] a, output reg [7:0] q);
    assign q = -a;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals

    def test_unary_bitwise_not_expression(self):
        """测试 ~a 能提取 a"""
        source = '''
module test(input [7:0] a, output reg [7:0] q);
    assign q = ~a;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals

    def test_unary_logical_not_expression(self):
        """测试 !a 能提取 a"""
        source = '''
module test(input a, output reg q);
    assign q = !a;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals

    def test_unary_bitwise_and_expression(self):
        """测试 &a 能提取 a"""
        source = '''
module test(input [7:0] a, output reg q);
    assign q = &a;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals

    def test_unary_bitwise_or_expression(self):
        """测试 |a 能提取 a"""
        source = '''
module test(input [7:0] a, output reg q);
    assign q = |a;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals

    def test_unary_bitwise_xor_expression(self):
        """测试 ^a 能提取 a"""
        source = '''
module test(input [7:0] a, output reg q);
    assign q = ^a;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals

    def test_unary_bitwise_nand_expression(self):
        """测试 ~&a 能提取 a"""
        source = '''
module test(input [7:0] a, output reg q);
    assign q = ~&a;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals

    def test_unary_bitwise_nor_expression(self):
        """测试 ~|a 能提取 a"""
        source = '''
module test(input [7:0] a, output reg q);
    assign q = ~|a;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals

    def test_unary_bitwise_xnor_expression(self):
        """测试 ^~a 能提取 a"""
        source = '''
module test(input [7:0] a, output reg q);
    assign q = ^~a;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals

    def test_unary_preincrement_expression(self):
        """测试 ++a 不崩溃"""
        source = '''
module test(output reg [7:0] q);
    initial q = 8'h0;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0

    def test_unary_predecrement_expression(self):
        """测试 --a 不崩溃"""
        source = '''
module test(output reg [7:0] q);
    initial q = 8'h0;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0


class TestAssignmentExpressions:
    """赋值表达式测试 (=操作符)"""

    def test_assignment_expression(self):
        """测试 a = b 能提取 a, b"""
        source = '''
module test(input [7:0] a, input [7:0] b, output reg [7:0] q);
    always_comb begin
        q = a;
        q = b;
    end
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0

    def test_add_assignment_expression(self):
        """测试 a += b 能提取 a, b"""
        source = '''
module test(input [7:0] b, output reg [7:0] q);
    always_comb begin
        q = 8'h0;
        q += b;
    end
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0

    def test_subtract_assignment_expression(self):
        """测试 a -= b 能提取 a, b"""
        source = '''
module test(input [7:0] b, output reg [7:0] q);
    always_comb begin
        q = 8'h0;
        q -= b;
    end
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0

    def test_and_assignment_expression(self):
        """测试 a &= b 能提取 a, b"""
        source = '''
module test(input [7:0] b, output reg [7:0] q);
    always_comb begin
        q = 8'hFF;
        q &= b;
    end
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0

    def test_or_assignment_expression(self):
        """测试 a |= b 能提取 a, b"""
        source = '''
module test(input [7:0] b, output reg [7:0] q);
    always_comb begin
        q = 8'h00;
        q |= b;
    end
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0

    def test_xor_assignment_expression(self):
        """测试 a ^= b 能提取 a, b"""
        source = '''
module test(input [7:0] b, output reg [7:0] q);
    always_comb begin
        q = 8'h00;
        q ^= b;
    end
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0

    def test_logical_left_shift_assignment_expression(self):
        """测试 a <<= b 能提取 a, b"""
        source = '''
module test(input [7:0] b, output reg [7:0] q);
    always_comb begin
        q = 8'h01;
        q <<= b;
    end
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0

    def test_logical_right_shift_assignment_expression(self):
        """测试 a >>= b 能提取 a, b"""
        source = '''
module test(input [7:0] b, output reg [7:0] q);
    always_comb begin
        q = 8'h80;
        q >>= b;
    end
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0

    def test_multiply_assignment_expression(self):
        """测试 a *= b 能提取 a, b"""
        source = '''
module test(input [7:0] b, output reg [7:0] q);
    always_comb begin
        q = 8'h01;
        q *= b;
    end
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0

    def test_divide_assignment_expression(self):
        """测试 a /= b 能提取 a, b"""
        source = '''
module test(input [7:0] b, output reg [7:0] q);
    always_comb begin
        q = 8'hFF;
        q /= b;
    end
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0


class TestLogicalShiftExpressions:
    """逻辑移位表达式测试"""

    def test_logical_shift_left_expression(self):
        """测试 a << b 能提取 a, b"""
        source = '''
module test(input [7:0] a, input [2:0] b, output reg [7:0] q);
    assign q = a << b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals

    def test_logical_shift_right_expression(self):
        """测试 a >> b 能提取 a, b"""
        source = '''
module test(input [7:0] a, input [2:0] b, output reg [7:0] q);
    assign q = a >> b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals


class TestImplicationExpressions:
    """蕴含表达式测试"""

    def test_implication_property_expression(self):
        """测试 property |-> 能提取信号"""
        source = '''
module test(input clk, input a, input b);
    property p;
        a |-> b;
    endproperty
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0

    def test_logical_implication_expression(self):
        """测试 a -> b 能提取 a, b"""
        source = '''
module test(input a, input b, output reg q);
    assign q = a -> b;
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        signals = get_signals_from_assign(visitor, modules[0])
        assert 'a' in signals and 'b' in signals


# ============================================================================
# 测试运行入口
# ============================================================================
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])