# TODO - sv_query 项目

> 创建时间: 2026-05-24
> 项目路径: /Users/fundou/my_dv_proj/sv_query

---

## 当前状态

### ✅ 已完成: Visitor 架构迁移
- **839 测试通过**，系统稳定运行
- Legacy fallback 已移除 (`_legacy_collect_stmts_with_context` 抛出 NotImplementedError)
- SignalExpressionVisitor: 61 visit methods + 41 get_all methods
- StatementCollectorVisitor: 51 visit methods

---

## 当前任务

### P2 - 中优先级 (可选优化)

#### [ ] SignalExpressionVisitor 单 dispatch 重构
- **类型**: 代码优化 (非功能改进)
- **现状**: 当前是**双接口**设计
  - `visit()` → `Optional[str]` (单信号)
  - `get_all_signals()` → `List[str]` (多信号)
  - 每种节点类型需要两个 handler (如 `visit_binary_expression` + `get_all_binary_expression`)
- **目标**: 改为**单接口**设计
  - `extract()` → `SignalResult(primary, all_signals, all_signals_unique)`
  - 每种节点类型只需一个 handler
  - 通过注册式分派 (@SignalVisitor.on)
- **参考文档**: `docs/ARCHITECTURE_IMPROVEMENT.md`
- **收益**:
  - -50% handler 代码量
  - 消除 visit/get_all 之间别名映射重复
  - 更清晰的 API
- **风险**: 中等 (需迁移 40+ handlers，建议分步进行)
- **触发条件**: 有明确扩展需求时

#### [ ] StatementCollectorVisitor 架构对齐 (可选)
- **类型**: 代码优化
- **现状**: 同样是双接口 (statement collecting + context) 混合设计
- **目标**: 参照 SignalExpressionVisitor 改进方案进行对齐
- **前置条件**: SignalExpressionVisitor 重构完成后再评估

---

### P3 - 长期改进

### ✅ DataFlow 数据流分析 (已完成)
- **状态**: ✅ 已实现 (2026-05-26)
- **文件**: `src/trace/core/graph/dataflow.py`
- **CLI**: `src/cli/commands/dataflow.py`
- **功能**:
  - 路径搜索 (nx.all_simple_paths)
  - BIT_SELECT 边处理 (byte_data[3:0] → byte_data)
  - Struct 成员展开 (pkt1.data → pkt2.data)
  - 时钟域分析
  - 条件判断提取
  - 中间信号收集
- **参考文档**: `docs/DATAFLOW_IMPLEMENTATION_PLAN.md`

#### [ ] ControlFlow 控制流分析架构
- **类型**: 新功能
- **描述**: 实现信号间控制流分析 (条件、分支、状态机)
- **架构**: `docs/CONTROL_FLOW_ANALYSIS.md`
- **核心组件**:
  - `ConditionInfo`: 条件信息 (kind, expr, signals, branches)
  - `ControlFlowResult`: 控制流结果封装
  - `StateTransition`: 状态机转换
  - `ControlFlowAnalyzer`: 主分析器
- **功能**:
  - 条件使能分析 (en 为真/假时数据是否流动)
  - 分支覆盖分析 (if/else/case 是否完整)
  - 状态机状态转换图
  - 控制依赖链传播
- **与 DataFlow 融合**:
  - `DataFlowResult.control_flow`: 融合控制流
  - `data_flow_when`: 数据流成立条件
- **状态**: 提案阶段
- **优先级**: DataFlow 实现完成后
- **参考文档**: `docs/CONTROL_FLOW_ANALYSIS.md`

#### [ ] Visitor 组合模式
- **类型**: 架构探索
- **描述**: 将 Visitor 拆分为可组合的组件 (SignalExtractor / ContextExtractor)
- **前置条件**: P2 重构完成

#### [ ] 类型安全增强
- **类型**: 工具提升
- **描述**: 使用 Protocol 定义节点类型，提升 IDE 自动补全
- **前置条件**: Python 3.8+

---

## 已完成

### ✅ 架构迁移 (2026-05-23)
| 任务 | 描述 |
|------|------|
| Visitor 替代 Legacy | [铁律29] 移除 fallback，Legacy 抛出 NotImplementedError |
| SignalExpressionVisitor 增强 | 覆盖 38/41 ExpressionKind (93%) |
| StatementCollectorVisitor 增强 | 覆盖 30/32 StatementKind (94%) |
| 架构改善提案 | `docs/ARCHITECTURE_IMPROVEMENT.md` |

### ✅ DataFlow/控制流架构设计 (2026-05-24)
| 文档 | 描述 |
|------|------|
| `docs/DATAFLOW_ANALYSIS_ARCHITECTURE.md` | DataFlow 三层架构 + TimingAnalysisResult |
| `docs/CONTROL_FLOW_ANALYSIS.md` | 控制流分析架构 + ConditionInfo + StateTransition |
| `docs/ARCHITECTURE_COMPARISON.md` | 现有架构 vs DataFlow 提案对照 |
| `docs/SCHEMA_COMPARISON.md` | data_models.py vs DataFlow Schema 对照 |
| SignalResult POC | SignalExpressionVisitor.extract() 单 dispatch POC |
| 方案选择建议 | 渐进式迁移: 保持 data_models.py，新增 dataflow_models.py |

---

## 备注

1. **当前系统已可正常工作**，P2 任务为可选优化
2. P2 任务建议在有明确需求时进行 (如支持更多 SV 类型、发现扩展困难)
3. 每次提交前确保 839 测试通过