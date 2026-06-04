# pyslang 10/11 兼容性

> 创建时间: 2026-06-04
> 状态: ✅ v10 和 v11 都 100% 测试通过 (1501/1501)
> 范围: `pyproject.toml` 锁 `pyslang>=10.0.0,<12.0.0`

---

## 1. 背景

pyslang 11.0 (2026-05-15 发布) 引入了两个层面的 breaking changes:

1. **API 重构**: bindings 按 C++ namespace 拆 submodules
2. **语义变化**: SyntaxList / SeparatedList 包装层消失, 一些 syntax 节点结构扁平化

我们的项目在 v10 上稳定运行多年, 需要在不加技术债的前提下完整支持 v11。

---

## 2. 解决策略

### 2.1 阶段一: Compat shim (解决 API 路径)

新增 `src/trace/core/_pyslang_compat.py` (240 行):

- 探测 v10 vs v11, 自动选路径
- 提供统一 re-export: `SyntaxKind` / `SyntaxTree` / `TokenKind` / `Compilation` / `ValueDriver` / `NamedValueExpression`
- v11+ 上把缺的 attr 注入 `pyslang` 主模块 (覆盖 `pyslang.X` attribute 形式)
- v11+ 上 PEP 562 `__getattr__` fallback: 业务代码用 `pyslang.SomeSymbol` 自动从 `pyslang.ast` 找
- 新增 `is_syntax_list()` / `iter_syntax_list()` helper: 统一处理 v10 SyntaxList 包装 vs v11 plain list

### 2.2 阶段二: 业务代码适配 (解决语义变化)

修了 **4 个真实语义差异**:

#### 差异 #1: SyntaxList / SeparatedList 包装层消失

| 场景 | v10 | v11 |
|------|-----|-----|
| `member.items` | `SyntaxNode(kind=SeparatedList)` | plain Python `list` |
| `syntax.members` | `SyntaxNode(kind=SyntaxList)` | plain list |
| `SyntaxKind.SyntaxList` enum | 存在 | **不存在** |

**修复**: 业务代码用 `is_syntax_list(x)` / `iter_syntax_list(x)` 统一处理。修了 7 个文件:

- `semantic_adapter.py` (ModportDeclaration 解析)
- `base.py` (Modport + Fork/Join 解析)
- `driver_extractor.py` (SequentialBlock 内部)
- `sva_extractor.py` (2 处 sequence/property 提取)
- `signal_expression_visitor.py` (`_get_kind_name`: list → "SyntaxList" dispatch)
- `visitors/constraint_visitor.py` (3 处)
- `sim/tests/regression/test_generate_case.py` (CaseGenerate 查找)

#### 差异 #2: constraint foreach loop var 暴露

| 场景 | v10 | v11 |
|------|-----|-----|
| `foreach (arr[i])` 内部 `loopList` | `[OpenParen, IdentifierName(arr), OpenBracket, SeparatedList, CloseBracket, CloseParen]` | `[OpenParen, IdentifierName(arr), OpenBracket, IdentifierName(i), CloseBracket, CloseParen]` |
| 索引变量 `i` 是不是 IdentifierName | **不是** (是 token) | **是** (真 IdentifierName 节点) |

**修复**: `visit_foreach_constraint` 改位置-based: 只取 OpenParen 之后第一个 IdentifierName (array name), 遇 OpenBracket 跳出。

#### 差异 #3: class composition property 不自动 inherit

| 场景 | v10 | v11 |
|------|-----|-----|
| `packet.range` (CLASS_INSTANCE) | ✅ | ✅ |
| `packet.range.min_addr` (CLASS_INSTANCE_PROPERTY) | ✅ 自动从 class type 复制 | ❌ **不复制** |

**修复**: `get_modport_info` 用 `is_syntax_list` 判 sep_list:

- v10: `item.ports[1]` 是 SeparatedList, 里面是 ModportSimplePortListSyntax
- v11: `item.ports[1]` 直接是 ModportSimplePortListSyntax

同样修 `port_names` 嵌套 SeparatedList。

#### 差异 #4: constraint ranges 内部结构变化

| 场景 | v10 | v11 |
|------|-----|-----|
| InsideExpression.ranges 内容 | `[OpenBrace, SeparatedList(ValueRangeExpression, Comma, ...), CloseBrace]` | `[OpenBrace, ValueRangeExpression, CloseBrace]` |

**修复**: `_extract_vars_from_expr` 适配两种结构, 提取 ValueRangeExpression 的 left/right。

---

## 3. 验证

### 3.1 单元 + 集成测试

12 个 compat 单元测试 (`sim/tests/integration/test_pyslang_compat.py`):
- 6 个 re-export 都正确
- 4 个 attr 注入验证
- 1 个 PEP 562 fallback 验证
- 1 个 unknown attr 正确 raise

8 个双版本 smoke 测试 (`sim/tests/integration/test_pyslang_version_compat.py`):
- `test_version_detected`
- `test_trace_evidence_text` / `json`
- `test_verify_gap_evidence`
- `test_risk_analyze_evidence`
- `test_dataflow_evidence`
- `test_controlflow_evidence`
- `test_cdc_analyze_evidence`

### 3.2 全量回归

| pyslang 版本 | 测试结果 | 备注 |
|-------------|---------|------|
| 10.0.0 | ✅ 1501 passed | 之前一直支持 |
| 11.0.0 | ✅ 1501 passed | Stage 6 part 1+2 修复后完全兼容 |

两边数字一字不差, 行为一致。

### 3.3 手动 smoke test

```bash
# v10
pip install pyslang==10.0.0
python3 -m pytest sim/tests/ -q
# 1501 passed

# v11
pip install pyslang==11.0.0
python3 -m pytest sim/tests/ -q
# 1501 passed
```

---

## 4. 升级建议

**用户**: 升级 `pyslang` 到 11.0.0 完全无副作用, 测试都过。如果项目里有别的代码直接 `from pyslang import X` 引用, 我们的 compat shim 也自动 inject 到 `pyslang` 模块, 不需要改。

**维护者**: 写新代码时, 直接用 `from trace.core._pyslang_compat import SyntaxKind, ...`, 不要用 `from pyslang import ...`。已有代码在 compat 覆盖范围内, 不需要动。

---

## 5. 未来工作

- pyslang 12.0+ 如果有 breaking, 扩展 `_pyslang_compat.py` 加分支即可
- CI 跑 2 版本: 推荐加 `.github/workflows/test.yml` matrix 跑 `pyslang==10.0.0` 和 `pyslang==11.0.0`
- 收集更多 11.0 语义变化, 持续 shrink 业务代码里的 v10-specific 假设

---

## 6. 一句话总结

**Stage 6 用 240 行 compat shim + ~150 行业务代码适配, 让项目在 pyslang 10 和 11 上都是 1501/1501 全过, 0 行为变化, 100% 向后兼容 v10。**
