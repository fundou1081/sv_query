# 方案 A: core/ 目录重组计划

> 记录时间: 2026-05-14

## 目标

将 `src/trace/core/` 拆分为两个子包：
- `core/graph/` — 图数据模型 + 图操作
- `core/query/` — 查询接口

## 重组后的目录结构

```
core/
├── graph/                          ← 新建
│   ├── __init__.py                 ← 新建：导出 models + diff
│   ├── models.py                   ← 从 graph_models.py 重命名
│   └── diff.py                     ← 从 graph_diff.py 重命名
│
├── query/                          ← 新建
│   ├── __init__.py                 ← 新建：导出 4 个 tracer
│   ├── signal.py                   ← 从 query_signal.py 移入
│   ├── load.py                     ← 从 query_load.py 移入
│   ├── module.py                   ← 从 query_module.py 移入
│   └── clock_domain.py             ← 从 query_clock_domain.py 移入
│
├── graph_builder.py                ← 保留（构建逻辑）
├── module_instance_graph.py        ← 保留（MIG）
├── bit_select_handler.py           ← 保留（位选处理）
├── class_graph_builder.py          ← 保留（Class 构建）
├── base.py                         ← 保留（PyslangAdapter）
├── pyslang_adapter.py              ← 保留
├── data_models.py                  ← 保留
├── class_hierarchy.py              ← 保留
├── graph_traversal.py              ← 保留（需更新 import）
├── unified_tracer.py               ← 保留（需更新 import）
├── __init__.py                     ← 更新 export
└── visitors/                       ← 保留（未使用的 visitor 框架）
```

## 需要移动的文件

| 原路径 | 新路径 |
|---|---|
| `core/graph_models.py` | `core/graph/models.py` |
| `core/graph_diff.py` | `core/graph/diff.py` |
| `core/query_signal.py` | `core/query/signal.py` |
| `core/query_load.py` | `core/query/load.py` |
| `core/query_module.py` | `core/query/module.py` |
| `core/query_clock_domain.py` | `core/query/clock_domain.py` |

## 需要新建的文件

| 文件 | 内容 |
|---|---|
| `core/graph/__init__.py` | 导出 `SignalGraph, TraceNode, TraceEdge, NodeKind, EdgeKind, GraphDiff, diff_graph, diff_reachability, forward_reachability` |
| `core/query/__init__.py` | 导出 `SignalTracer, SignalChain, LoadTracer, LoadChain, ModuleTracer, ModuleConnections, ClockDomainTracer, ClockDomainTrace, CrossingRisk` |

## 需要更新的 import 路径

### 内部代码（约 10 处）

| 文件 | 改动 |
|---|---|
| `core/graph_traversal.py` | `from trace.core.graph_models` → `from trace.core.graph.models` |
| `core/query/load.py` | `from trace.core.graph_models` → `from trace.core.graph.models` |
| `core/bit_select_handler.py` | 4 处 `trace.core.graph_models` → `trace.core.graph.models` |
| `core/class_graph_builder.py` | `from .graph_models` → `from .graph.models` |
| `core/unified_tracer.py` | `from .core.query_signal` → `from .core.query.signal` 等 4 处 |
| `core/__init__.py` | 更新所有 export 路径 |

### 测试文件（5 处关键 import）

| 测试文件 | 需改的 import |
|---|---|
| `sim/tests/integration/test_graph_diff.py` | `trace.core.graph_diff` → `trace.core.graph.diff` |
| `sim/tests/unit/test_graph_models.py` | `trace.core.graph_models` → `trace.core.graph.models` |
| `sim/tests/unit/test_query_load.py` | `trace.core.query_load` → `trace.core.query.load` |
| `sim/tests/integration/test_cdc_multiclock.py` | `trace.core.query_clock_domain` → `trace.core.query.clock_domain` |
| `sim/tests/integration/test_port_inout.py` | `trace.core.query_module` → `trace.core.query.module` |
| `sim/tests/integration/test_instance_connection.py` | `trace.core.query_signal` → `trace.core.query.signal` |
| `sim/tests/integration/test_reset_edge.py` | `trace.core.query_clock_domain` → `trace.core.query.clock_domain` |
| `sim/tests/regression/test_constraint_complete.py` | `trace.core.visitors.constraint_visitor`（visitor 路径不变） |

**其他 100+ 测试文件只 import `trace.unified_tracer` 或 `trace`，不受影响。**

### 文档（1 处）

| 文件 | 改动 |
|---|---|
| `EXAMPLES.md` | `trace.core.query_clock_domain` → `trace.core.query.clock_domain` |

## 改动汇总

| 类别 | 数量 |
|---|---|
| 移动文件 | 6 个 |
| 新建 `__init__.py` | 2 个 |
| 测试文件 import 改动 | ~8 处 |
| 内部代码 import 改动 | ~10 处 |
| 文档改动 | 1 处 |
| `core/__init__.py` export 更新 | 1 处 |

## 预计工作量

约 30-45 分钟手动操作，主要是路径替换和测试验证。

## 执行步骤（待补充）

1. 创建 `core/graph/` 和 `core/query/` 目录
2. 移动文件
3. 更新所有 import 路径
4. 更新 `core/__init__.py` export
5. 运行测试确认 251 tests passed
6. Commit