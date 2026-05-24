# sv_query 架构演进历史

**日期**: 2026-05-24
**目的**: 回顾开发历史，理清每次架构变化解决的问题

---

## 一、架构演进时间线

### 阶段 1：原始 visitor 模式
```
f2efd0a - feat: Task 1 完成 - SignalExpressionVisitor
```
- **问题**: 需要一个专门提取信号的 visitor
- **方案**: 45 个 `visit_` 方法，手动 dispatch
- **缺点**: 命名与 pyslang 不一致

### 阶段 2：SignalResult 引入
```
6a069b5 - feat: add SignalResult + extract() for single-dispatch POC
```
- **问题**: `visit()` 返回 `Optional[str]`，信息不足
- **方案**: 引入 `SignalResult` 统一返回格式
- **改进**: 
  - `primary` - 主信号名
  - `all_signals` - 所有信号列表
  - `kind_name`, `op_name` - 元信息

### 阶段 3：@on handler 单 dispatch
```
b9108f9 - refactor: remove duplicate handlers, keep only first occurrence
dd318c6 - refactor: remove 575 handlers that don't match pyslang SyntaxKind
```
- **问题**: 
  - 有 982 个 handler，但很多与 pyslang 不匹配
  - 命名不一致（Expr vs Expression）
- **方案**: 与 pyslang 1:1 对齐，536 个 handler
- **改进**: 完全对齐 pyslang SyntaxKind

### 阶段 4：handler 完善
```
9e36d5f - feat: add 153 missing handlers for complete pyslang SyntaxKind coverage
028c941 - docs: mark 161 newly added handlers as [NOT IMPLEMENTED]
df024f6 - docs: mark all 536 handlers as [NOT TESTED]
```
- **问题**: 需要 100% 覆盖率
- **方案**: 批量添加 handlers，标记 `[NOT IMPLEMENTED]`
- **改进**: 536 handlers vs 536 SyntaxKind

### 阶段 5：新架构启用
```
5c945fc - feat: enable new dispatch architecture (_dispatch_enabled=True)
79899bb - feat: enable new dispatch architecture
```
- **问题**: 新旧架构并存，需要启用新架构
- **方案**: `_dispatch_enabled=True`
- **结果**: 834 测试通过

### 阶段 6：handler 迁移
```
453f99b - feat: migrate ElementSelectExpression handler
07560c1 - feat: migrate MemberAccessExpression handler
a469990 - feat: migrate IdentifierSelectName handler
```
- **问题**: 部分 handler 需要从 `visit_` 迁移逻辑
- **方案**: 将 `visit_` 逻辑合并到 `@on` handler
- **改进**: Handler 逻辑更完整

### 阶段 7：架构反思（当前）
```
82dc447 - docs: add underlying abstraction analysis
8e4a98f - docs: add Signal + Connection abstraction analysis
```
- **问题**: Handler 混入了遍历逻辑，不灵活
- **方案**: 
  - TraversalStrategy 抽象（DFS/BFS/Selective）
  - NodeAccessor 抽象（pyslang API 封装）
  - Handler 只处理节点，不控制遍历

---

## 二、每次架构变化解决的问题

| 阶段 | 变化 | 解决的问题 | 未解决的问题 |
|------|------|-----------|-------------|
| 1→2 | SignalResult | 返回信息不足 | 遍历逻辑混在 handler |
| 2→3 | @on handler 1:1 对齐 pyslang | 命名不一致、覆盖率不足 | Handler 仍混遍历 |
| 3→4 | 批量添加 handlers | 覆盖率 100% | Handler 是 stub |
| 4→5 | 启用新架构 | 新旧并存 | Handler 遍历逻辑 |
| 5→6 | Handler 迁移 | Handler 逻辑不完整 | 仍需改进 |
| 6→7 | **当前反思** | Handler 遍历不灵活 | 待解决 |

---

## 三、核心问题演进

### 问题 1：Signal 提取 vs Connection 追踪

