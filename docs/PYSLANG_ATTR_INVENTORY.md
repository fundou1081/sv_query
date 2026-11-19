# pyslang 属性 / kind 清单（P184 Phase 0）

> **状态**: inventory，不启动 ASTFrontend Protocol。
> **来源**: `tools/scan_pyslang_attrs.py --json --ratchet` + `tools/pyslang_attr_baseline.json`
> **日期**: 2026-11-19

## 1. 为什么 50 不是基线

旧扫描器用 receiver 名字启发式，当前树 50 处“候选”里：

```text
真实 pyslang getter      10 处（7 个 baseline 条目）
wrapper / dataclass      36 处
未 review 的 unknown     14 处（无 baseline 时）
```

`tools/pyslang_attr_baseline.json` 只保存 **10 个真实 pyslang 读取** 和 3 个
人工 review 的 wrapper 例外；`--ratchet` 只拦新增 pyslang / unknown，不把 50 当基线。

## 2. 风险属性名

`RISKY`（getter 可能抛 `UnicodeDecodeError` / pyslang 内部错误）：

```text
name, type, symbol, baseClass, body, members,
elementType, arrayElementType
```

## 3. 已确认的 pyslang getter 读取

| 文件 | receiver | attr | count |
|---|---|---|---:|
| `sv_query/trace/core/bit_select_handler.py` | `decl` | `name` | 1 |
| `sv_query/trace/core/covergroup_extractor.py` | `node` | `body` | 1 |
| `sv_query/trace/core/driver_extractor.py` | `ref_expr` | `symbol` | 2 |
| `sv_query/trace/core/driver_extractor.py` | `ref_expr.symbol` | `name` | 1 |
| `sv_query/trace/core/extractors/alias_extractor.py` | `ref_expr` | `symbol` | 2 |
| `sv_query/trace/core/extractors/alias_extractor.py` | `ref_expr.symbol` | `name` | 1 |
| `sv_query/trace/core/semantic/ports_ifaces.py` | `module` | `body` | 2 |

每条 baseline 都有 `reason`/`evidence`，不是仅靠变量名。

## 4. kind 字符串（当前代码中观察到的代表值）

```text
SyntaxKind.VariableDim
SyntaxKind.BinaryExpression
SyntaxKind.ConcatenationExpression
SymbolKind.Instance
SymbolKind.InstanceArray
SymbolKind.Definition
SymbolKind.GenerateBlock
SymbolKind.GenerateBlockArray
SymbolKind.Sequence
SymbolKind.Property
Expression kinds: AssignmentExpression, RangeSelect
Statement kinds: fork, randomize, if, case
```

这是未来 `pyslang_v11.py` 的输入清单，不是完整 pyslang enum；新增 kind 由
ratchet/review 扩展。

## 5. 使用

```bash
python3 tools/scan_pyslang_attrs.py --check
# [ratchet] PASS: pyslang 10 处均在 baseline; unknown 0
```
