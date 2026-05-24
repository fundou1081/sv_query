# TODO - sv_query 项目

> 创建时间: 2026-05-24
> 项目路径: /Users/fundou/my_dv_proj/sv_query

---

## 当前状态

### ✅ 已完成: Visitor 架构迁移
- **834 测试通过**，系统稳定运行
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

#### [ ] DataFlow 数据流分析架构
- **类型**: 新功能
- **描述**: 实现信号间数据流分析 (from → to)
- **架构**: `docs/DATAFLOW_ANALYSIS_ARCHITECTURE.md`
- **核心组件**:
  - `DataFlowSegment`: 单步驱动 (from → to)
  - `DataFlowPath`: 完整路径
  - `DataFlowResult`: 分析结果封装
  - `DataFlowAnalyzer`: 主分析器
- **算法**:
  - 路径搜索 (networkx.all_simple_paths)
  - 上下文丰富 (condition, timing)
- **优先级**: P2 单 dispatch 重构完成后开始
- **参考文档**: `docs/DATAFLOW_ANALYSIS_ARCHITECTURE.md`

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

---

## 备注

1. **当前系统已可正常工作**，P2 任务为可选优化
2. P2 任务建议在有明确需求时进行 (如支持更多 SV 类型、发现扩展困难)
3. 每次提交前确保 834 测试通过