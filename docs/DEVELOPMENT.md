# sv_query 开发规范

## 架构原则

### 四层架构 (不可破坏)

```
┌─────────────────────────────────────────────────────────────┐
│  Query Layer (unified_tracer.py)                            │
├─────────────────────────────────────────────────────────────┤
│  Graph Layer (graph_models.py - networkx)                    │
├─────────────────────────────────────────────────────────────┤
│  Builder Layer (graph_builder.py)                       │
├─────────────────────────────────────────────────────────────┤
│  Extractor Layer (base.py + collectors)                    │
└─────────────────────────────────────────────────────────────┘
```

### 约束

1. **禁止在 Query 层直接操作 Graph**
   - ✅ `unified_tracer.py` 统一入口
   - ❌ 禁止在 query_*.py 中直接调用 `graph.add_node()`

2. **Parser 适配通过 base.py**
   - ✅ 使用 `ASTWalker` 基类
   - ✅ 使用 `PyslangAdapter` 接口
   - ❌ 禁止硬编码特定 parser

3. **Graph 依赖 networkx**
   - ✅ 使用 networkx.DiGraph
   - ❌ 禁止替换为其他图库

## 代码规范

### 文件组织

```
src/trace/
├── unified_tracer.py      # Query Layer (唯一入口)
└── core/
    ├── __init__.py      # 导出
    ├── base.py         # ASTWalker + Collectors
    ├── graph_models.py # SignalGraph
    ├── graph_builder.py # Builder
    ├── query_signal.py
    ├── query_module.py
    └── query_clock_domain.py
```

### 命名规则

| 类型 | 前缀 | 示例 |
|------|------|------|
| Query 文件 | query_ | query_signal.py |
| 类 | Tracer/Collector | SignalTracer |
| 方法 | trace_ | trace_signal() |

### 禁止模式

```python
# ❌ 禁止: 直接创建 SignalGraph
graph = SignalGraph()  # 应该在 Builder 中

# ❌ 禁止: 在 Tracer 中添加节点
self.graph.add_node(node)  # 应该通过 Builder

# ❌ 禁止: 硬编码 parser
if isinstance(parser, PyslangParser):  # 使用适配器
```

## 新增功能规范

### 添加新查询场景

1. 在 `query_*.py` 创建 `XXXTracer` 类
2. 在 `unified_tracer.py` 添加 `trace_xxx()` 方法
3. 在 `core/__init__.py` 导出

### 添加新 Collector

1. 继承 `ASTWalker`
2. 在 `base.py` 实现
3. 在 `GraphBuilder` 注册

## Git 提交规范

```
<type>: <description>

Types:
- feat: 新功能
- fix: Bug 修复
- refactor: 重构
- docs: 文档
- test: 测试
```

## 代码审查检查点

- [ ] 是否在四层架构内？
- [ ] 是否有新的外部依赖？
- [ ] 是否在正确文件？
- [ ] 命名是否符合规范？

---

*创建时间: 2026-05-04*
*最后更新: 2026-05-04*
