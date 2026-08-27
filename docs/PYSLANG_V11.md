# pyslang v11 only policy

> 创建时间: 2026-06-04 (compat shim)
> 重构时间: 2026-08-27 (D5 — 删除 compat shim, 加 alias bridge)
> 状态: ✅ D5 LOCKED (om_x100b67c3047874a0c44881d1ea50581) — v11 only, v9/v10 不再考虑
> 范围: `pyproject.toml` 锁 `pyslang>=11.0.0,<12.0.0`

---

## 1. 背景

pyslang 11.0 (2026-05-15 发布) 引入了两个层面的 breaking changes:

1. **API 重构**: bindings 按 C++ namespace 拆 submodules
   - `pyslang.Compilation` → `pyslang.ast.Compilation`
   - `pyslang.SyntaxKind` / `SyntaxTree` → `pyslang.syntax.*`
   - `pyslang.TokenKind` → `pyslang.parsing.TokenKind`
   - `pyslang.ValueDriver` → `pyslang.analysis.ValueDriver`
   - `pyslang.NamedValueExpression` → `pyslang.ast.NamedValueExpression`
   - 几乎所有 AST 节点 (RootSymbol / InstanceBodySymbol / InstanceSymbol /
     StatementBlockSymbol / Token / ...) 都搬到 `pyslang.ast.*`
2. **语义变化**: SyntaxList / SeparatedList 包装层消失 — 现在 `.items` 直接是 plain list

## 2. D5 决策 (2026-08-27)

**用户原话** (07:20 GMT+8): *"那我们确定一下版本，以后仅支持 v11 api，之后都不要再考虑 v9 和 v10 兼容的事情。"*

**结果**:
- ❌ 删 `_pyslang_compat.py` (232 行 compat shim 完全消亡)
- ✅ 加 `trace/__init__.py` v11 alias bridge (PEP 562 `__getattr__` fallback)
- ✅ 5 个 import site 改用 `pyslang.ast.*` / `pyslang.syntax.*` 直接导入
- ✅ `is_syntax_list` / `iter_syntax_list` helper 从 compat 文件迁到 `trace/core/ast_utils.py`
- ✅ 5 个 `[Stage 6] v10/v11` 注释清理 (uvm_testbench_extractor / driver_extractor)

## 3. v11 alias bridge (替代 compat shim 的机制)

[位置: `src/trace/__init__.py` 顶部 ~25 行]

**问题**: v11 把几乎所有 AST 类型搬到子模块, 但业务代码常用 `pyslang.X` 顶层形式:
```python
# type annotation
def get_compilation(self) -> pyslang.Compilation: ...
# isinstance
if isinstance(body, pyslang.InstanceBodySymbol): ...
# attribute
tree = pyslang.SyntaxTree.fromText(...)
```

**解法**: 在 `trace/__init__.py` 顶部用 PEP 562 `__getattr__` fallback — 任何 `pyslang.X` 找不到时, 自动去 `pyslang.ast` / `pyslang.syntax` / `pyslang.parsing` / `pyslang.analysis` 子模块找, 找到后 `setattr` 缓存到顶层, 后续直接命中:
```python
def _pyslang_getattr(name):
    if name in _pyslang.__dict__:
        return _pyslang.__dict__[name]
    for sub in (_pyslang_ast, _pyslang_syntax, _pyslang_parsing, _pyslang_analysis):
        obj = getattr(sub, name, None)
        if obj is not None:
            setattr(_pyslang, name, obj)
            return obj
    raise AttributeError(f"module 'pyslang' has no attribute {name!r}")
_pyslang.__getattr__ = _pyslang_getattr
```

**注意**: 
- 不能 `del _pyslang` — 它被 `_pyslang_getattr` 闭包引用
- 不能用 `hasattr(_pyslang, name)` 在 `__getattr__` 里 — 会触发自身无限递归
- 改用 `name in _pyslang.__dict__` (dict 直接 lookup, 不触发 attribute protocol)

