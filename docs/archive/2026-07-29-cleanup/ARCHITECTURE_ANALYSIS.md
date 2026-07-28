# sv_query 代码架构分析报告

> 日期: 2026-05-31
> 分析范围: src/trace/

---

## 1. 架构总览

### 1.1 当前目录结构

```
src/trace/
├── unified_tracer.py          # ⭐ 中心入口，788 行
├── core/
│   ├── base.py                # 2318 行 - 超大文件
│   ├── semantic_adapter.py     # 1637 行 - 超大文件
│   ├── graph_builder.py       # 2832 行 - 🔴 最大文件
│   ├── class_graph_builder.py # 1234 行
│   ├── module_instance_graph.py # 1098 行
│   ├── bit_select_handler.py  # 362 行
│   ├── graph_traversal.py     # 182 行
│   ├── compiler.py            # 322 行
│   ├── data_models.py         # 345 行
│   ├── query/                 # ✅ 较好分层
│   │   ├── signal.py          # 487 行
│   │   ├── module.py          # 220 行
│   │   ├── clock_domain.py   # 271 行
│   │   └── load.py            # 120 行
│   ├── graph/
│   │   ├── models.py          # 559 行
│   │   ├── signal_graph_viewer.py # 757 行
│   │   ├── dataflow.py        # 764 行
│   │   ├── analyzer/
│   │   │   ├── timing_analyzer.py
│   │   │   ├── cdc_analyzer.py
│   │   │   └── controlflow_analyzer.py
│   │   ├── diff.py            # 407 行
│   │   └── *.py               # 其他 models
│   ├── builder/               # ✅ 较好分层
│   ├── cache/
│   └── visitors/              # ⚠️ 职责模糊
│       ├── signal_expression_visitor.py  # 最大 visitor
│       ├── assignment_visitor.py
│       ├── statement_visitor.py
│       └── ...
```

### 1.2 文件大小分布（行数）

| 文件 | 行数 | 问题 |
|------|------|------|
| graph_builder.py | 2832 | 🔴 过大，单一职责违反 |
| base.py | 2318 | 🔴 超大文件 |
| semantic_adapter.py | 1637 | 🔴 过大 |
| signal_graph_viewer.py | 757 | 🟡 较大 |
| dataflow.py | 764 | 🟡 较大 |
| class_graph_builder.py | 1234 | 🟡 较大 |
| module_instance_graph.py | 1098 | 🟡 较大 |

**核心问题**: 5 个超大文件（>1000 行），占代码总量 60%+

---

## 2. 核心问题分析

### 2.1 问题 1: 单一巨型入口 (unified_tracer.py)

**现状**:
```python
class UnifiedTracer:
    def __init__(self, sources):
        # 200+ 行初始化逻辑
        self._graph = ...
        self._module_graph = ...
        self._semantic_adapter = ...
        self._signal_tracer = ...

    def trace_fanout(...): pass
    def trace_fanin(...): pass
    def trace_impact(...): pass
    def analyze_cdc(...): pass
    def analyze_timing(...): pass
    # ... 还有 StateMachineAnalyzer, InstanceInfo 等混入
```

**问题**:
- `unified_tracer.py` 788 行，包含了 `StateMachineAnalyzer`、`InstanceInfo` 等多个不相关类
- `UnifiedTracer` 类承担了太多职责（trace / CDC / timing / FSM / instance）
- 没有清晰的层次，调用方（CLI）和核心逻辑耦合

**建议拆分**:
```
unified_tracer.py (改为 facade)
├── trace_service.py      # trace_fanout/fanin
├── impact_service.py     # trace_impact
├── cdc_service.py        # analyze_cdc
├── timing_service.py     # analyze_timing
└── fsm_service.py       # StateMachineAnalyzer
```

---

### 2.2 问题 2: graph_builder.py 职责膨胀 (2832 行)

**现状**:
```python
class GraphBuilder:
    def build(self, sources): ...          # 100+ 行
    def _build_dataflow(self, ...): ...   # 200+ 行
    def _build_controlflow(self, ...): ... # 300+ 行
    def _process_assignment(self, ...): ... # 400+ 行
    def _process_module(self, ...): ...    # 300+ 行
    def _resolve_port_connection(self, ...): ... # 200+ 行
    def _handle_bit_select(self, ...): ... # 200+ 行
    # ... 还有无数 _private 方法
```

**问题**:
- 2832 行，Python 单文件最大建议 500 行
- 职责混杂：数据流构建 + 控制流构建 + 端口连接 + BitSelect 处理
- 没有明显的扩展点，新增功能只能往里堆

**建议拆分**:
```
graph_builder/
├── __init__.py
├── builder.py              # 入口，只负责协调
├── dataflow_builder.py    # 数据流构建
├── controlflow_builder.py # 控制流构建
├── port_resolver.py       # 端口连接解析
├── expression_resolver.py # 表达式解析
└── bit_select_handler.py # 保持独立
```

---

### 2.3 问题 3: semantic_adapter.py 职责不清晰 (1637 行)

**现状**:
```python
class SemanticAdapter:
    def get_type(self, name): ...
    def resolve_symbol(self, name): ...
    def get_module_interface(self, module): ...
    def get_class_methods(self, class_name): ...
    def get_signal_decl(self, signal_id): ...
    # ... 100+ 方法
```

