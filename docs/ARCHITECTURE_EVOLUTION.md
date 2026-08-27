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
- **结果**: 839 测试通过

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

### 仍需解决的问题 (实际状态)

| 问题 | 规划 | 实际状态 |
|------|------|----------|
| 遍历策略单一 | 需要 BFS/Selective | ❌ 未实现，仍只有 DFS |
| 遍历逻辑混在 handler | Handler 应只处理业务 | ❌ 未实现 |
| NodeAccessor 缺失 | 封装 pyslang API | ❌ 未实现 |

**当前架构**: Handler 仍混遍历逻辑，但系统运行正常，无紧急需求推动改进。

### 正确的抽象保持不变

- **Signal + Connection** ✓
- **SignalGraph** ✓
- **SignalResult** ✓

### 下一步 (未实施)

> 📝 注 (2026-05-31): 以下改进方向为规划中功能，当前未实施。

1. **TraverseStrategy 抽象** - 支持 DFS/BFS/Selective
2. **NodeAccessor 抽象** - 封装 pyslang API
3. **简化 Handler** - 只处理业务逻辑，不涉及遍历

---

## 七、2026-08-26 case27 架构决策

### 背景

iter_031 + iter_032 调查发现 case27 (`golden_dataflow_27_generate_loop.sv`) 信号图与代码 1:1 不对应, 3 个 gap:

- Gap 1: `acc[i]` 显示 `[i]` 模板 label
- Gap 2: generate-block 内 4 个 `prod[i]` 的 `*` op 节点缺失
- Gap 3: module 顶层 `sum_out` ternary `?:` op 节点缺失

深度架构分析 (T.66, T.83, T.85, T.87) 揭示根因: pyslang API 选型问题 (Syntax vs Semantic vs native).

### 锁定决策 (4 条)

| # | 决策 | 含义 |
|---|------|------|
| **D1** | **坚持 Semantic API** | 不用 Syntax API, 不用混合层 (`PyslangAdapter`), 不用 native API 重构 |
| **D2** | **放弃 generate-block 内部信息** | case27 Gap 1 + Gap 2 接受为设计限制, 不再修 |
| **D3** | **可视化彻底展平** | generate-block 不作为独立 viz 节点, 全部展平到 module 顶层 |
| **D4** | **signal graph 信息完整是核心不变式** | module 顶层所有可见信号必须 100% 在 viz 里 (定义 A/B/C/D 待用户选) |

### 修复方向调整

- ❌ 取消方案 5 (切到 `PyslangAdapter`)
- ❌ 取消方案 2 (`_create_net_decl_edges` 加 generate 递归)
- ❌ 取消方案 4 (PR3 MIG fallback 拓展到 DriverExtractor)
- ❌ 取消方案 3 (pyslang native API 重构)
- ✅ 保留方案 1 (修 `_get_readable_expr` 表达式污染) — 修 Gap 3 症状
- ✅ 新增 iter_033 任务: 修 Gap 3 (顶层 ternary `?:` op 节点) + 写"信息完整"校验测试

### 决策文件

`docs/architecture/case27_signal_graph_completeness_decision.md` — 完整 D1-D4 + 拒绝方案 + 后果清单 + 相关 commits

### 关键引文 (用户 23:00 GMT+8)

> "不，我坚持使用 semantic api 。那么看来使用 semantic api 就无法提取 generate 信息，那就不要了。我们最终可视化就彻底展平。更关键的，我们必须保证 signal graph 的信息完整。"

---

## 八、2026-08-27 pyslang v11-only 决策 (D5)

### 背景

iter_034 启动, 发现 pyslang v11 跟 v10/v9 的 API 差异是 case27 Gap 3 的根因之一:
- `InstanceBodySymbol.members` 在 v11 返回 0 (包装层变化)
- `compilation.topInstances` 是 v11 新增 API
- `portConnections` / `hierarchicalPath` 是 v11 实例属性

继续保留 v9/v10 compat 代码让代码变复杂, 维护成本高, 但 v11 已稳定部署.

### D5 决策

| 项 | 内容 |
|---|---|
| **决策** | 以后仅支持 pyslang v11 API |
| **用户原话** (07:20 GMT+8): | "那我们确定一下版本，以后仅支持 v11 api，之后都不要再考虑v9 和 v10兼容的事情。" |
| **影响** | `_pyslang_compat.py` 整个删除 (git rm, 232 行), 5 个 import 迁到 `pyslang.ast.*` / `pyslang.syntax.*` / `pyslang.parsing.*` / `pyslang.analysis.*`, `is_syntax_list` / `iter_syntax_list` 迁到 `ast_utils.py`, 5 个 [Stage 6] v10/v11 注释清理, `trace/__init__.py` 加 PEP 562 `__getattr__` v11 alias bridge |
| **风险** | 🟢 LOW — 当前 installed pyslang 已是 v11 |
| **状态** | ✅ DONE (2026-08-27, HEAD `62ef835`) — 6 commits, 1470 tests pass, 0 回归 |
| **commit chain** | P1 docs `1b4b573` → P2 imports `88c0f05` → P3 probes `2ce4e09` → P4 compat shim `6199a03` → P5 注释 `0fb950c` (amended) → P6 tests + alias bridge `62ef835` |
| **任务** | iter_034 (见 `docs/task_tree/iterations/iter_034_pyslang_v11_only_cleanup.md`) |

### 关键技术变化

| Symbol 类型 | v10 API | v11 API |
|---|---|---|
| `Compilation` | `pyslang.Compilation` | `pyslang.ast.Compilation` |
| `SyntaxKind` | `pyslang.SyntaxKind` | `pyslang.syntax.SyntaxKind` |
| `SyntaxTree` | `pyslang.SyntaxTree` | `pyslang.syntax.SyntaxTree` |
| `TokenKind` | `pyslang.TokenKind` | `pyslang.parsing.TokenKind` |
| `ValueDriver` | `pyslang.ValueDriver` | `pyslang.analysis.ValueDriver` |
| `NamedValueExpression` | `pyslang.NamedValueExpression` | `pyslang.ast.NamedValueExpression` |
| `RootSymbol.members` | ✓ | ❌ (改用 topInstances) |
| `InstanceBodySymbol.members` | ✓ 直接 | ❌ 返回 0 (新包装) |

---

## 关键引文 (用户 23:00 GMT+8)

> "不，我坚持使用 semantic api 。那么看来使用 semantic api 就无法提取 generate 信息，那就不要了。我们最终可视化就彻底展平。更关键的，我们必须保证 signal graph 的信息完整。"