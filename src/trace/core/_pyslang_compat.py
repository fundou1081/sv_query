"""
pyslang 版本兼容层
==================

处理 pyslang 10.x → 11.x 的 breaking changes (submodule 重构).

## Background

pyslang 11.0 (2026-05-15) 把 bindings 拆成 submodules 匹配 C++ namespace:

| API                 | v10 path                  | v11 path                   |
|---------------------|---------------------------|----------------------------|
| `SyntaxKind`        | `pyslang.SyntaxKind`      | `pyslang.syntax.SyntaxKind`|
| `SyntaxTree`        | `pyslang.SyntaxTree`      | `pyslang.syntax.SyntaxTree`|
| `TokenKind`         | `pyslang.TokenKind`       | `pyslang.parsing.TokenKind`|
| `Compilation`       | `pyslang.Compilation`     | `pyslang.ast.Compilation`  |
| `ValueDriver`       | `pyslang.ast.ValueDriver` | `pyslang.analysis.ValueDriver` |
| `DiagnosticEngine`  | top-level (无参)          | top-level (需 sourceManager)|

CHANGELOG 引用:
> "pyslang bindings are now separated into submodules matching the C++
>  API namespaces, which will require adding imports to your existing
>  scripts to make them continue to run"

## Strategy

- 探测 pyslang 版本 (v10 全部 top-level, v11 大部分进 submodule)
- 在 import 时 try v10 路径, except 后 try v11 路径
- 提供统一的 re-export, 业务代码 `from trace.core._pyslang_compat import X` 即可
- 不影响 `import pyslang` 本身 (子模块用 `pyslang.X` 引用仍然 OK)

## Usage

```python
# 旧:
from pyslang import SyntaxKind, SyntaxTree, TokenKind
from pyslang import Compilation  # 仅 v10

# 新 (兼容 v10 + v11):
from trace.core._pyslang_compat import (
    SyntaxKind, SyntaxTree, TokenKind, Compilation,
    ValueDriver, NamedValueExpression,
)
```

## Verified

- pyslang 10.0.0: ✅
- pyslang 11.0.0: ✅
"""
from __future__ import annotations

# 内部探测 v10 vs v11, 根据是否能从 top-level 导入 SyntaxKind 判断
_IS_V10 = False
_IS_V11_PLUS = False
try:
    from pyslang import SyntaxKind as _SyntaxKind_v10
    _IS_V10 = True
except ImportError:
    _IS_V11_PLUS = True


def _detect_version() -> str:
    """返回 'v10' / 'v11+' / 'unknown'"""
    if _IS_V10:
        return "v10"
    if _IS_V11_PLUS:
        return "v11+"
    return "unknown"


# ----------------------------------------------------------------------------
# 1. SyntaxKind (v10: top, v11: pyslang.syntax)
# ----------------------------------------------------------------------------
try:
    from pyslang import SyntaxKind  # v10
except ImportError:
    from pyslang.syntax import SyntaxKind  # v11


# ----------------------------------------------------------------------------
# 2. SyntaxTree (v10: top, v11: pyslang.syntax)
# ----------------------------------------------------------------------------
try:
    from pyslang import SyntaxTree  # v10
except ImportError:
    from pyslang.syntax import SyntaxTree  # v11


# ----------------------------------------------------------------------------
# 3. TokenKind (v10: top, v11: pyslang.parsing)
# ----------------------------------------------------------------------------
try:
    from pyslang import TokenKind  # v10
except ImportError:
    from pyslang.parsing import TokenKind  # v11


# ----------------------------------------------------------------------------
# 4. Compilation (v10: top, v11: pyslang.ast)
# ----------------------------------------------------------------------------
try:
    from pyslang import Compilation  # v10
except ImportError:
    from pyslang.ast import Compilation  # v11


# ----------------------------------------------------------------------------
# 5. ValueDriver (v10: pyslang.ast, v11: pyslang.analysis)
# ----------------------------------------------------------------------------
try:
    from pyslang.ast import ValueDriver  # v10
except ImportError:
    from pyslang.analysis import ValueDriver  # v11


# ----------------------------------------------------------------------------
# 6. NamedValueExpression (v10 + v11 都在 pyslang.ast, 稳定)
# ----------------------------------------------------------------------------
from pyslang.ast import NamedValueExpression


# ----------------------------------------------------------------------------
# 7. DiagnosticEngine (v10: top 无参, v11: top 需 sourceManager 参数)
#    我们的代码之前 import 了但未实际用, 这里不 re-export,
#    业务代码真用时自己处理版本差异
# ----------------------------------------------------------------------------
# Note: 不导出 DiagnosticEngine, 因为我们目前没真用, 真用时:
#   v10:  DiagnosticEngine()
#   v11+: DiagnosticEngine(source_manager)


__all__ = [
    "SyntaxKind",
    "SyntaxTree",
    "TokenKind",
    "Compilation",
    "ValueDriver",
    "NamedValueExpression",
    "_detect_version",
]


# ----------------------------------------------------------------------------
# 8. 注入到 pyslang 主模块 (覆盖 `pyslang.X` attribute 用法)
#    业务代码常见形态: `pyslang.Compilation()`, `pyslang.SyntaxTree.fromText(...)`,
#    `pyslang.SyntaxKind.SomeKind` 等, 这些不走 import, 所以 shim 必须注入。
# ----------------------------------------------------------------------------
if _IS_V11_PLUS:
    import pyslang as _pyslang_mod  # noqa: F811

    # v10 中有但 v11 top-level 缺失的 attr, 反向注入以保持 `pyslang.X` 形式可用
    _INJECT_MAP = {
        "SyntaxKind": SyntaxKind,
        "SyntaxTree": SyntaxTree,
        "TokenKind": TokenKind,
        "Compilation": Compilation,
        "ValueDriver": ValueDriver,
        "NamedValueExpression": NamedValueExpression,
    }
    for _name, _obj in _INJECT_MAP.items():
        if not hasattr(_pyslang_mod, _name):
            setattr(_pyslang_mod, _name, _obj)
    del _INJECT_MAP, _name, _obj

    # [Stage 6] PEP 562 fallback: 业务代码常用 `pyslang.SomeSymbol` 形式访问
    # AST 类型, 这些在 v11 中都在 pyslang.ast 子模块。给 pyslang module 加
    # __getattr__, 找不到时去 ast 子模块找。
    def _pyslang_fallback(name):
        """v11 fallback: pyslang.X 找不到时, 从 pyslang.ast 找"""
        from pyslang import ast as _ast
        if hasattr(_ast, name):
            return getattr(_ast, name)
        raise AttributeError(f"module 'pyslang' has no attribute {name!r}")

    _pyslang_mod.__getattr__ = _pyslang_fallback
    del _pyslang_fallback, _pyslang_mod


# 模块级便捷提示 (debug 用)
if __name__ == "__main__":
    print(f"pyslang version detected: {_detect_version()}")
    print(f"SyntaxKind: {SyntaxKind}")
    print(f"SyntaxTree: {SyntaxTree}")
    print(f"Compilation: {Compilation}")
    # 验证注入
    import pyslang as _p
    print(f"pyslang.Compilation == Compilation: {_p.Compilation is Compilation}")
    print(f"pyslang.SyntaxTree == SyntaxTree: {_p.SyntaxTree is SyntaxTree}")
