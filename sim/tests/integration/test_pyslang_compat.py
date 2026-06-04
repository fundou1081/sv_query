"""
[Stage 6] pyslang 10/11 兼容层测试
"""
import sys
sys.path.insert(0, '/Users/fundou/my_dv_proj/sv_query/src')
import pytest
from trace.core._pyslang_compat import (
    SyntaxKind, SyntaxTree, TokenKind, Compilation,
    ValueDriver, NamedValueExpression, _detect_version,
)


class TestCompatImports:
    """v10 + v11 都能 import 成功"""

    def test_syntax_kind_imported(self):
        assert SyntaxKind is not None
        # SyntaxKind 是 enum, 有 .SomeMember
        assert hasattr(SyntaxKind, "IntegerLiteral") or hasattr(SyntaxKind, "IdentifierName")

    def test_syntax_tree_imported(self):
        assert SyntaxTree is not None
        assert hasattr(SyntaxTree, "fromText")

    def test_token_kind_imported(self):
        assert TokenKind is not None

    def test_compilation_imported(self):
        assert Compilation is not None
        # 验证可以实例化
        c = Compilation()
        assert c is not None
        assert hasattr(c, "getRoot")

    def test_value_driver_imported(self):
        # ValueDriver 在 v10/v11 都在, 但 import 路径不同
        assert ValueDriver is not None

    def test_named_value_expression_imported(self):
        assert NamedValueExpression is not None


class TestPyslangInjection:
    """v11+ 上, shim 把缺省 attr 注入到 pyslang 主模块"""

    def test_compilation_injected(self):
        import pyslang
        assert hasattr(pyslang, "Compilation")
        assert pyslang.Compilation is Compilation

    def test_syntax_kind_injected(self):
        import pyslang
        assert hasattr(pyslang, "SyntaxKind")
        assert pyslang.SyntaxKind is SyntaxKind

    def test_syntax_tree_injected(self):
        import pyslang
        assert hasattr(pyslang, "SyntaxTree")
        assert pyslang.SyntaxTree is SyntaxTree

    def test_fallback_to_ast(self):
        """PEP 562 fallback: pyslang.X (v11 顶层无) 走 ast 子模块"""
        import pyslang
        # v11 上 InstanceBodySymbol 在 pyslang.ast
        if _detect_version() == "v11+":
            assert hasattr(pyslang, "InstanceBodySymbol")
            # InstanceBodySymbol 应该是从 ast 来
            from pyslang.ast import InstanceBodySymbol
            assert pyslang.InstanceBodySymbol is InstanceBodySymbol

    def test_unknown_attr_raises(self):
        """不存在的 attr 应该 raise AttributeError, 不是 silently None"""
        import pyslang
        with pytest.raises(AttributeError):
            _ = pyslang.SomeRandomThingNotExist123


class TestRealCompilation:
    """实际能编译 SystemVerilog 源码"""

    def test_compile_simple_module(self):
        source = "module top; logic [7:0] data; endmodule"
        comp = Compilation()
        tree = SyntaxTree.fromText(source)
        comp.addSyntaxTree(tree)
        root = comp.getRoot()
        assert root is not None