**问题**:
- 语义分析 + 符号解析 + 类型系统 + 接口查询 全搅在一起
- 方法太多（100+），没有分组
- 没有明确的抽象层

**建议拆分**:
```
semantic_adapter/
├── __init__.py
├── type_system.py         # 类型系统
├── symbol_resolver.py     # 符号解析
├── module_interface.py    # 模块接口
└── class_interface.py     # 类接口
```

---

### 2.4 问题 4: visitors/ 职责重叠

**现状**:
```
visitors/
├── signal_expression_visitor.py  # 处理信号表达式
├── assignment_visitor.py          # 处理赋值
├── statement_collector_visitor.py # 处理语句
├── statement_visitor.py           # 处理语句（重复?）
├── base_visitor.py                 # 基类
└── constraint_visitor.py          # 约束处理
```

**问题**:
- `signal_expression_visitor.py` + `assignment_visitor.py` + `statement_visitor.py` 边界模糊
- 很多 visitor 功能重复
- `signal_expression_visitor.py` 可能太大

---

### 2.5 问题 5: query/ 相对较好但可改进

**现状**:
```
query/
├── signal.py   # SignalTracer, DriverChain, SignalChain
├── module.py  # 模块查询
├── load.py    # 负载查询
└── clock_domain.py # CDC 域查询
```

**评价**: 这是项目中分层最好的模块，职责清晰。

**可改进**: 缺少统一的 `QueryEngine` facade

---

## 3. 架构问题总结

### 3.1 问题矩阵

| 问题 | 影响 | 优先级 |
|------|------|--------|
| 巨型单体 `graph_builder.py` (2832行) | 难以维护/测试/扩展 | 🔴 P0 |
| 巨型单体 `semantic_adapter.py` (1637行) | 难以维护/测试 | 🔴 P0 |
| 巨型单体 `base.py` (2318行) | 难以理解 | 🟠 P1 |
| `UnifiedTracer` 职责过多 | 违背单一职责 | 🟠 P1 |
| visitors/ 职责重叠 | 代码重复 | 🟡 P2 |
| `query/` 缺少统一 facade | 使用不便 | 🟡 P2 |

### 3.2 根本原因

1. **快速迭代导致**: 功能堆砌优先，架构重构滞后
2. **缺乏架构设计**: 没有在开始前设计分层
3. **测试覆盖不足**: 没有足够的单元测试保障重构安全
4. **模块化意识弱**: 把相关功能放在同一文件而非同一模块

---

## 4. 建议重构方案

### 4.1 目标架构

```
src/trace/
├── __init__.py
├── api/                          # ✅ 新增：统一 API 层
│   ├── tracer.py                 # Facade，简化入口
│   └── queries.py                # QueryEngine facade
├── services/                     # ✅ 新增：业务服务层
│   ├── impact_service.py
│   ├── cdc_service.py
│   ├── timing_service.py
│   └── verification_service.py
├── core/
│   ├── builders/                 # ✅ 重构：构建器
│   │   ├── dataflow_builder.py
│   │   ├── controlflow_builder.py
│   │   └── port_resolver.py
│   ├── semantic/                 # ✅ 重构：语义层
│   │   ├── type_system.py
│   │   ├── symbol_resolver.py
│   │   └── module_interface.py
│   ├── query/                   # 保留但改进
│   ├── graph/                   # 保留
│   ├── cache/                   # 保留
│   └── visitors/               # 整理
└── utils/                       # ✅ 新增：工具层
    ├── compiler.py
    └── adapters/
```

### 4.2 重构优先级

| 阶段 | 任务 | 工作量 | 收益 |
|------|------|--------|------|
| **Phase 1** | 拆分 `graph_builder.py` | ⭐⭐⭐⭐ | 🔴🔴🔴 |
| **Phase 2** | 拆分 `semantic_adapter.py` | ⭐⭐⭐ | 🔴🔴 |
| **Phase 3** | 整理 `UnifiedTracer` 职责 | ⭐⭐ | 🔴🔴 |
| **Phase 4** | 整理 `visitors/` | ⭐⭐ | 🟡 |
| **Phase 5** | 添加 `api/` facade 层 | ⭐ | 🟡 |

---

## 5. 风险评估

### 5.1 重构风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 破坏现有功能 | 高 | 确保 1080+ 测试全部通过 |
| 耗时过长 | 中 | 分阶段执行，每阶段可回滚 |
| 与 CLI 耦合 | 中 | 只改 core 层，保持 API 兼容 |

### 5.2 不重构风险

| 风险 | 影响 |
|------|------|
| 新功能开发速度下降 | 持续 |
| 代码维护成本上升 | 持续 |
| Bug 修复难度增加 | 持续 |

---

## 6. 附录：代码统计

```
总代码行数: ~17,200 行（不含测试）

核心文件 (>1000 行):
- graph_builder.py: 2832
- base.py: 2318
- semantic_adapter.py: 1637
- class_graph_builder.py: 1234
- module_instance_graph.py: 1098

大型文件 (500-1000 行):
- signal_graph_viewer.py: 757
- dataflow.py: 764
- signal.py (query): 487

平均文件大小: ~350 行
```

---

*分析工具: wc -l + grep + 人工审查*
*日期: 2026-05-31*