**原始设计**：
```python
# 一个 visitor 做所有事
visitor.extract(node)  # 返回信号
visitor.get_all_signals(node)  # 返回所有信号
```

**问题**：
- Signal 提取和 Connection 追踪混在一起
- 不同任务需要不同遍历策略

### 问题 2：遍历逻辑和业务逻辑混在一起

**当前问题**：
```python
@on('AssignmentExpression')
def handle_assignment(self, node):
    # 业务逻辑：提取赋值关系
    left = getattr(node, 'left', None)
    right = getattr(node, 'right', None)
    
    # 遍历逻辑：手动递归子节点
    left_result = self.extract(left)
    right_result = self.extract(right)
    
    return left_result.merge(right_result)
```

**期望**：
```python
@on('AssignmentExpression')
def handle_assignment(self, node):
    # 只处理业务逻辑
    left = getattr(node, 'left', None)
    right = getattr(node, 'right', None)
    return ConnectionEdge(source=right, sink=left)
    # 遍历由框架控制
```

### 问题 3：不同任务需要不同遍历策略

| 任务 | 遍历策略 | 需求 |
|------|----------|------|
| 提取所有 port | BFS | 按层级收集 |
| 提取数据流 | DFS | 追踪依赖链 |
| 提取信号 | Selective | 只追踪表达式 |

**当前问题**：只有一种固定遍历方式（DFS）

---

## 四、现有抽象的价值

### Signal + Connection 抽象 ✓

这是 **正确的抽象**，不需要改变：

```
SignalNode (节点) + ConnectionEdge (边) = SignalGraph (图)
```

### 需要改进的是遍历层

**当前**：
```
Handler = 业务逻辑 + 遍历逻辑
```

**改进后**：
```
TraversalStrategy (遍历) + NodeAccessor (访问) + Handler (业务)
```

---

## 五、演进脉络图

```
┌─────────────────────────────────────────────────────────────┐
│  阶段 1: 原始 visitor                                        │
│  45 visit_ 方法，手动 dispatch                               │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  阶段 2: SignalResult                                       │
│  统一返回格式，但遍历逻辑仍在 handler                         │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  阶段 3-4: @on handler 与 pyslang 1:1                       │
│  536 handlers，但大部分是 stub，遍历逻辑混在一起             │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  阶段 5-6: 新架构启用 + handler 迁移                         │
│  新架构工作，但 handler 仍混遍历逻辑                         │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  阶段 7: 架构反思 (当前)                                     │
│  核心问题：遍历逻辑和业务逻辑混在一起                          │
│                                                             │
│  解决方向：                                                  │
│  TraversalStrategy (DFS/BFS/Selective)                     │
│       │                                                     │
│       ▼                                                     │
│  NodeAccessor (pyslang API 封装)                           │
│       │                                                     │
│       ▼                                                     │
│  Handler (只返回 SignalResult/ConnectionEdge)              │
└─────────────────────────────────────────────────────────────┘
```

---

## 六、结论

### 每次变化解决的问题

| 变化 | 解决的问题 |
|------|-----------|
| SignalResult | 返回信息不足 |
| @on handler 1:1 对齐 | 命名不一致、覆盖率不足 |
| 启用新架构 | 新旧架构并存 |
| Handler 迁移 | Handler 逻辑不完整 |

### 仍需解决的问题

1. **遍历策略单一** - 只有 DFS，需要 BFS/Selective
2. **遍历逻辑混在 handler** - Handler 不够简洁
3. **NodeAccessor 缺失** - 直接访问 pyslang，耦合高

### 正确的抽象保持不变

- **Signal + Connection** ✓
- **SignalGraph** ✓
- **SignalResult** ✓

### 下一步

1. **TraverseStrategy 抽象** - 支持 DFS/BFS/Selective
2. **NodeAccessor 抽象** - 封装 pyslang API
3. **简化 Handler** - 只处理业务逻辑，不涉及遍历