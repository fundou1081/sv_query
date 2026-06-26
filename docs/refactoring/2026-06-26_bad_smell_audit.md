# sv_query Bad Smell 报告 (2026-06-26)

## 🔴 1. God Class (严重)

| Class | 行数 | 文件 |
|-------|------|------|
| **SignalExpressionVisitor** | **7312** | visitors/signal_expression_visitor.py |
| PyslangAdapter | 2051 | core/base.py |
| DriverExtractor | 1801 | core/driver_extractor.py |
| SemanticAdapter | 1712 | core/semantic_adapter.py |
| ClassGraphBuilder | 1321 | core/class_graph_builder.py |
| StatementCollectorVisitor | 1306 | visitors/statement_collector_visitor.py |
| ModuleInstanceGraph | 953 | core/module_instance_graph.py |
| SubroutineExpander | 779 | builder/subroutine_expander.py |
| SignalGraphViewer | 784 | graph/signal_graph_viewer.py |
| DataFlowGraph | 697 | graph/dataflow.py |
| SignalTracer | 681 | query/signal.py |
| ControlCoverageGenerator | 648 | core/coverage_generator.py |
| SVAExtractor | 592 | core/sva_extractor.py |
| ProtocolDetector | 599 | applications/bus/detector.py |
| ConstraintVisitor | 544 | visitors/constraint_visitor.py |
| UVMTestbenchExtractor | 503 | core/uvm_testbench_extractor.py |
| SVCompiler | 527 | core/compiler.py |

**总计 18 个 >500 行的 god class**, 严重违反 SRP.

## 🔴 2. Long Method (严重)

| Method | 行数 | 文件 |
|--------|------|------|
| `DriverExtractor.extract()` | **817** | driver_extractor.py |
| `DriverExtractor._handle_invocation()` | **463** | driver_extractor.py |
| `ConnectionExtractor.extract()` | **393** | connection_extractor.py |
| `DataFlowGraph._find_paths()` | **336** | graph/dataflow.py |
| `LoadExtractor._get_signal()` | **286** | load_extractor.py |
| `ClassGraphBuilder._build_constraint_item()` | **257** | class_graph_builder.py |
| `SignalGraphViewer.render_dot()` | **256** | signal_graph_viewer.py |
| `ClassGraphBuilder._build_conditional_constraint()` | **220** | class_graph_builder.py |
| `SignalTracer._trace_drivers_recursive()` | **171** | query/signal.py |
| `ConstraintVisitor._extract_vars_from_expr()` | **163** | constraint_visitor.py |

**40+ method >80 行**, 应该 extract method.

## 🟠 3. Duplication (中等)

### 3a. `str(ident.value).strip()` 模式 (9+ 处)
- `visitors/constraint_visitor.py:158, 172, 393, 398, 432, 439, 480`
- `visitors/signal_expression_visitor.py:5239, 6875`
- `class_graph_builder.py:833`

应抽 `_safe_ident_str(ident)` helper.

### 3b. 7+ 处 try/except (UnicodeDecodeError, RuntimeError) 模式 (我刚加)
- `statement_collector_visitor._extract_clock/_reset/visit_always_ff`
- `class_graph_builder._class_name`
- `signal_expression_visitor.visit_identifier_name` (我加)
- `semantic_adapter._iter_children`
- `bit_select_handler._extract_all_widths/_scan_constraint_bit_selects`
- `unified_tracer._resolve_class_member_access`

应抽 `safe_node_attr(node, attr, default="")` helper.

### 3c. "mutex lock" 字符串硬编码 7+ 处

## 🟠 4. Feature Envy (中等)

- `signal_expression_visitor` 大量访问 `base.py` 跟 `semantic_adapter.py` 内部细节
- `semantic_adapter` 1 个类 1712 行做所有事 (extraction, traversal, formatting)

## 🟡 5. 其他

- **Pass as placeholder**: `uvm_testbench_extractor.py:114,150,174,225,362` 用 `pass` 占位 (smell)
- **Magic numbers**: depth=1/2/3 散在多处, 应该是 enum / constant
- **Dead code?**: 需要进一步 grep `def xxx():` 但未使用

## 📋 改进优先级 (按 ROI 排序)

| 优先级 | 改进 | 预期收益 | 风险 |
|--------|------|---------|------|
| **P0** | 抽 `safe_node_attr()` helper, 替换 7+ 处 try/except | 减 50+ 行, 单一 fix point | 🟢 LOW |
| **P0** | 抽 `_safe_ident_str()` 替换 9+ 处 | 减 30+ 行 | 🟢 LOW |
| **P1** | 拆分 `signal_expression_visitor.py` (7312 行) | 长期可维护性 | 🟡 MED |
| **P1** | `DriverExtractor.extract()` 817 行 extract method | 可读性 | 🟡 MED |
| **P1** | `DriverExtractor._handle_invocation()` 463 行 extract method | 可读性 | 🟡 MED |
| **P2** | 拆 god class (PyslangAdapter 2051 行) | 长期可维护性 | 🔴 HIGH (影响大) |
| **P3** | 删 dead code | 减 noise | 🟢 LOW |

## 🎯 建议本轮聚焦 P0

1. 抽 `src/trace/core/_safe_attrs.py` (新文件) 提供:
   ```python
   def safe_node_attr(node, attr, default=""):
       """pyslang binary garbage safe getattr"""
       try:
           val = getattr(node, attr, default)
       except (RuntimeError, Exception):
           return default
       if val is None:
           return default
       try:
           return str(val).strip() if hasattr(val, '__str__') else default
       except (UnicodeDecodeError, TypeError):
           return default
   ```

2. 替换 7+ 处 try/except 站点

3. 抽 `_safe_ident_str(ident)`:
   ```python
   def safe_ident_str(ident, default=""):
       try:
           val = getattr(ident, "value", default)
           return str(val).strip() if val else default
       except (UnicodeDecodeError, TypeError):
           return default
   ```

4. 跑 7 test 确认 0 regression
