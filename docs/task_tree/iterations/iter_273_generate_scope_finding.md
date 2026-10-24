# Iteration 273: generate 局部信号作用域 —— 实测到的缺陷与两种修法

**Metadata**:
- **Iteration #**: 273
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-24 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "先 1 后 2" —— 2 = 收敛 generate 语义）
- **Outcome**: ✅ 调查完成 + 缺陷登记 + xfail 守卫（**修法待拍板**）

## 🎯 目标

决策 D2 说"generate 块内部信息不表示"。本次核实实例级图下这条决策是否成立。

## 🔬 实测（最小 fixture）

```systemverilog
generate for (i = 0; i < 4; i++) begin : G
    logic local_wire;
    assign local_wire = din[i];
    leaf u_leaf(.a(local_wire), .y(dout[i]));
end endgenerate
```

图（`build_graph()`，实例级）：

```
din[0] → local_wire → G[0].u_leaf.a
din[1] → local_wire → G[1].u_leaf.a
din[2] → local_wire → G[2].u_leaf.a
din[3] → local_wire → G[3].u_leaf.a
```

**4 个独立的 `local_wire` 被合并成一个 `top.local_wire` 节点**，于是：

| 查询 | 现状（错） | 应有 |
|---|---|---|
| `drivers G[1].u_leaf.a` | `{top.local_wire}`（背后是 din[0..3] 全部） | `{top.G[1].local_wire}` |
| `loads top.local_wire` | 4 个实例端口 | 只有 G[i] 对应的那一个 |
| 节点 id | `top.local_wire`（不带块路径） | `top.G[1].local_wire` |

## 🧠 根因

`DriverExtractor` 处理 generate 内语句时**只替换 genvar 下标**：

```python
genvar_ctx = adapter.get_genvar_context(assign)   # {'i': 1}
# acc[i+1] → acc[2]  ✅ 下标替换
# local_wire        ❌ 裸名没有任何作用域前缀
```

`local_wire` 是块内**声明**的裸名，不含 genvar，所以保持 `local_wire` →
最终 id `top.local_wire`，4 轮共享。

## 🔀 两种修法

| 方案 | 做法 | 优点 | 代价 |
|---|---|---|---|
| **A（推荐）** | 作用域限定：generate 内语句带上块路径，局部信号命名 `top.G[i].local_wire` | 信息完整、命名与实例级一致、消除假边 | 要改 `get_assignments` 的 scope 传递 + `get_signal` 前缀拼接 + 声明侧命名；约 1 个迭代 |
| B | 按 D2 丢弃 generate 内局部信号（连边一起） | 改动小 | 丢 `din[i] → u_leaf.a` 的真实连通性；generate-heavy 设计（zipcpu/CLA）查询会断链 |

> 现状最糟：**既没按 B 丢弃，也没按 A 限定** —— 信号被表示了，但作用域是错的。
> 这比"不表示"更危险，因为输出看起来像正常结果。

## ✅ 本次产出

1. [`docs/KNOWN_LIMITATIONS.md §3.5`](../../KNOWN_LIMITATIONS.md)：用可观察后果登记该缺陷
   （什么输入 → 什么错误输出 → 两种修法）
2. `sim/tests/unit/test_generate_local_scope.py`：两个 **xfail** 用例锁定**期望行为**
   （`top.G[i].local_wire` 存在 / `G[1].u_leaf.a` 的驱动只有本轮信号）。
   修好后自动转 xpass，届时删 marker。
3. 未改产品代码：修法涉及命名规则变更，按项目纪律先拍板再动手。

## 💡 建议

选 **A（作用域限定）**。理由：

- 与"只认实例路径"的单一命名空间一致（`top.G[1].local_wire` 就是该块内的实例路径作用域）
- generate-heavy 设计（zipcpu 的 idecode、CLA 的 ripple）靠这条连通性才能查通
- 方案 B 会主动删掉真实边，与"信号图信息完整"的核心不变量冲突

## 🔗 相关

- 前序: [iter_272 删除模块定义级路径](iter_272_delete_module_scope_path.md)
- 决策: [case27 架构决策 D2](../../architecture/case27_signal_graph_completeness_decision.md)
