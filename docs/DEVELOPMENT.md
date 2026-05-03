# sv_query 开发规范 (纪律要求)

## 一、四层架构 (铁律)

```
┌─────────────────────────────────────────────────────────────┐
│ Query Layer                                            │
│ 位置: src/trace/unified_tracer.py                        │
│ 职责: 统一入口，分发到具体 Tracer                    │
├─────────────────────────────────────────────────────────────┤
│ Graph Layer                                         │
│ 位置: src/trace/core/graph_models.py                  │
│ 依赖: networkx                                   │
├─────────────────────────────────────────────────────────────┤
│ Builder Layer                                     │
│ 位置: src/trace/core/graph_builder.py             │
│ 职责: 从 Parser 构建 Graph                        │
├─────────────────────────────────────────────────────────────┤
│ Extractor Layer                                   │
│ 位置: src/trace/core/base.py                  │
│ 职责: 从 AST 提取数据                          │
└─────────────────────────────────────────────────────────────┘
```

## 二、禁止行为 (违者必究)

### 2.1 禁止在 Query 层直接操作 Graph

```python
# ❌ 错误: 禁止在 unified_tracer.py 中
def trace_signal(self, signal):
    self._graph.add_node(...)  # 禁止

# ✅ 正确: 通过 Builder
def trace_signal(self, signal):
    self.build_graph()  # 确保已构建
    return self._signal_tracer.trace(signal)
```

### 2.2 禁止在 Tracer 中修改 Graph

```python
# ❌ 错误: 禁止在 query_signal.py 中
class SignalTracer:
    def trace(self, signal):
        self.graph.add_node(...)  # 禁止
        self.graph.add_edge(...)   # 禁止

# ✅ 正确: 只读查询
class SignalTracer:
    def trace(self, signal):
        return SignalChain(
            drivers=self.graph.find_drivers(node_id),
            loads=self.graph.find_loads(node_id)
        )
```

### 2.3 禁止硬编码 Parser

```python
# ❌ 错误: 禁止
if hasattr(parser, 'trees'):
    tree = parser.trees[fname]

# ✅ 正确: 通过适配器
adapter = PyslangAdapter(parser)
modules = adapter.get_modules()
```

### 2.4 禁止创建新 Graph 类

```python
# ❌ 错误: 禁止
class MyGraph(SignalGraph):
    ...

# ✅ 正确: 扩展现有
class MyBuilder(GraphBuilder):
    def build(self):
        graph = super().build()
        # 添加扩展
        return graph
```

### 2.5 禁止修改 networkx 内部

```python
# ❌ 错误: 禁止
graph._node_data[...] = ...  # 禁止直接操作私有属性
```

## 三、文件规则

### 3.1 必须的位置

| 功能 | 文件 |  |
|------|------|------|
| 统一入口 | unified_tracer.py | Query Layer |
| 图模型 | graph_models.py | Graph Layer |
| 构建器 | graph_builder.py | Builder Layer |
| AST遍历 | base.py | Extractor Layer |
| 信号查询 | query_signal.py | 场景A |
| 模块查询 | query_module.py | 场景B |
| 时钟域查询 | query_clock_domain.py | 场景C |

### 3.2 文件命名

```
# ✅ 正确
query_signal.py      # 小写 + 下划线
graph_models.py     # 小写 + 下划线
unified_tracer.py  # 小写 + 下划线

# ❌ 错误
QuerySignal.py     # 大驼峰
signalTracer.py   # 混合
```

### 3.3 目录深度

```
# ✅ 正确
src/trace/unified_tracer.py        # 深度2
src/trace/core/graph_models.py   # 深度3

# ❌ 错误
src/trace/core/xxx/tracer.py    # 深度4
```

## 四、类规则

### 4.1 类名必须

```python
# Query Layer
class UnifiedTracer:  # 唯一入口

# Graph Layer
class SignalGraph:  # 只能有一个
class TraceNode:
class TraceEdge:

# Builder Layer
class GraphBuilder:

# Extractor Layer
class ASTWalker:       # 基类
class DriverCollector:  # 具体实现
class LoadCollector:
class ConnectionCollector:
class ClockDomainCollector:

# Query Layer
class SignalTracer:
class ModuleTracer:
class ClockDomainTracer:
```

### 4.2 方法命名

```python
# ✅ 正确
def trace_signal(self, signal, module=None)
def trace_module(self, module)
def trace_clock_domain(self, clock)

# ❌ 错误
def query(signal)      # 不具体
def get(signal)       # 不具体
def find(signal)      # 不具体
```

## 五、依赖规则

### 5.1 必须的依赖

```
# requirements.txt 必须包含
networkx>=3.0
```

### 5.2 禁止的依赖

```
# ❌ 禁止添加以下任何之一
- igraph     # 禁止替换 networkx
- graphviz   # 禁止
- pygraphviz # 禁止
```

### 5.3 新增依赖

```
# 流程:
1. 在 requirements.txt 添加
2. 在 docs/CHANGELOG.md 记录
3. 说明原因
```

## 六、Git 规则

### 6.1 提交信息格式

```
<type>: <简短描述>

Types:
- feat    : 新功能
- fix     : Bug 修复
- refactor: 重构 (不改变功能)
- docs    : 文档
- test    : 测试
```

### 6.2 分支命名

```
# ✅ 正确
feature/xxx
fix/bug-xxx
refactor/xxx

# ❌ 错误
xxx-feature
my-branch
```

## 七、代码审查检查清单

提交前必须检查:

- [ ] 代码在正确文件？
- [ ] 没有直接操作 Graph？
- [ ] 没有硬编码 Parser？
- [ ] 文件命名正确？
- [ ] 类名符合规范？
- [ ] 方法命名具体？
- [ ] 没有新增禁止的依赖？

---

*更新时间: 2026-05-04*
