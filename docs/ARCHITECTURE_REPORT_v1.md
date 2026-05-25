# sv_query 架构报告

**版本**: v1.0.0  
**日期**: 2026-05-25  
**Git**: main@fb9380a  
**状态**: ✅ 839 tests passed

---

## 项目规模

| 指标 | 数值 |
|------|------|
| 源代码文件 | 34 个 |
| 代码行数 | 21,236 行 |
| 代码大小 | 843 KB |
| 测试文件 | 135 个 |
| 文档数量 | 67 个 |

---

## 核心架构

```
┌─────────────────────────────────────────────────────────────┐
│                     unified_tracer.py                        │
│                    (统一入口 API)                            │
└────────────────┬────────────────────────────────────────────┘
                 │
     ┌───────────┼────────────┐
     ▼           ▼            ▼
┌─────────┐ ┌─────────┐ ┌──────────┐
│GraphBuilder│ │SignalTracer│ │ModuleTracer│
│  (图构建)  │ │ (信号追溯) │ │ (模块追踪) │
└────┬─────┘ └────┬────┘ └────┬─────┘
     │            │            │
     ▼            ▼            ▼
┌─────────────────────────────────────┐
│         SignalGraph                  │
│  (nodes: PORT_IN/OUT, SIGNAL,       │
│   INSTANTIATED_MODULE               │
│   edges: DRIVER, CONNECTION)        │
└─────────────────────────────────────┘
```

---

## 源代码结构

### 核心图构建 (SignalGraph 核心)

| 文件 | 状态 | 说明 |
|------|------|------|
| `graph_builder.py` | ✅ ACTIVE | 主图构建器 2431 行，使用 visitor |
| `graph/models.py` | ✅ ACTIVE | NodeKind, EdgeKind, TraceNode |
| `pyslang_adapter.py` | ✅ ACTIVE | Pyslang 适配器 |
| `graph_traversal.py` | ✅ ACTIVE | 图遍历工具 |

### 表达式/信号提取 (Visitor 模式)

| 文件 | 状态 | 说明 |
|------|------|------|
| `visitors/signal_expression_visitor.py` | ✅ ACTIVE | 核心 visitor 7030 行，使用 @on 装饰器 |
| `visitors/base_visitor.py` | ✅ ACTIVE | BaseVisitor 基类 |
| `visitors/signal_result.py` | ✅ ACTIVE | SignalResult 数据类 |
| `visitors/statement_collector_visitor.py` | ✅ ACTIVE | 语句收集 visitor |
| `visitors/assignment_visitor.py` | ⚠️ LEGACY | **未使用，可删除** |
| `visitors/statement_visitor.py` | ⚠️ LEGACY | **未使用，可删除** |
| `visitors/constraint_visitor.py` | ⚠️ LEGACY | 仅 class_graph_builder 使用 |

### 信号查询 (SignalGraph 查询)

| 文件 | 状态 | 说明 |
|------|------|------|
| `query/signal.py` | ✅ ACTIVE | SignalTracer 驱动/负载追溯 |
| `query/load.py` | ✅ ACTIVE | LoadTracer |
| `query/module.py` | ✅ ACTIVE | ModuleTracer |
| `query/clock_domain.py` | ✅ ACTIVE | ClockDomainTracer |

### Builder 工具

| 文件 | 状态 | 说明 |
|------|------|------|
| `builder/expression_builder.py` | ✅ ACTIVE | ExpressionBuilder 表达式节点 |
| `builder/function_expander.py` | ⚠️ PARTIAL | 函数展开器 |

### 类层次结构

| 文件 | 状态 | 说明 |
|------|------|------|
| `class_graph_builder.py` | ⚠️ PARTIAL | 类图构建器 |
| `class_hierarchy.py` | ⚠️ PARTIAL | 类层次结构 |

### 其他核心组件

| 文件 | 状态 | 说明 |
|------|------|------|
| `base.py` | ✅ ACTIVE | 基础架构 2287 行 |
| `bit_select_handler.py` | ✅ ACTIVE | BitSelect 处理器 |
| `compiler.py` | ✅ ACTIVE | 编译器 |
| `semantic_adapter.py` | ✅ ACTIVE | 语义适配器 |
| `data_models.py` | ✅ ACTIVE | 数据模型 |
| `snapshot_manager.py` | ✅ ACTIVE | 快照管理 |
| `module_instance_graph.py` | ✅ ACTIVE | 模块实例图 |

---

## Visitor 模式架构

### SignalExpressionVisitor (核心)

```python
# 使用 @on 装饰器注册 handler
class SignalExpressionVisitor(BaseVisitor):
    _HANDLERS: ClassVar[Dict[str, Callable]] = {}
    
    @on('BinaryOp')
    def handle_binary_op(self, node):
        ...
```

### 委托关系

```
graph_builder.py
    ↓
[铁律29] 委托给 SignalExpressionVisitor
    ↓
_get_signal() → visitor.visit()
_get_all_signals() → visitor.get_all_signals()
```

---

## CLI 命令

| 命令 | 文件 | 功能 |
|------|------|------|
| `trace fanin` | trace.py | 追溯信号驱动源 |
| `trace fanout` | trace.py | 追溯信号负载 |
| `graph` | graph.py | 图导出 |
| `diff` | diff.py | 图比较 |
| `stats` | stats.py | 统计信息 |

---

## LEGACY 代码清单

```
⚠️ 未使用 (可删除):
  - visitors/assignment_visitor.py
  - visitors/statement_visitor.py

⚠️ 部分使用 (需评估):
  - visitors/constraint_visitor.py (仅 class_graph_builder 使用)
  - class_graph_builder.py
  - class_hierarchy.py
  - builder/function_expander.py
```

---

## 已修复的关键问题

1. **PORT_OUT 边界处理** - 不再错误追溯到模块内部
2. **PORT_IN 外部输入识别** - 正确区分外部输入和内部端口别名
3. **SIGNAL 中间线网** - 正确添加到驱动源
4. **跨模块追溯** - 支持实例端口映射的外部驱动源追溯

---

## SignalGraph 节点类型

| NodeKind | 说明 |
|----------|------|
| PORT_IN | 模块输入端口 |
| PORT_OUT | 模块输出端口 |
| SIGNAL | 线网/信号 |
| INSTANTIATED_MODULE | 实例化模块 |
| EXPRESSION | 表达式节点 |
| FUNCTION_CALL | 函数调用节点 |

## SignalGraph 边类型

| EdgeKind | 说明 |
|----------|------|
| DRIVER | 驱动关系 (a -> b, a 驱动 b) |
| CONNECTION | 端口连接 (实例端口映射) |
| BIT_SELECT | 位选择 |
| CLOCK | 时钟关系 |

---

## 关键设计原则

1. **[铁律15]** 必须使用 Visitor 模式，禁止 if-elif 链
2. **[铁律29]** SignalExpressionVisitor 是信号提取的唯一入口
3. **PORT_OUT 是透明驱动映射点** - 自身是驱动终点，不继续追溯内部
4. **PORT_IN 无前驱 = 外部输入** - 正确区分外部输入和内部端口别名