# ==============================================================================
# trace - SystemVerilog 信号追踪框架
# ==============================================================================

# [D5] pyslang v11 only — alias bridge: pyslang v11 把 Compilation/SyntaxKind/
# SyntaxTree/TokenKind/ValueDriver/NamedValueExpression 移到子模块, 但业务代码常
# 用 `pyslang.X` 顶层形式. 这里在 import 时把它们 alias 回顶层 (不是 v9/v10 compat,
# 是 v11 子模块 → 顶层 bridge). 加 noqa 因为我们是有意扩展 pyslang.
import pyslang as _pyslang
from pyslang.ast import Compilation as _Compilation_v11, NamedValueExpression as _NamedValueExpression_v11
from pyslang.syntax import SyntaxKind as _SyntaxKind_v11, SyntaxTree as _SyntaxTree_v11
from pyslang.parsing import TokenKind as _TokenKind_v11
from pyslang.analysis import ValueDriver as _ValueDriver_v11
for _name, _obj in [
    ("Compilation", _Compilation_v11),
    ("SyntaxKind", _SyntaxKind_v11),
    ("SyntaxTree", _SyntaxTree_v11),
    ("TokenKind", _TokenKind_v11),
    ("ValueDriver", _ValueDriver_v11),
    ("NamedValueExpression", _NamedValueExpression_v11),
]:
    if not hasattr(_pyslang, _name):
        setattr(_pyslang, _name, _obj)
del _name, _obj, _pyslang
del _Compilation_v11, _SyntaxKind_v11, _SyntaxTree_v11, _TokenKind_v11, _ValueDriver_v11, _NamedValueExpression_v11


# [D5] pyslang v11 only. No more compat shim — code uses `pyslang.ast` /
# `pyslang.syntax` / `pyslang.parsing` / `pyslang.analysis` directly.
from .core import (
    ClockDomainTracer,
    ModuleTracer,
    SignalGraph,
    SignalTracer,
)
from .unified_tracer import UnifiedTracer

__all__ = [
    "UnifiedTracer",
    "SignalGraph",
    "SignalTracer",
    "ModuleTracer",
    "ClockDomainTracer",
]
