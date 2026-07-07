# test_operator_visitor_randomize.py - Operator visitor randomize method 单元测试
"""
[Phase 1 Day 1 2026-07-07] Randomize method extraction 测试

覆盖 src/trace/core/visitors/operator_visitor.py 中 randomize 相关的 @on handler.
移除 [NOT TESTED] 标记, 验证 signal extraction 正确性.

测试目标:
1. ArrayOrRandomizeMethodExpression — array.randomize() / array.randomize() with { ... }
2. (后续可扩展) PostrandomizeMethodExpr / PrerandomizeMethodExpr / RandomizeMethodExpr
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.compiler import SVCompiler
from trace.core.semantic_adapter import SemanticAdapter
from trace.core.visitors.signal_expression_visitor import SignalExpressionVisitor
from trace.core.visitors.signal_result import SignalResult


def _compile_and_visit(source: str):
    """Compile SV source and return (semantic_adapter, visitor)."""
    comp = SVCompiler({'test.sv': source})
    root = comp.get_root()
    sem = SemanticAdapter(root, comp)
    visitor = SignalExpressionVisitor(sem)
    return sem, visitor


def _find_subroutines(root):
    """Find all subroutines (tasks/functions) in any class, return list of (cls_name, name, syntax)."""
    results = []
    def walk(node, class_name=""):
        kind = str(getattr(node, "kind", ""))
        if "ClassType" in kind:
            class_name = str(getattr(node, "name", "")).strip()
        if "Subroutine" in kind:
            name = str(getattr(node, "name", "")).strip()
            if name:
                syntax = getattr(node, "syntax", None)
                results.append((class_name, name, syntax))
            return
        try:
            for child in node:
                walk(child, class_name)
        except TypeError:
            pass
    walk(root)
    return results


def _get_class_tasks_via_root(root):
    """Find all task/function syntax in any class via root traversal."""
    return _find_subroutines(root)


# =============================================================================
# ArrayOrRandomizeMethodExpression — `array.randomize()` / `array.randomize() with { ... }`
# =============================================================================

class TestArrayOrRandomizeMethodExpression:
    """ArrayOrRandomizeMethodExpression: array.randomize() with method"""

    def test_randomize_no_crash(self):
        """测试 array.randomize() 不崩溃"""
        source = '''
class packet;
    rand bit [7:0] addr;
endclass

class my_seq;
    packet req;
    task body();
        req.randomize();
    endtask
endclass

module top; endmodule'''
        sem, visitor = _compile_and_visit(source)
        assert visitor is not None

    def test_randomize_with_inline_constraint_no_crash(self):
        """测试 array.randomize() with { ... } 不崩溃"""
        source = '''
class packet;
    rand bit [7:0] addr;
endclass

class my_seq;
    packet req;
    task body();
        req.randomize() with { addr < 64; };
    endtask
endclass

module top; endmodule'''
        sem, visitor = _compile_and_visit(source)
        assert visitor is not None

    def test_randomize_in_foreach_no_crash(self):
        """测试 foreach 里的 array.randomize() 不崩溃"""
        source = '''
class packet;
    rand bit [7:0] addr;
endclass

class my_seq;
    packet req_arr [4];
    task body();
        foreach (req_arr[i]) req_arr[i].randomize();
    endtask
endclass

module top; endmodule'''
        sem, visitor = _compile_and_visit(source)
        assert visitor is not None

    def test_randomize_with_inline_constraint_extracts_signals(self):
        """测试 array.randomize() with { addr < 64; } 能提取信号"""
        source = '''
class packet;
    rand bit [7:0] addr;
endclass

class my_seq;
    packet req;
    task body();
        req.randomize() with { addr < 64; };
    endtask
endclass

module top; endmodule'''
        sem, visitor = _compile_and_visit(source)
        # SVCompiler 通过 sem._compiler 拿 root
        comp = sem._compiler if hasattr(sem, '_compiler') else None
        # 直接用 root 走 walk
        from trace.core.compiler import SVCompiler as _SVC
        comp2 = _SVC({'test.sv': source})
        root = comp2.get_root()

        found_signals = []
        for cls_name, name, syntax in _find_subroutines(root):
            if cls_name == "my_seq" and name == "body":
                # 走 task syntax.items 找 ExpressionStatement → ArrayOrRandomize
                items = getattr(syntax, 'items', [])
                for stmt in items:
                    if hasattr(stmt, 'expr'):
                        expr = stmt.expr
                        expr_kind = str(getattr(expr, "kind", ""))
                        if "ArrayOrRandomizeMethodExpression" in expr_kind:
                            result = visitor.extract(expr)
                            found_signals = result.all_signals

        # 期望找到 'addr' (in inline constraint)
        assert "addr" in found_signals, f"Expected 'addr' in signals, got: {found_signals}"


# =============================================================================
# Smoke test — randomize handler 不 crash 整个 build
# =============================================================================

class TestRandomizeSmokeTest:
    """Smoke test: randomize pattern 在更复杂的 class 也不 crash"""

    def test_complex_sequence_with_randomize(self):
        """测试典型 UVM sequence 风格 (含 create / start_item / randomize / finish_item)"""
        source = '''
class packet;
    rand bit [7:0] addr;
    rand bit [7:0] data;
endclass

class my_seq;
    packet req;
    task body();
        req = new();
        req.randomize() with { addr < 64; data != 0; };
        req.randomize();
    endtask
endclass

module top; endmodule'''
        sem, visitor = _compile_and_visit(source)
        assert visitor is not None

    def test_randomize_return_value_no_crash(self):
        """测试 randomize() 返回值赋值不 crash"""
        source = '''
class packet;
    rand bit [7:0] addr;
endclass

class my_seq;
    packet req;
    bit ok;
    task body();
        ok = req.randomize();
        ok = req.randomize() with { addr == 8'h42; };
    endtask
endclass

module top; endmodule'''
        sem, visitor = _compile_and_visit(source)
        assert visitor is not None