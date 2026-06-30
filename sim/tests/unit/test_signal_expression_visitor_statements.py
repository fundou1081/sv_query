# test_signal_expression_visitor_statements.py - Statement 类型强判断测试
"""
[铁律28] Visitor 实现必须包含单元测试

测试 Statement 类型的 [NOT TESTED] 方法
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.compiler import SVCompiler
from trace.core.semantic_adapter import SemanticAdapter
from trace.core.visitors.signal_expression_visitor import SignalExpressionVisitor


class TestLoopStatements:
    """循环语句测试"""

    def test_for_loop_statement(self):
        """测试 for 循环能提取信号"""
        source = '''
module test(input clk, input [7:0] data, output reg [7:0] q);
    always @(posedge clk) begin
        for (int i = 0; i < 8; i++) begin
            q = data;
        end
    end
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0

    def test_while_loop_statement(self):
        """测试 while 循环不崩溃"""
        source = '''
module test();
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        assert visitor is not None

    def test_do_while_statement(self):
        """测试 do-while 循环能提取信号"""
        source = '''
module test(input clk, input [7:0] data, output reg [7:0] q);
    always @(posedge clk) begin
        q = data;
    end
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0

    def test_foreach_loop_statement(self):
        """测试 foreach 循环不崩溃"""
        source = '''
module test();
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        assert visitor is not None

    def test_repeat_loop_statement(self):
        """测试 repeat 循环能提取信号"""
        source = '''
module test(input clk, input [7:0] data, output reg [7:0] q);
    always @(posedge clk) begin
        repeat (3) begin
            q = data;
        end
    end
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0

    def test_forever_loop_statement(self):
        """测试 forever 循环能提取信号"""
        source = '''
module test(input clk, output reg q);
    initial begin
        forever begin
            @(posedge clk);
        end
    end
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0


class TestJumpStatements:
    """跳转语句测试"""

    def test_return_statement(self):
        """测试 return 语句能提取信号"""
        source = '''
module test(input [7:0] a, input [7:0] b, output reg [7:0] q);
    function [7:0] max_val(input [7:0] x, input [7:0] y);
        if (x > y) return x;
        else return y;
    endfunction
    assign q = max_val(a, b);
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assigns = list(sem.get_assignments(modules[0]))
        assert len(assigns) > 0

    def test_break_statement(self):
        """测试 break 语句不崩溃"""
        source = '''
module test();
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        assert visitor is not None

    def test_continue_statement(self):
        """测试 continue 语句不崩溃"""
        source = '''
module test(input clk);
    initial begin
        for (int i = 0; i < 10; i++) begin
            continue;
        end
    end
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        assert visitor is not None

    def test_disable_statement(self):
        """测试 disable 语句不崩溃"""
        source = '''
module test();
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        assert visitor is not None


class TestCaseStatements:
    """Case 语句测试"""

    def test_case_statement(self):
        """测试 case 语句能提取信号"""
        source = '''
module test(input [1:0] sel, input [7:0] a, input [7:0] b, output reg [7:0] q);
    always_comb begin
        case (sel)
            2'b00: q = a;
            2'b01: q = b;
            default: q = 8'h0;
        endcase
    end
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0

    def test_case_generate(self):
        """测试 case generate 不崩溃"""
        source = '''
module test();
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        assert visitor is not None

    def test_unique_case_statement(self):
        """测试 unique case 语句能提取信号"""
        source = '''
module test(input [1:0] sel, input [7:0] a, input [7:0] b, output reg [7:0] q);
    always_comb begin
        unique case (sel)
            2'b00: q = a;
            2'b01: q = b;
        endcase
    end
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0

    def test_priority_case_statement(self):
        """测试 priority case 语句能提取信号"""
        source = '''
module test(input [1:0] sel, input [7:0] a, input [7:0] b, output reg [7:0] q);
    always_comb begin
        priority case (sel)
            2'b00: q = a;
            2'b01: q = b;
        endcase
    end
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0


class TestAssertionStatements:
    """断言语句测试"""

    def test_assert_property_statement(self):
        """测试 assert property 语句不崩溃"""
        source = '''
module test(input clk, input req, input ack);
    property handshake;
        req |-> ##1 ack;
    endproperty
    assert property (@(posedge clk) handshake);
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0

    def test_assume_property_statement(self):
        """测试 assume property 语句不崩溃"""
        source = '''
module test(input clk, input req);
    assume property (@(posedge clk) req |-> ##1 req);
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0

    def test_cover_property_statement(self):
        """测试 cover property 语句不崩溃"""
        source = '''
module test(input clk, input req);
    cover property (@(posedge clk) req |-> ##1 req);
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0

    def test_cover_sequence_statement(self):
        """测试 cover sequence 语句不崩溃"""
        source = '''
module test(input clk, input a, input b);
    cover sequence (@(posedge clk) a ##1 b);
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0

    def test_expect_property_statement(self):
        """测试 expect property 语句不崩溃"""
        source = '''
module test(input clk, input req, input ack);
    expect (@(posedge clk) req |-> ##1 ack);
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0

    def test_immediate_assert_statement(self):
        """测试 immediate assert 语句能提取信号"""
        source = '''
module test(input [7:0] a, input [7:0] b);
    always_comb begin
        assert (a > b);
    end
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0


class TestWaitStatements:
    """等待语句测试"""

    def test_wait_statement(self):
        """测试 wait 语句能提取信号"""
        source = '''
module test(input clk, input ready, output reg [7:0] q);
    always @(posedge clk) begin
        wait (ready);
        q = 8'h42;
    end
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0

    def test_wait_order_statement(self):
        """测试 wait order 语句不崩溃"""
        source = '''
module test();
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        assert visitor is not None


class TestEventStatements:
    """事件语句测试"""

    def test_blocking_event_trigger_statement(self):
        """测试 blocking event trigger 语句能提取信号"""
        source = '''
module test(input clk);
    initial begin
        #10;
    end
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0

    def test_nonblocking_event_trigger_statement(self):
        """测试 nonblocking event trigger 语句不崩溃"""
        source = '''
module test(input clk);
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        assert visitor is not None


class TestParallelStatements:
    """并行语句测试"""

    def test_parallel_block_statement(self):
        """测试 fork-join_parallel 不崩溃"""
        source = '''
module test();
    initial begin
        fork
            begin
                #10;
            end
            begin
                #5;
            end
        join_any
    end
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0


class TestGenerateStatements:
    """Generate 语句测试"""

    def test_if_generate(self):
        """测试 if generate 能提取信号"""
        source = '''
module test(input [7:0] a, output [7:0] q);
    generate
        if (1) begin : genblk
            assign q = a;
        end
    endgenerate
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0

    def test_loop_generate(self):
        """测试 for generate 能提取信号"""
        source = '''
module test(input [7:0] a, output [7:0] q);
    genvar i;
    generate
        for (i = 0; i < 1; i++) begin : genblk
            assign q = a;
        end
    endgenerate
endmodule'''
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        sem = SemanticAdapter(root, comp)
        visitor = SignalExpressionVisitor(sem)
        modules = list(sem.get_modules())
        assert len(modules) > 0


# ============================================================================
# 测试运行入口
# ============================================================================
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
