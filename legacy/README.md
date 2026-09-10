# legacy/ — 已移出的历史实现 (可恢复)

> **原则** (方豆 iter_174): "用移出代替删除，这样可以恢复" — 不再使用的实现
> 移到本目录保留, 不删除。恢复方式见下。

## 清单

| 文件 | 原路径 | 移出时间 | 原因 |
|---|---|---|---|
| `base_pyslang_adapter.py` | `src/trace/core/base.py` | 2026-09-08 (iter_174) | **2,341 行 legacy adapter 层**: `ASTWalker` + `PyslangAdapter` (2,067 行) + 3 个 Collector。在 src/ **从未被实例化** (运行时唯一 adapter = `SemanticAdapter`) — 仅 8 处类型注解引用 (已改为 `SemanticAdapter`) + 少量测试 (已移植/退役)。2026-07-15 的 V2 清理删除了 `core/pyslang_adapter.py` 但漏掉本层。 |

## 恢复方式

```bash
git mv legacy/base_pyslang_adapter.py src/trace/core/base.py
# 然后把 src/ 中 `SemanticAdapter` 注解改回 `PyslangAdapter` (8 处, git show bcbdc5c 可查),
# 并恢复 core/__init__.py 的导出 —— 但注意: 运行时从未使用该层, 恢复通常没有必要。
```

守卫: `sim/tests/unit/test_no_pyslang_adapter_legacy.py` + `sim/tests/integration/test_pyslang_v11_aliases.py::test_base_legacy_layer_moved_out`
会在 legacy 层被重新引入到 `src/` 时报错。
