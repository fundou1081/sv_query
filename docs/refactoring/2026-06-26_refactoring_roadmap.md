# sv_query 拆解计划 (2026-06-26)

## 总览: 3 大块并行

| 块 | 范围 | 工作量 | 风险 | 收益 |
|---|------|--------|------|------|
| **A. SignalExpressionVisitor 拆分** | 7312 行 → 6-8 sub_visitor | 2-3 周 | 🟡 MED | 长期可维护 |
| **B. DriverExtractor extract() 拆 method** | 817 行 → 9 private method | 1-2 周 | 🟢 LOW | 立刻可读 |
| **C. P0 helper 抽取** | 7+ try/except → helper | 2-3 天 | 🟢 LOW | 立刻见效 |

---

## C. P0 helper 抽取 (建议先做, 2-3 天)

### 创建 `src/trace/core/_safe_attrs.py`

```python
"""[ADD 2026-06-26] pyslang binary-garbage safe attribute access.

解决 8GB 内存环境下 pyslang partial elaboration 触发的:
- UnicodeDecodeError: pyslang attribute 含非 utf-8 字节
- RuntimeError "mutex lock failed": pyslang 内部 pthread 死锁
- TypeError: str() 失败

替换 7+ 处重复的 try/except 模式.
"""

from typing import Any
MUTEX_ERROR_MARKER = "mutex"

def safe_node_attr(node: Any, attr: str, default: str = "") -> str:
    """安全获取 AST 节点属性, 容错 UnicodeDecodeError / RuntimeError"""
    try:
        val = getattr(node, attr, default)
    except (RuntimeError, Exception) as e:
        if MUTEX_ERROR_MARKER in str(e).lower():
            return default
        return default  # 其他也容错
    if val is None:
        return default
    try:
        return str(val).strip() if val else default
    except (UnicodeDecodeError, TypeError):
        return default

def safe_ident_str(ident: Any, default: str = "") -> str:
    """安全提取 IdentifierName 的 .value string"""
    try:
        val = getattr(ident, "value", default) if ident is not None else default
        if val is None:
            return default
        return str(val).strip()
    except (UnicodeDecodeError, TypeError):
        return default
```

### 替换站点 (7+)

- `statement_collector_visitor._extract_clock` 整个 try/except
- `statement_collector_visitor._extract_reset` 整个 try/except
- `statement_collector_visitor.visit_always_ff` 整个 try/except
- `class_graph_builder._class_name` 整个 try/except
- `signal_expression_visitor.visit_identifier_name` 整个 try/except
- `semantic_adapter._iter_children` getattr 整个 try/except
- `bit_select_handler._extract_all_widths` cls_name try/except
- `bit_select_handler._scan_constraint_bit_selects` cls_name try/except
- `unified_tracer._resolve_class_member_access` class_names 整个 try/except

每处: 6-15 行 try/except → 1 行 helper call

### 验证
跑 7 个 test (单跑), 确认 0 regression

---

## B. DriverExtractor.extract() 拆 method (1-2 周)

### 当前 817 行 = 9 phase (linear sequence)
```
L331-1147: extract()
├── L338-396:   Module loop (init ctx)
├── L397-401:   Port declarations (~5 lines, 1 phase)
├── L402-426:   Variable declarations (~25 lines, 1 phase)
├── L427-479:   Net aliases (~50 lines, 1 phase)
├── L480-518:   Net declarations (~40 lines, 1 phase)
├── L519-884:   Assignments (~365 lines, 1 phase) ← 最大
│   └── L650-848: find_invocations() closure (200 lines)
├── L885-1129:  Always blocks (~245 lines, 1 phase)
└── L1130-1147: Finalize edges (~18 lines, 1 phase)
```

### 拆解 plan

