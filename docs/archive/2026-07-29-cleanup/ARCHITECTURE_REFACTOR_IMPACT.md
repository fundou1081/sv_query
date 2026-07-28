# sv_query 代码架构重构影响评估

> 日期: 2026-05-31
> 分析范围: 重构对现有代码的影响

---

## 1. 重构影响总览

### 1.1 UnifiedTracer 依赖分析

**直接依赖 UnifiedTracer 的文件数**: ~90+ 个

| 类别 | 数量 | 文件 |
|------|------|------|
| CLI 命令 | 15 | cdc.py, trace.py, graph.py, visualize.py, ... |
| 测试文件 | 70+ | test_*.py 各类测试 |
| 示例/文档 | 2 | examples/comprehensive_analysis.py |
| 内部模块 | 3 | signal_graph_viewer.py, timing_analyzer.py, cdc_analyzer.py |

**关键发现**:
- CLI 所有命令都通过 `UnifiedTracer` 统一入口
- 没有其他替代入口，重构必须保持 API 兼容
- 测试覆盖 90+，重构风险极高

### 1.2 GraphBuilder 依赖分析

**直接依赖 GraphBuilder 的文件数**: 2 个

| 文件 | 用途 |
|------|------|
| `src/cli/commands/controlflow.py` | CLI 命令 |
| `src/trace/core/graph/analyzer/controlflow_analyzer.py` | 控制流分析器 |

**影响评估**: 🟡 中等
- CLI 层不直接使用 GraphBuilder，通过 UnifiedTracer
- controlflow_analyzer.py 使用较少

### 1.3 SemanticAdapter 依赖分析

**直接依赖 SemanticAdapter 的文件数**: 13+ 个

| 文件 | 用途 |
|------|------|
| `src/trace/core/graph_builder.py` | 核心构建器 |
| `src/cli/commands/controlflow.py` | CLI 命令 |
| `src/cli/commands/expression.py` | CLI 命令 |
| `sim/tests/unit/test_*.py` | 单元测试 |
| `sim/tests/regression/test_controlflow.py` | 回归测试 |

**影响评估**: 🔴 高
- graph_builder.py 强依赖 SemanticAdapter
- 大量测试直接使用 SemanticAdapter 做断言

---

## 2. 核心依赖关系图

```
CLI 层 (15 commands)
    │
    ▼
UnifiedTracer  ◄──────────────────────────────┐
    │                                        │
    ├── GraphBuilder ────────────────────────┤
    │       │                                │
    │       ├── SemanticAdapter ◄────────────┤
    │       │       │                        │
    │       │       └── base.py (Pyslang...) │
    │       │                                │
    │       └── ClassGraphBuilder            │
    │               │                        │
    │               └── SemanticAdapter      │
    │                                        │
    ├── ClassGraphBuilder                    │
    │       │                                │
    │       └── SemanticAdapter              │
    │                                        │
    ├── query/signal.py (SignalTracer)       │
    ├── query/module.py (ModuleTracer)       │
    ├── query/clock_domain.py (ClockTracer)  │
    │                                        │
    └── module_instance_graph.py            │
            │                                │
            └── SemanticAdapter              │
```

**关键结论**:
- `UnifiedTracer` 是唯一入口，所有 CLI 通过它
- `SemanticAdapter` 是核心依赖，被所有组件使用
- `GraphBuilder` 依赖 `SemanticAdapter`

---

## 3. 推荐的渐进式重构策略

### 3.1 策略选择

**选项 A: 大爆炸重构** ❌ 不推荐
- 一次拆分所有组件
- 影响 90+ 文件
- 风险极高，可能破坏现有功能

**选项 B: 渐进式Facade重构** ✅ 推荐
- 保留 `UnifiedTracer` 作为 facade（不改变 API）
- 内部拆分为独立服务
- 逐步拆分，每次改动小，可回滚

---

### 3.2 Phase 1: 拆分 GraphBuilder (最小风险)

**目标**: 将 `graph_builder.py` (2832行) 拆分为多个模块

**前提条件**:
- GraphBuilder 外部依赖少（只有 2 个文件直接引用）
- 通过 UnifiedTracer 间接使用，CLI 无感知

**拆分方案**:

```
core/builders/
├── __init__.py
├── dataflow_builder.py    # 数据流构建 (~800行)
├── controlflow_builder.py # 控制流构建 (~600行)
├── port_resolver.py       # 端口连接 (~400行)
├── expression_builder.py  # 表达式解析 (~400行)
└── builder.py             # 入口，协调器 (~600行)
```

**影响范围**:
```
需修改的文件:
├── src/trace/unified_tracer.py      # 改 import
├── src/trace/core/__init__.py        # 改 export
└── src/trace/core/graph/analyzer/controlflow_analyzer.py  # 改 import

无需修改的文件 (间接通过 UnifiedTracer):
├── src/cli/commands/*.py            # 不用改
└── sim/tests/*.py                   # 不用改
```

**风险**: 🟢 低 (~3 文件需修改)

---

### 3.3 Phase 2: 拆分 SemanticAdapter (中等风险)

**目标**: 将 `semantic_adapter.py` (1637行) 拆分为语义层