## 4. ast_utils.py (helper 迁移目的地)

[位置: `src/trace/core/ast_utils.py` 末尾]

`is_syntax_list` / `iter_syntax_list` 从原 `_pyslang_compat.py` 迁过来, 简化 v11-only 实现:
- `is_syntax_list(node)`: `isinstance(node, list)` 或 `kind` 含 `SeparatedList` / `SyntaxList`
- `iter_syntax_list(node)`: 直接 `list(node)`

调用方 (`semantic_adapter.py` 8 处 + `base.py` 2 处) 改 `from trace.core.ast_utils import is_syntax_list, iter_syntax_list`。

## 5. 测试覆盖

[位置: `sim/tests/integration/test_pyslang_v11_aliases.py`]

| 测试类 | 测试数 | 验证什么 |
|---|---|---|
| `TestV11AliasBridge::test_alias_present` | 6 (parametrize) | `pyslang.{Compilation,SyntaxKind,SyntaxTree,TokenKind,ValueDriver,NamedValueExpression}` 可访问 |
| `TestV11AliasBridge::test_alias_identity` | 6 (parametrize) | alias 跟子模块中真实类 same object |
| `TestAstUtilsHelpers` | 5 | is_syntax_list / iter_syntax_list 行为 |
| `TestImportPaths` | 5 | 关键模块 (semantic_adapter / compiler / base / mig_validator / graph_builder) 能 import |
| `TestRealV11Compilation` | 1 | 真实 `compile_sources` 跑通 |

[位置: `sim/tests/integration/test_pyslang_v11_cli_smoke.py`]

12 个 tests, 含 7 个 CLI 命令 (trace / verify / risk / dataflow / controlflow / cdc + trace_json) 的 v11 smoke。

## 6. 验证统计 (commit 62ef835 HEAD)

| 层 | 通过 | 失败 | 说明 |
|---|---|---|---|
| Unit tests (sim/tests/unit) | **1061** | 0 | 全部通过, 62.29s |
| Integration (377 - 5 pre-exist) | 377 | 2 pre-exist | darkriscv/picorv32 SVG (base 也 fail) |
| v11 alias + helpers | 19 | 0 | 全部通过 |
| v11 CLI smoke | 12 | 0 | 全部通过 |
| Case27 truth | 1 | 3 pre-exist | iter_032 documented gaps |
| **总计** | **1470** | 5 (均 pre-existing) | **0 回归** |

## 7. 维护指南

**新代码**:
```python
# 直接从子模块 import (推荐 — 清晰)
from pyslang.ast import Compilation, InstanceBodySymbol, NamedValueExpression
from pyslang.syntax import SyntaxKind, SyntaxTree
from pyslang.parsing import TokenKind
from pyslang.analysis import ValueDriver

# 或者用 pyslang.X 形式 (alias bridge 自动解析)
import pyslang
comp = pyslang.Compilation()  # 自动从 pyslang.ast 找
if isinstance(body, pyslang.InstanceBodySymbol): ...  # 自动从 pyslang.ast 找
```

**不要**:
- ❌ 不要再加 v9/v10 compat 代码
- ❌ 不要重新创建 `_pyslang_compat.py`
- ❌ 不要用 `hasattr(pyslang, 'X')` 探测 (alias bridge 会让 v11 看起来什么都有)

**保留**:
- ✅ `trace/core/ast_utils.py` 的 `is_syntax_list` / `iter_syntax_list` (虽然 v11 是 plain list, 但保留 `kind` 检查作为 safety net)

## 8. 相关文档

- `docs/architecture/case27_signal_graph_completeness_decision.md` — D1-D5 决策记录
- `docs/task_tree/iterations/iter_034_pyslang_v11_only_cleanup.md` — 实际执行记录
- `docs/ARCHITECTURE_EVOLUTION.md` 第 8 节 — iter_034 在版本演进史中的位置