抽 9 个 private method:
```python
def _extract_port_nodes(self, module, result, module_name) -> None: ...
def _extract_var_nodes(self, module, result, module_name) -> None: ...
def _extract_net_aliases(self, module, result, module_name) -> None: ...
def _extract_net_nodes(self, module, result, module_name) -> None: ...
def _extract_assign_edges(self, module, result, module_name) -> None: ...
    # assign phase 最大, 内部 find_invocations 抽 _find_module_invocations
def _extract_always_edges(self, module, result, module_name) -> None: ...
def _finalize_edges(self, result) -> None: ...

def extract(self) -> ExtractorResult:
    result = ExtractorResult()
    self._current_module = None
    self._current_source_file = ""
    for module in self.adapter.get_modules():
        module_name = self.adapter.get_module_name(module)
        self._current_module = module
        src_file, src_line, _, _ = self.adapter.get_source_location(module)
        self._current_source_file = src_file
        self._extract_port_nodes(module, result, module_name)
        self._extract_var_nodes(module, result, module_name)
        self._extract_net_aliases(module, result, module_name)
        self._extract_net_nodes(module, result, module_name)
        self._extract_assign_edges(module, result, module_name)
        self._extract_always_edges(module, result, module_name)
    self._finalize_edges(result)
    return result
```

### 收益
- extract() 30 行 (跟 phase 1:1 映射)
- 9 个 sub-method 单独 <200 行, 各自命名清晰
- find_invocations closure → _find_module_invocations public method, 可单测

---

## A. SignalExpressionVisitor 拆分 (2-3 周, 长期)

### 当前 7312 行
- 536 @on handler (116 boilerplate ≤3 行, 164 medium 4-8 行, 256 long ≥9 行)
- 1 个 VariableDimension 780 行 (最大)
- 11 internal helper
- 1 个 main extract() dispatch
- 45 visit_* (dispatcher)

### 拆法 1: 抽 VariableDimension (优先, 1-2 天)

VariableDimension 780 行应该先拆 method. 看 VariableDimension 内容:
- 拆 5-8 个 sub-method, 每个 <100 行
- extract_variable_dimension main dispatch

### 拆法 2: 按 SV syntax category 拆 sub_visitor (长期, 1-2 周)

按 @on kind 分组, 拆成 6-8 个 sub_visitor.py:

```
src/trace/core/visitors/signal_expression/
├── __init__.py                    # re-export
├── _base.py                       # SignalExpressionVisitorBase (extract + dispatch)
├── _safe_attrs.py                 # C 块 helper
├── literal_visitor.py             # @on StringLiteral, IntegerLiteral, TimeLiteral, ...
├── operator_visitor.py            # @on BinaryOp, UnaryOp, ConditionalOp, ...
├── member_visitor.py              # @on IdentifierName, MemberAccess, ScopedName, ...
├── generate_visitor.py            # @on LoopGenerate, IfGenerate, CaseGenerate, ...
├── class_visitor.py               # @on ClassDeclaration, NewClassExpression, ...
├── constraint_visitor.py          # @on ConstraintBlock, ConditionalConstraint, ...
├── pattern_visitor.py             # @on AssignmentPattern, MultipleConcatenation, ...
└── assignment_visitor.py          # @on ProceduralAssign, ContinuousAssign, ...
```

每个 sub_visitor 是 mixin, 主 class 多继承:
```python
class SignalExpressionVisitor(
    BaseSignalVisitor,           # main dispatch
    LiteralVisitor,              # 30 @on handlers
    OperatorVisitor,             # 80 @on handlers
    MemberVisitor,               # 60 @on handlers
    GenerateVisitor,             # 50 @on handlers
    ClassVisitor,                # 100 @on handlers
    ConstraintVisitor,           # 80 @on handlers
    PatternVisitor,              # 70 @on handlers
    AssignmentVisitor,           # 90 @on handlers
):
    pass
```

### 风险
- 🟡 MED: 大改动, 但 @on 装饰器架构本来就支持
- 测试: 跑 7 unit test 确认 0 regression (主要是 pr4_visualize_l2, cross_module_trace)
- 长期收益: 改 1 个 visitor 不影响其他 6-7 个

---

## 🎯 推荐执行顺序

1. **C. P0 helper 抽取 (2-3 天)** ← 先做
   - 风险 🟢, 立即见效
   - 建立拆分基础
2. **B. DriverExtractor.extract() 拆 method (1-2 周)** ← 中期
   - 风险 🟢, 改善最严重的 long method
   - 提供"如何拆 extract()" 的样板
3. **A. SignalExpressionVisitor 拆分 (2-3 周)** ← 长期
   - 风险 🟡, 改善最大 god class
   - 在 C 跟 B 完成后做, 风险更低

总预计: 4-6 周
