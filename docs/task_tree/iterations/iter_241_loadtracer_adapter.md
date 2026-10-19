# Iteration 241: `LoadTracer` 消除第二份遍历实现 (方案 A)

**Metadata**:
- **Iteration #**: 241
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_agent_semantic_capability_gaps.md` (iter_240 登记的缺口 #3)
- **Created**: 2026-10-19 GMT+8
- **Author**: 方豆 / AI 助手 (方豆: "现在做 loadtracer 方案 A 吧，把这个做完")
- **Outcome**: ✅ 成功 (遍历只剩一份; 3 个缺陷全修; 新增 23 条测试)

## 🎯 本次目标

清掉 iter_240 登记在 `KNOWN_LIMITATIONS §3.3` 的第 3 条：

> `LoadTracer` (API `trace_loads`) **完全无跨模块支持** → `trace_loads('sub_adder.sum')` → `[]`

方豆选定**方案 A（消除第二实现）**，否决方案 B（保留双实现、只注入 MIG）与
方案 C（只修假 root）。

## 📊 诊断 (动手前)

登记写的是"完全无跨模块支持"，实测**比登记的更严重**。`inst_demo.sv` 实测：

| 调用 | 旧 `LoadTracer` | `SignalTracer`（`svq loads` 实际路径） |
|---|---|---|
| `sub_adder.sum`（module=None） | `[]`，root = **`'None.sub_adder.sum'`** | `add_out`, `u_adder.sum` |
| `inst_demo.in_a`（module=None） | `[]`，root = `'None.inst_demo.in_a'` | 5 个节点全链 |
| `sub_adder.a`（module=None） | `[]`，root = `'None.sub_adder.a'` | 4 个节点 |

三个缺陷（不是一个）：

| # | 缺陷 | 性质 |
|---|---|---|
| **L1** | `trace()` 自己拼 `f"{module}.{signal}"`，`module=None` → `"None.sig"` | **silent wrong answer**，且**与跨模块无关** —— 不给 module 的单模块查询也错 |
| **L2** | 没有 MIG | 登记在案的那条 |
| **L3** | 不支持 `depth`；`confidence` 词表与 `SignalChain` 不一致；`LoadChain.path` 恒空 | 附带 |

**根因**：`loads` 有两套平行遍历 —— `SignalTracer.trace_fanout`（CLI 走这条，
iter_240 已修好跨模块）与 `LoadTracer`（API 走这条，无人维护）。
`LoadTracer` 是 `GraphTraversal`（177 行基类）**唯一**的子类，而 `svq loads`
根本没用它。

## 🔬 实际结果

### 改法（方案 A）

1. **`SignalTracer._make_id` → 公开 `make_id()`**（5 处内部调用同步改名，删兼容别名）。
   id 解析规则只允许有一份；之前正是两份规则分叉出的 `"None.sig"`。
2. **`query/load.py` 重写为薄适配层**：`LoadTracer(graph, mig=None, use_mig=True)`
   内部持有 `SignalTracer`；`trace()` = 解析 id + 委托 `trace_fanout` + 打包
   `LoadChain`；`get_loads()` 同理返回 id 列表。
   - 删除 `_find_loads` / `_collect_all_loads` / 继承关系 → **不再有第二份遍历**
   - 保留 `LoadChain` 的字段与 `confidence` 词表（`no_load`/`high`/`medium`/`unknown`），
     不破坏既有构造方
   - 新增 `depth` 参数（L3）
3. **删除 `src/trace/core/graph_traversal.py`**（177 行死代码）。
4. **`UnifiedTracer._init_tracers` 传 mig 给 `LoadTracer`**；`trace_loads` 增加 `depth`。
5. 修正两处**引用已删除类 `TraceResult`** 的过期 docstring
   （`driver_extractor.py` / `extractors/function_extractor.py`）—— 参数实际是 duck-typed
   图构建结果。

净效果：**-154 行**（删 177 行基类，`load.py` 127 → 133 行）。

### 修复后实测

| 调用 | 结果 |
|---|---|
| `trace_loads('sub_adder.sum')` | root=`sub_adder.sum`，2 个跨模块节点 ✅ |
| `trace_loads('inst_demo.in_a')` | 5 个节点全链 ✅ |
| `trace_loads(..., depth=1)` | 只有直接后继 ✅ |
| `trace_loads(..., depth=2)` | 两跳，不含最外层 ✅ |
| `LoadTracer(graph, use_mig=False)` | 退化为模块内 ✅ |
| **parity**：`trace_loads` vs `trace_fanout` | 6 组查询**逐节点一致** ✅ |

### 测试

新增 `sim/tests/unit/test_load_tracer_adapter.py`（23 条）：

- **L1**：完整 id + `module=None` 能查出结果；root 不以 `None.` 开头；短名 + `module=None`
  如实报 `unknown` 而非伪造 id；未知信号 `unknown`
- **L2**：跨模块双跳；限定查询不越界；`use_mig=False` 关闭跨模块
- **L3**：`depth=1` 只有直接后继、`depth=2` 两跳、`depth=None` 是全闭包；
  `confidence` 词表保持不变；`get_loads` 去重且直接后继在前
- **结构性回归锁**（核心）：`LoadTracer` 不得再拥有 `_collect_all_loads` /
  `_find_loads` / `_find_by_edge_kind` / `_collect_all_by_edge_kind`；
  `trace.core.graph_traversal` 不得复活；`LoadTracer` 内部必须是 `SignalTracer`

验证：
- 新测试文件 **23 passed**；与既有 `test_query_load.py`(4) +
  `test_cross_module_traversal.py`(11) 合跑 **38 passed**
- 全量 canonical：**3422 passed / 0 failed**（iter_240 基线 3399 → +23，正好等于新增数）
- 预提交检查：`check_docs` ✅ / `check_cli_layers` rc=0 /
  `gen_cli_surface --check` ✅ / `check_except_pass` = 0

### 顺带纠正一处文档漂移

iter_240 的提交信息写了"INDEX (3399/0, 228 份)"，但实际只改了迭代份数，
**canonical 计数行仍停在 iter_226 的 3317**（4 个迭代未同步）。本次改为实测 3422
并在备注里写明这段漂移，避免下一个人以为 3317 是当前值。

## 💡 关键发现 / 决策

1. **"登记的局限"会低估真实缺陷。** 登记写的是"无跨模块支持"，实际 L1 缺陷
   （`"None.sig"`）与跨模块毫无关系 —— 它让**任何不给 module 的调用**静默返回空。
   根因是"登记时只看了跨模块这一个维度"，没做"这个 API 还有哪些输入形态"的枚举。
   教训：登记局限时要按**输入形态**逐个过，而不是按**发现它的那个场景**描述。

2. **副本实现是 bug 的温床，而且只能靠结构性约束治。** 修法不是"把 LoadTracer 的
   逻辑改对"（那仍会有两份），而是**删掉一份**。为了让"再长出一份"立刻可见，
   补了结构性断言（方法不存在 / 模块不存在），而不只是行为断言。

3. **策略：先诊断再动手救了一次。** 若直接按登记描述"给 LoadTracer 注入 MIG"，
   L1 的假 root 缺陷会原样留下 —— 测试只会覆盖"跨模块有结果了"，不会覆盖
   `module=None` 的完整 id 形态。

## 🔗 相关

- 前置: [iter_240](iter_240_cross_module_traversal_fix.md)（登记来源）
- 局限文档: [KNOWN_LIMITATIONS §3.3](../../KNOWN_LIMITATIONS.md)
- 架构: [ARCHITECTURE.md 五、Query API](../../ARCHITECTURE.md)