**前提条件**:
- 需要 Phase 1 完成
- SemanticAdapter 被 GraphBuilder 和大量测试使用

**拆分方案**:

```
core/semantic/
├── __init__.py
├── type_system.py         # 类型系统 (~400行)
├── symbol_resolver.py     # 符号解析 (~400行)
├── module_interface.py     # 模块接口 (~300行)
├── class_interface.py     # 类接口 (~300行)
└── adapter.py             # 入口，统一包装 (~300行)
```

**影响范围**:
```
需修改的文件 (13+):
├── src/trace/unified_tracer.py
├── src/trace/core/graph_builder.py
├── src/trace/core/class_graph_builder.py
├── src/trace/core/module_instance_graph.py
├── src/trace/core/graph/analyzer/controlflow_analyzer.py
├── src/cli/commands/controlflow.py
├── src/cli/commands/expression.py
└── sim/tests/unit/test_*.py (多个)
```

**风险**: 🟡 中等 (13+ 文件需修改)

**缓解措施**:
- 保持 `SemanticAdapter` 作为 facade，内部调用新模块
- 新模块作为私有实现，外部不可见

---

### 3.4 Phase 3: 整理 UnifiedTracer (低风险)

**目标**: 将 `UnifiedTracer` 内部拆分为独立服务

**拆分方案**:

```
services/
├── __init__.py
├── trace_service.py       # trace_fanout/fanin
├── impact_service.py      # trace_impact
├── cdc_service.py        # CDC 分析
├── timing_service.py     # Timing 分析
└── graph_service.py      # 图管理
```

**注意**: 保持 `UnifiedTracer` facade 不变，只改内部实现

**风险**: 🟢 低 (只改内部实现)

---

## 4. 重构工作量估算

| Phase | 任务 | 文件数 | 工作量 | 风险 |
|-------|------|--------|--------|------|
| 1 | 拆分 GraphBuilder | 3 | ⭐⭐⭐ | 🟢 低 |
| 2 | 拆分 SemanticAdapter | 15+ | ⭐⭐⭐⭐ | 🟡 中 |
| 3 | 整理 UnifiedTracer | 1 | ⭐⭐ | 🟢 低 |
| 4 | 整理 visitors/ | 6 | ⭐⭐ | 🟡 中 |

**总工作量**: ~2-3 周（全職）

---

## 5. 不重构的成本

| 指标 | 当前状态 | 预测（6个月后） |
|------|----------|-----------------|
| 新功能开发速度 | 正常 | 下降 30% |
| Bug 修复时间 | 正常 | 上升 50% |
| 代码理解成本 | 中等 | 高 |
| 测试维护成本 | 中等 | 高 |

---

## 6. 结论与建议

### 6.1 结论

1. **GraphBuilder 拆分风险最低**，应作为重构第一步
2. **SemanticAdapter 拆分需谨慎**，因为测试直接依赖
3. **UnifiedTracer 保持 facade**，不改 API
4. **渐进式重构可行**，每次只改 3-5 文件

### 6.2 建议行动

| 优先级 | 行动 | 理由 |
|--------|------|------|
| 🔴 P0 | **先拆分 GraphBuilder** | 风险低，收益高，锻炼团队 |
| 🟠 P1 | 拆分 SemanticAdapter | 降低核心文件复杂度 |
| 🟡 P2 | 整理 UnifiedTracer | 提升可测试性 |
| 🟢 P3 | 整理 visitors/ | 代码整洁 |

### 6.3 重构前提条件

在开始重构前，确保：
1. ✅ 测试覆盖率 ≥ 95% (当前估计 85%+)
2. ✅ 有 CI/CD 自动化测试
3. ✅ 每次重构后测试全部通过
4. ✅ 有代码 review 流程

---

## 7. 附录：文件依赖详情

### 7.1 UnifiedTracer 直接依赖

```
src/cli/commands/cdc.py
src/cli/commands/trace.py
src/cli/commands/graph.py
src/cli/commands/visualize.py
src/cli/commands/sva.py
src/cli/commands/timing.py
src/cli/commands/stats.py
src/cli/commands/risk.py
src/cli/commands/diff.py
src/cli/commands/verify.py
src/cli/commands/dataflow.py
src/cli/commands/expression.py
src/cli/commands/controlflow.py
src/cli/commands/snapshot.py
src/cli/main.py

sim/tests/integration/test_*.py (40+)
sim/tests/regression/test_*.py (40+)
sim/tests/unit/test_*.py (10+)

examples/comprehensive_analysis.py
docs/openchip_qa_test.py
```

### 7.2 SemanticAdapter 直接依赖

```
src/trace/core/graph_builder.py
src/trace/unified_tracer.py
src/cli/commands/controlflow.py
src/cli/commands/expression.py
sim/tests/unit/test_semantic_adapter.py
sim/tests/unit/test_connection_tracing.py
sim/tests/unit/test_expression_evaluation.py
sim/tests/unit/test_instance_name_extraction.py
sim/tests/unit/test_parameter_extraction.py
sim/tests/unit/test_comment_handling.py
sim/tests/unit/test_width_extraction.py
sim/tests/regression/test_controlflow.py
```

---

*分析工具: grep + wc + 人工审查*
*日期: 2026-05-31*