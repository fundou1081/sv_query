# 组合链 (has-a) 设计方案

- 状态: [生效] ✓ 已实现
- 日期: 2026-05-12
- 提出: 方浩
- 审查: 2026-05-12 人工确认通过

---

## 背景

现有 `SignalGraph` 已经支持：
- CLASS_PROPERTY 节点 (变量+类型信息)
- CONSTRAINT_* 节点 (约束)
- extends 继承关系 (ClassHierarchy)

但**组合关系 (has-a)** 尚未支持。

---

## 两种关系的性质对比

| 关系 | 含义 | 示例 | 现有数据位置 |
|------|------|------|-------------|
| **extends** | 继承 is-a | `class req extends packet` | ClassHierarchy._parent_map |
| **has-a** | 组合 contains-a | `class outer { inner my_inner; }` | CLASS_PROPERTY 的 dataType |

### extends (继承) — 适合纯数据层

- 性质：类型层级，元数据
- 用途：is-a 判断、继承链查询
- 现有：ClassHierarchy 独立管理，不进图
- 结论：**继续保持分离**

### has-a (组合) — 应该进图

- 性质：实例成员，具体变量
- 用途：从信号沿组合链向上追容器类
- 示例：
  ```
  signal: outer.my_inner.x
  查询约束时需要知道:
    - x 在 inner 类里
    - inner 是 outer 的成员
  ```

---

## 设计方案

### 1. SignalGraph 新增边类型

```python
# graph_models.py

class EdgeKind(Enum):
    # ... 现有边 ...
    CONSTRAINS = auto()      # class → constraint_block
    HAS_CONDITION = auto()  # constraint → condition var
    HAS_CONSEQUENT = auto() # constraint → consequent var
    
    # 新增
    HAS_MEMBER = auto()      # class → property_node (实例成员)
    INSTANCE_OF = auto()    # property_node → 被引用的类
```

### 2. ClassHierarchy 保持纯净

```python
class ClassHierarchy:
    """只做 extends 查询 API，不涉及 has-a"""
    
    def add_class(self, name: str, extends: Optional[str] = None): ...
    def get_parent(self, class_name: str) -> Optional[str]: ...
    def get_ancestors(self, class_name: str) -> List[str]: ...
    def is_ancestor_of(self, ancestor: str, descendant: str) -> bool: ...
```

下游只用 ClassHierarchy 做 is-a 判断，不处理组合。

### 3. ClassGraphBuilder 扩展

在 `_build_class_nodes` 中，对每个 CLASS_PROPERTY 检查：

```python
# 检测组合关系
type_node = getattr(decl, 'type', None)
if type_node and getattr(type_node, 'kind') == SyntaxKind.NamedType:
    # NamedType 表示引用了另一个类
    # 添加 HAS_MEMBER 边 + INSTANCE_OF 边
    type_name = str(type_node).strip()
    graph.add_trace_edge(TraceEdge(
        src=cls_node_id,
        dst=property_node_id,
        kind=EdgeKind.HAS_MEMBER,
    ))
    graph.add_trace_edge(TraceEdge(
        src=property_node_id,
        dst=type_name,  # 指向类名
        kind=EdgeKind.INSTANCE_OF,
    ))
```

### 4. 组合关系识别逻辑

```python
def _is_class_type_reference(type_node) -> bool:
    """判断 type 是否是类引用 (而非 int, bit 等内建类型)"""
    kind = getattr(type_node, 'kind', None)
    if kind == SyntaxKind.NamedType:
        return True   # 引用另一个类
    if kind in [SyntaxKind.IntType, SyntaxKind.BitType, ...]:
        return False  # 内建类型
    return False
```

注意区分：
- `inner my_inner` → NamedType ✅ 是组合
- `int addr` → IntType ❌ 不是组合
- `bit [7:0] data` → BitType ❌ 不是组合
- `inner array_of_inner[4]` → NamedType + dimensions ✅ 是数组组合

---

## 图结构示例

```
SignalGraph:

  class outer
    └── property: outer.my_inner (类型: inner)
    └── property: outer.y (类型: int)
  
  class inner
    └── property: inner.x (类型: int)

边:
  outer --HAS_MEMBER--> outer.my_inner
  outer.my_inner --INSTANCE_OF--> inner
  inner --HAS_MEMBER--> inner.x
```

---

## 下游查询流程

给定信号 `outer.my_inner.x` 查找约束：

1. **定位信号节点**: `inner.x`
2. **沿 INSTANCE_OF 找到类型类**: `inner`
3. **在 inner 的约束中查找**: 对 `x` 的约束
4. **如果 inner 是组合成员**: 继续沿 HAS_MEMBER 找到 `outer.my_inner`
5. **在 outer 中查找**: 对 `my_inner` 的约束

---

## 需实现清单

| 任务 | 位置 | 优先级 |
|------|------|--------|
| EdgeKind 新增 HAS_MEMBER, INSTANCE_OF | graph_models.py | P0 |
| ClassGraphBuilder 增加组合检测逻辑 | class_graph_builder.py | P0 |
| 测试：单层组合关系 | test_constraint_*.py | P1 |
| 测试：多层嵌套组合 | test_constraint_*.py | P1 |
| 测试：数组类型组合 | test_constraint_*.py | P1 |

---

## 参考 API

```python
# 查询示例
graph.get_edges(kind=EdgeKind.HAS_MEMBER)
graph.get_edges(src=cls_node_id, kind=EdgeKind.HAS_MEMBER)

# 给定成员节点，找它的类引用
for src, dst, edge in graph.edges():
    if edge.kind == EdgeKind.INSTANCE_OF and src == member_node_id:
        return dst  # 类名
```

---

## 备选方案 (已否决)

### 方案B: ClassHierarchy 同时管理 extends + has-a

**否决原因**：
- has-a 涉及具体变量节点，需要和 CLASS_PROPERTY 配合
- 分离管理会导致图遍历逻辑分裂
- 不符合"数据层纯数据，图层纯图"的分离原则
