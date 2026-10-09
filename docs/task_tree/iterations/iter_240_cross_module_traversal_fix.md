# Iteration 240: 修 `loads`/`drivers` 的跨模块传递 (D1/D2/D3 三缺陷)

**Metadata**:
- **Iteration #**: 240
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_agent_semantic_capability_gaps.md` (审计发现的查询完整性问题)
- **Created**: 2026-09-09 GMT+8
- **Author**: 方豆 / AI 助手 (方豆: "先搁置 2a。优先处理这个问题")
- **Outcome**: ✅ 成功 (跨模块遍历成为一等机制; 影响面 1 failed → 已按新契约修正; 新增 11 条测试)

## 🎯 背景 (方豆追问触发的审计)

方豆问"**刚才你发现 BFS 有只进不出的问题，已经修复了吗？**" → 我复核确认 `PathResolver` 已修 (iter_237),
但顺着做了**同类缺陷全仓审计**, 发现 `SignalTracer` (`svq loads` / `drivers` / `fanin` / `fanout`) 的
跨模块处理是**兜底补丁**而不是遍历机制, 有三个缺陷:

| # | 缺陷 | 证据 (inst_demo.sv) |
|---|---|---|
| **D1** | MIG 端口映射**只补一条, 不入队** → 不传递 | `loads sub_adder.sum` 到不了 `inst_demo.add_out` |
| **D2** | 兜底**只在图上零结果时**触发 (`if not loads and use_mig`) → 部分结果**抑制**跨模块路径 | 代码 + `loads inst_demo.u_adder.sum` 只给 1 条 |
| **D3** | **`depth=1` 走 `_find_loads`**, 完全不查 MIG → 同一查询不同 depth 答案不一致 | `depth=1` → `[]`, `depth=2/3/None` → 有结果 |

根因: `port path ↔ module-def signal` 是**绑定关系** (同一信号的两个视角), 不是数据边 ——
它不该进 `SignalGraph`(会污染可视化与基准), 但遍历**必须能跨过它**。旧实现把它当"补丁"而非"一步"。

## 🔧 修法 (单点注入, 不动那 8 处边循环)

1. 新增 `SignalTracer._mig_neighbors(signal_id)`: 返回映射**对端** (两个方向: 进模块 + 出模块), 由 `use_mig` 门控, 过滤 binary 名字, MIG 查表异常只记 debug 不中断
2. 注入到**四个入口**:
   - `_trace_loads_recursive` (递归入口, 对端作为本节点的 load 继续往下追)
   - `_trace_drivers_recursive` (递归入口, 对端作为 driver 继续往上追)
   - `_find_loads` (depth=1 路径, 修 D3)
   - `_find_drivers` (depth=1 路径, 对称)
   - 每跳记 **1 层深度** (所以 `max_depth` 语义对跨模块跳同样生效)
3. **删掉两个一次性兜底** (`_collect_all_loads` / `_collect_all_drivers` 里的 `if not ... and use_mig`)
   —— 已被遍历覆盖, 留着就是死代码
4. **过程中我自己踩了一个坑 (如实记录)**: 第一版在递归前把对端 `seen_ids.add(peer.id)`,
   而递归入口也会 add → 递归第一步就 return → **传递性仍然失效**。
   实测发现 (`loads sub_adder.sum` 仍是 1 条) 后改成"不预 add, 由递归入口自己 add"。

## 📊 效果 (inst_demo.sv)

| 查询 | 修复前 | 修复后 |
|---|---|---|
| `loads sub_adder.sum` | `[u_adder.sum]` | `[u_adder.sum, **add_out**]` ← D1 |
| `loads inst_demo.in_a` | `[u_adder.a]` | `[u_adder.a, **sub_adder.a, sub_adder.sum, u_adder.sum, add_out**]` ← D2 |
| `loads sub_adder.sum --depth 1` | `[]` (bug) | `[u_adder.sum]` ← D3 |
| `drivers sub_adder.sum` | `[a, b]` | `[u_adder.sum?, a, u_adder.a, **in_a**, b, u_adder.b, **in_b**]` |
| `loads inst_demo.u_adder.sum` | `[add_out]` | `[sub_adder.sum, add_out]` (超集) |

**作用域**: 以上均为**全局查询**; 加上 `--module M` 后**不跨模块** (只答 M 内, 保护 golden 语义)。

**超集性质**: 旧结果全部保留 (不丢信息), 只是补齐了跨模块链条。

## 📉 影响面 (先评估后动手)

- **方案 A (采纳)**: 遍历层接入映射 —— 改动集中在 `signal.py`, **不改图**
- **方案 B (否决)**: 给 `SignalGraph` 补端口映射边 —— 实测 **+29%~60% 边**
  (inst_demo 20→32 / scheduler 173→223), 会波及基准 baseline / 可视化 / diff / 大量计数断言;
  且"端口↔内部"是**绑定**不是数据流, 画进图里语义上也不对
- **测试影响**: 跑了全部 loads/drivers 相关测试 (130 个文件引用) → **290 passed / 1 failed**
  - 唯一失败 `test_trace_snapshot.py::test_p2_fanout_from_snapshot`: 断言 `--filelist` 与 `--from-snapshot` 计数相等。
    **不是回归**: live 模式有 MIG, snapshot 模式只有图 (快照不含 adapter/MIG) → 现在两者**必然**不同。
    契约改为 `snapshot 结果 ⊆ live 结果` + 注释说明原因

## 🔍 全量门禁抓到的第二个问题: **跨模块遍历越出了用户限定的作用域**

第一次全量: **1 failed / 3398 passed** —— `sim/tests/regression/test_boundary.py::TestBoundaryExtensive::test_parameterized_module`:
```
assertEqual(len(result.drivers), 1) → 4 != 1 : dout = din 参数化模块应有 1 个驱动源 (din)
```

该测试查的是 **`trace_signal('dout', 'top')`** —— 一个**限定了模块**的查询 ("top 模块内 dout 谁驱动")。
我的改动让它跨出了 `top`, 答到 `testbench` 层 (`testbench.u_dut.din` / `testbench.din`)。
**这不是测试过时, 而是我的改动违反了查询语义**: 用户说 "在 top 里看", 就不该越界。

**修法 (第二个设计决策)**: **作用域 = 用户是否指定 `--module`**:
- 全局查询 (`module=None`) → 跨模块 ✓ (这是修 D1/D2/D3 的目标场景)
- 限定查询 (`module='top'`) → **不跨模块**, 只答该模块内 (保护 golden 语义)

实现上踩了两个坑 (如实记录):
1. 只给 `_mig_neighbors` 加了门控不够 —— `trace_signal` / `trace_detailed` / `trace_fanin_detailed`
   这条链上 module 信息会丢 (内部传的是**完整 id**), 必须把 `allow_cross_module` 显式透传;
2. **更隐蔽的坑**: 我给参数加了默认值 `True`, 但 drivers 递归内部 **11 处递归调用没有透传** →
   下一层就退回默认 `True`, 作用域在最深一层失效 (限定查询仍越界)。
   补上全部 11 处透传后才正确 (并加了"是否仍有未透传调用"的自检)。

另外发现 drivers 递归里**既有**一段 P2 时期的"实例端口追溯"跨模块逻辑
(`graph._port_to_internal` 反查, 不经过 `_mig_neighbors`) —— 同样纳入作用域门控;
而"同类型实例间 wrapper passthrough"(iter_132 加了"无内部驱动"守卫) **保留**,
因为它发生在被查设计的实例之间, 不属越界。

**验证**: 限定查询 `trace_signal('dout','top').drivers` = `['top.din']` (1 个, golden 恢复);
全局 `trace_fanin('top.dout')` = 4 条完整链。

## ⚠️ 登记 (不修, 属独立问题)

1. **snapshot 模式无跨模块能力**: 快照只存图, 没有 MIG → `--from-snapshot` 结果 ⊆ live。
   若要两者一致, 需把端口映射写进快照 (快照 schema 变更, 影响 diff/viz) —— 待方豆拍板
2. **`distance` 字段一直是 1**: `signal.py:929` 有 `distance=1,  # TODO: 计算实际距离` (pre-existing)。
   我这次让结果跨 5 跳后该字段更显误导 (全标 1)。修它需要决定 API 形态 (返回副本 vs `(node, depth)` 对),
   且要注意别 mutate 图里共享的 TraceNode —— 单独立项
3. **`LoadTracer` (API `trace_loads`) 完全无跨模块支持** (`trace_loads sub_adder.sum` → `[]`)。
   它只被 `trace.core.__init__` 导出 + `test_query_load.py` 使用, **不是 CLI 路径** → 暂不动

## 📎 产物

- 修改: `src/trace/core/query/signal.py` (新增 `_mig_neighbors` + 四入口注入 + 删两处兜底)
- 新增测试: `sim/tests/unit/test_cross_module_traversal.py` (**11 passed**: 传递性/深度自洽/超集/`use_mig=False`/终止性)
- 测试契约更新: `sim/tests/cli/test_trace_snapshot.py` (snapshot ⊆ live)
- 文档: 本记录 + `CURRENT_TODO.md` + `overview.md` + `INDEX.md`
