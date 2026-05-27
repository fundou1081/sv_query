# sv_query 待实现功能清单

> 创建时间: 2026-05-26
> 更新日期: 2026-05-26
> 项目路径: /Users/fundou/my_dv_proj/sv_query

---

## 一、已实现功能 ✅

| 功能 | 实现日期 | 参考文档 |
|------|----------|----------|
| Driver/Load 追踪 | 2026-05 | README.md |
| 位选追踪 (BIT_SELECT) | 2026-05 | README.md |
| Class OOP 支持 | 2026-05 | README.md |
| Constraint 追踪 | 2026-05 | README.md |
| DataFlow 路径分析 | 2026-05-26 | DATAFLOW_IMPLEMENTATION_PLAN.md |
| Struct 成员展开 | 2026-05-26 | graph_builder.py |

---

## 二、待实现功能

### 🔴 高优先级

#### 1. ControlFlow 控制流分析

| 项目 | 内容 |
|------|------|
| **类型** | 新功能 |
| **描述** | 实现信号间控制流分析 (条件、分支、状态机) |
| **参考文档** | `docs/CONTROL_FLOW_ANALYSIS.md` |

**核心组件**:

| 组件 | 说明 |
|------|------|
| `ConditionInfo` | 条件信息 (kind, expr, signals, branches) |
| `StateTransition` | 状态机转换 |
| `ControlFlowResult` | 控制流结果封装 |
| `ControlFlowAnalyzer` | 主分析器 |

**功能目标**:
- [ ] 条件使能分析 (en 为真/假时数据是否流动)
- [ ] 分支覆盖分析 (if/else/case 是否完整)
- [ ] 状态机状态转换图
- [ ] 控制依赖链传播

**与 DataFlow 融合**:
- [ ] `DataFlowResult.control_flow`: 融合控制流
- [ ] `data_flow_when`: 数据流成立条件

---

### 🟡 Phase 3 - 高级追踪

#### 2. Generate block 追踪

| 项目 | 内容 |
|------|------|
| **类型** | 新功能 |
| **描述** | 支持 generate if/for/case 块的追踪 |
| **参考文档** | `README.md` Phase 3 |

**现状**: 未实现

---

#### 3. Function/Task 内联展开

| 项目 | 内容 |
|------|------|
| **类型** | 新功能 |
| **描述** | 展开函数体为实际逻辑，替换 FUNCTION_CALL 节点 |
| **参考文档** | `README.md` Phase 3 |

**相关**:
- `docs/archive/P1_EXPRESSION_NODE_TASKS.md` 中 `expand_function()` 设计

**现状**: 未实现

---

#### 4. Interface/modport 追踪

| 项目 | 内容 |
|------|------|
| **类型** | 新功能 |
| **描述** | 支持 SystemVerilog interface 和 modport 的信号追踪 |
| **参考文档** | `README.md` Phase 3 |

**现状**: 未实现

---

#### 5. 跨时钟域路径分析

| 项目 | 内容 |
|------|------|
| **类型** | 新功能 |
| **描述** | 分析信号在不同 clock domain 之间的传播路径 |
| **参考文档** | `README.md` Phase 3 |

**现状**: 部分实现 (DataFlow 中有时钟域分析)，需完善

---

#### 6. Class 内容深度提取与追踪

| 项目 | 内容 |
|------|------|
| **类型** | 功能增强 |
| **优先级** | 🟡 Phase 3 |
| **描述** | 完善 Class 内部属性、方法、继承关系的深度提取和追踪 |
| **参考文档** | `README.md` - Class OOP 支持 |

**现状**: 已有基础支持，需增强以下方面：

| 功能 | 当前状态 | 目标状态 |
|------|----------|----------|
| Class 属性类型解析 | 部分支持 | 支持完整类型推断 |
| 方法覆盖追踪 | 基础支持 | 支持 override 检测 |
| 静态属性追踪 | 未支持 | 支持 static member 追踪 |
| rand/randc 变量追踪 | 未支持 | 支持随机变量标注 |
| constraint 覆盖增强 | 基础 | 支持多重 augmented constraint 展开 |
| 深度继承链追踪 | 浅层 | 支持多层 extends 完整路径 |
| 反射/参数化 Class | 未支持 | 支持 `class #(...)` 参数化类型 |

**核心组件**:
- [ ] `ClassPropertyDeclaration` - 完善属性类型解析
- [ ] `FunctionDeclaration` / `TaskDeclaration` - 方法体展开
- [ ] `VariableDeclarations` - 静态变量支持
- [ ] `RandDeclaration` - rand/randc 变量标注
- [ ] `ConstraintBlock` - 多重 constraint 展开
- [ ] `ExtendsChain` - 继承链完整追踪

**现状**: 待实现

---

### 🟢 Phase 4 - 可视化 & CI

#### 7. Graphviz 可视化导出

| 项目 | 内容 |
|------|------|
| **类型** | 工具功能 |
| **描述** | 将 SignalGraph 导出为 Graphviz DOT 格式 |
| **参考文档** | `README.md` Phase 4 |

