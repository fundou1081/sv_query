# ==============================================================================
# trace - SystemVerilog 信号追踪框架
# ==============================================================================

# [D5] pyslang v11 only — alias bridge: pyslang v11 把几乎所有 AST 类型 (Compilation,
# SyntaxKind, SyntaxTree, TokenKind, ValueDriver, NamedValueExpression, RootSymbol,
# InstanceBodySymbol, InstanceSymbol, StatementBlockSymbol, Token, ...) 移到 pyslang.ast
# / pyslang.syntax / pyslang.parsing / pyslang.analysis 子模块, 但业务代码常用 `pyslang.X`
# 顶层形式 (type annotation, isinstance, attribute). 这里加 PEP 562 __getattr__ fallback:
# 任何 pyslang.X 找不到时, 自动去 pyslang.ast 找. 这不是 v9/v10 compat, 是 v11 子模块
# → 顶层的通用 bridge. 加 noqa 因为我们有意扩展 pyslang.

import sys as _sys
import pyslang as _pyslang
from pyslang import ast as _pyslang_ast
from pyslang import syntax as _pyslang_syntax
from pyslang import parsing as _pyslang_parsing
from pyslang import analysis as _pyslang_analysis


# PEP 562: module-level __getattr__ 让 pyslang.X 找不到时去 v11 子模块找
# 注意: 不能用 hasattr(_pyslang, name) — 它会触发 __getattr__ 自身, 导致无限递归
# 改用直接查 _pyslang.__dict__ (用 'in' 操作符, 不触发 attribute lookup)
def _pyslang_getattr(name):
    # 1) pyslang 顶层 (用 dict lookup, 不触发 __getattr__)
    if name in _pyslang.__dict__:
        return _pyslang.__dict__[name]
    # 2) v11 子模块查找 (按 ast → syntax → parsing → analysis 顺序)
    for sub in (_pyslang_ast, _pyslang_syntax, _pyslang_parsing, _pyslang_analysis):
        # 用 getattr with default 避免 sub 也触发 __getattr__ (虽然 sub 不会有此问题, 但防御性写法)
        obj = getattr(sub, name, None)
        if obj is not None:
            setattr(_pyslang, name, obj)
            return obj
    raise AttributeError(f"module 'pyslang' has no attribute {name!r}")
_pyslang.__getattr__ = _pyslang_getattr
# Note: 不 del _pyslang/_pyslang_*/_sys — 它们被 _pyslang_getattr 闭包引用, 必须保留
del _pyslang_getattr


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
