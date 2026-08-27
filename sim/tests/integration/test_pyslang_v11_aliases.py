"""
v11-only: 测试 pyslang v11 子模块 → 顶层 alias bridge (D5 实施后)

D5 Phase 4 删除了 _pyslang_compat.py. 替代方案是在 trace/__init__.py 顶部
把 pyslang v11 移走的 6 个类 (Compilation/SyntaxKind/SyntaxTree/TokenKind/
ValueDriver/NamedValueExpression) 通过 setattr 注入到 pyslang 顶层, 让
`pyslang.X` 形式的代码 (compiler.py, native_adapter.py 等) 不用改.

本测试验证:
1. import trace 后, pyslang 顶层确实有这 6 个 alias
2. alias 是同一个 object (不是 placeholder)
3. ast_utils.py 的 is_syntax_list / iter_syntax_list 工作正常
4. trace.core.semantic_adapter / compiler / base 能正常 import (P2 迁移后)
5. compile_sources 能跑 (v11 pyslang.Compilation)
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "src"))

import pyslang  # noqa: E402
import pytest  # noqa: E402

# import trace triggers alias bridge in trace/__init__.py
import trace  # noqa: F401, E402
from trace.core.ast_utils import is_syntax_list, iter_syntax_list  # noqa: E402


V11_ALIASED_TYPES = [
    "Compilation",
    "SyntaxKind",
    "SyntaxTree",
    "TokenKind",
    "ValueDriver",
    "NamedValueExpression",
]


class TestV11AliasBridge:
    """trace/__init__.py 注入的 v11 alias"""

    @pytest.mark.parametrize("name", V11_ALIASED_TYPES)
    def test_alias_present(self, name):
        assert hasattr(pyslang, name), f"pyslang.{name} missing after trace import"

    @pytest.mark.parametrize("name", V11_ALIASED_TYPES)
    def test_alias_identity(self, name):
        """alias 必须指向真实 v11 类 (从对应子模块), 不是 placeholder"""
        v11_obj = getattr(pyslang, name)
        # import 对应子模块, 验证是同一对象
        from pyslang.ast import (
            Compilation as _C, NamedValueExpression as _N,
        )
        from pyslang.syntax import SyntaxKind as _SK, SyntaxTree as _ST
        from pyslang.parsing import TokenKind as _TK
        from pyslang.analysis import ValueDriver as _VD
        m = {
            "Compilation": _C, "SyntaxKind": _SK, "SyntaxTree": _ST,
            "TokenKind": _TK, "ValueDriver": _VD, "NamedValueExpression": _N,
        }
        assert v11_obj is m[name], f"pyslang.{name} != real v11 class"


class TestAstUtilsHelpers:
    """ast_utils.py 的 is_syntax_list / iter_syntax_list (P4 从 _pyslang_compat 迁移)"""

    def test_is_syntax_list_none(self):
        assert is_syntax_list(None) is False

    def test_is_syntax_list_plain_list(self):
        assert is_syntax_list([1, 2, 3]) is True

    def test_is_syntax_list_string(self):
        assert is_syntax_list("hello") is False

    def test_iter_syntax_list_none(self):
        assert iter_syntax_list(None) == []

    def test_iter_syntax_list_plain_list(self):
        assert iter_syntax_list([1, 2, 3]) == [1, 2, 3]


class TestImportPaths:
    """P2 迁移后, 关键模块仍能 import (没有 _pyslang_compat 依赖)"""

    def test_semantic_adapter(self):
        from trace.core.semantic_adapter import SemanticAdapter
        assert SemanticAdapter is not None

    def test_compiler(self):
        from trace.core.compiler import compile_sources
        assert compile_sources is not None

    def test_base(self):
        from trace.core.base import ASTWalker, PyslangAdapter
        assert ASTWalker is not None
        assert PyslangAdapter is not None

    def test_mig_validator(self):
        # mig_validator 导出的是 compare_with_extract_module + verify_specific_port
        # (MIG 是 production path, 不替换; native API 仅作 verification tool)
        from trace.core.mig_validator import (
            compare_with_extract_module, verify_specific_port,
        )
        assert compare_with_extract_module is not None
        assert verify_specific_port is not None

    def test_graph_builder(self):
        from trace.core.graph_builder import GraphBuilder
        assert GraphBuilder is not None


class TestRealV11Compilation:
    """v11 真实编译 (验证 alias bridge + 导入路径都通)"""

    def test_compile_simple(self):
        # D5: 用 alias bridge 拿 pyslang.Compilation (顶层) + pyslang.SyntaxTree
        # 这是测 alias bridge 在 compile_sources 真实路径上工作
        from trace.core.compiler import compile_sources
        comp, _ = compile_sources({"test.sv": "module top; logic [7:0] data; endmodule"})
        root = comp.getRoot()
        assert root is not None
        assert root.topInstances  # v11 native API