**现状**: 未实现

---

#### 8. HTML 报告生成

| 项目 | 内容 |
|------|------|
| **类型** | 工具功能 |
| **描述** | 生成交互式 HTML 报告，展示信号追踪结果 |
| **参考文档** | `README.md` Phase 4 |

**现状**: 未实现

---

#### 9. GitHub Actions CI

| 项目 | 内容 |
|------|------|
| **类型** | DevOps |
| **描述** | 配置 GitHub Actions 进行自动化测试 |
| **参考文档** | `README.md` Phase 4 |

**现状**: 未实现

---

#### 10. 覆盖率分析集成

| 项目 | 内容 |
|------|------|
| **类型** | 工具功能 |
| **描述** | 与代码覆盖率工具集成，分析信号覆盖情况 |
| **参考文档** | `README.md` Phase 4 |

**现状**: 未实现

---

### 🟠 可选优化 (P2/P3)

#### 11. SignalExpressionVisitor 单 dispatch 重构

| 项目 | 内容 |
|------|------|
| **类型** | 代码优化 |
| **优先级** | P2 (可选) |
| **描述** | 从双接口 (`visit()` + `get_all_signals()`) 改为单接口 (`extract()`) |
| **参考文档** | `docs/ARCHITECTURE_IMPROVEMENT.md`, `docs/TODO.md` |

**当前设计**:
```python
# 双接口 - 每种节点类型需要两个 handler
visit() → Optional[str]           # 单信号
get_all_signals() → List[str]      # 多信号
```

**目标设计**:
```python
# 单接口 - 每种节点类型只需一个 handler
extract() → SignalResult(primary, all_signals, all_signals_unique)
```

**收益**:
- -50% handler 代码量
- 消除 visit/get_all 之间别名映射重复
- 更清晰的 API

**风险**: 中等 (需迁移 40+ handlers，建议分步进行)

**现状**: 讨论中，建议在有明确扩展需求时进行

---

#### 12. Visitor 组合模式

| 项目 | 内容 |
|------|------|
| **类型** | 架构探索 |
| **优先级** | P3 |
| **描述** | 将 Visitor 拆分为可组合的组件 (SignalExtractor / ContextExtractor) |
| **参考文档** | `docs/TODO.md` |

**前置条件**: P2 重构完成

**现状**: 提案阶段

---

#### 13. StatementCollectorVisitor 架构对齐

| 项目 | 内容 |
|------|------|
| **类型** | 代码优化 |
| **优先级** | P3 |
| **描述** | 参照 SignalExpressionVisitor 改进方案进行对齐 |
| **参考文档** | `docs/TODO.md` |

**前置条件**: SignalExpressionVisitor 单 dispatch 重构完成

**现状**: 提案阶段

---

#### 14. 类型安全增强

| 项目 | 内容 |
|------|------|
| **类型** | 工具提升 |
| **优先级** | P3 |
| **描述** | 使用 Protocol 定义节点类型，提升 IDE 自动补全 |
| **前置条件** | Python 3.8+ |

**现状**: 提案阶段

---

## 三、按优先级分类

### 优先实现顺序建议

| 顺序 | 功能 | 优先级 | 理由 |
|------|------|--------|------|
| 1 | ~~ControlFlow 控制流分析~~ | ✅ 已完成 | 17 个测试通过 |
| 2 | Interface/modport 追踪 | ✅ 已完成 | 跨模块追踪已支持 |
| 3 | ~~Function/Task 内联展开~~ | ✅ 已完成 | 81 个测试通过 |
| 4 | ~~Generate block 追踪~~ | ✅ 已完成 | 26 个测试通过 |
| 5 | ~~跨时钟域路径分析~~ | ✅ 已完成 | DataFlow 已支持 |
| 6 | ~~Class 实例化成员追踪 (p.addr)~~ | ✅ 已完成 | MEMBER_SELECT + 组合追踪 |
| 7 | bind 语句支持 | 🟡 待实现 | 计划中 |
| 8 | 复杂宏替换 | 🟠 待实现 | 暂不支持 |
| 9-10 | 可视化 & CI | 🟢 Phase 4 | 非核心功能 |

---

## 四、相关文档索引

| 文档 | 说明 |
|------|------|
| `README.md` | 项目整体规划 (Phase 1-4) |
| `docs/TODO.md` | 项目待办清单 |
| `docs/CONTROL_FLOW_ANALYSIS.md` | ControlFlow 架构设计 |
| `docs/DATAFLOW_ANALYSIS_ARCHITECTURE.md` | DataFlow 架构设计 |
| `docs/ARCHITECTURE_IMPROVEMENT.md` | Visitor 重构方案 |
| `docs/archive/P1_EXPRESSION_NODE_TASKS.md` | 表达式节点任务 (已归档) |

---

## 更新日志

| 日期 | 操作 |
|------|------|
| 2026-05-26 | 创建文档，整理待实现功能清单 |