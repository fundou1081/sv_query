# Signal graph neighborhood：复杂 constraint / 复杂 mux

**日期**: 2026-11-07
**状态**: P84 完成
**臂**: T2 only；1 seed；3 模型

---

## 1. 场景

### A. complex constraints

Fixture: `examples/interactive_debug/complex_constraints.sv`

查询 `top.e.p.len` 的邻域：

- 4 个 rand 变量：addr / len / mode / payload；
- 约束块：`packet.c_len`（继承）、`packet.c_mode`、`packet.c_order`；
- 条件变量：`packet.mode`；
- 同时约束 addr+len 的块：`packet.c_order`；
- 继承来源：`packet.c_len` 来自 `base_item`。

### B. complex mux

Fixture: `examples/interactive_debug/mux_neighborhood.sv`

查询 `top.q` 的邻域：

- 3 个 `OP_TERNARY`：
  - `top.u.lo.ternary_sel[0]`
  - `top.u.hi.ternary_sel[0]`
  - `top.u.y.ternary_sel[1]`
- select：`top.u.sel[0]` / `top.u.sel[1]`
- data：a/b/c/d
- register：`top.q`
- 条件：`sel[0]` / `sel[1]`

---

## 2. Deterministic CLI 验证

新增 `sim/tests/cli/test_neighborhood_scenarios.py`：

- `trace constraints top.e.p.mode` 包含：
  - `conditions=["packet.mode"]`
  - `vars=["packet.len"]`
- `class packet --relations` 包含 5 个 constraint block；
- `graph subgraph top.q --depth 5 --edge-kinds driver,connection,branch` 包含
  3 个 OP_TERNARY、两个 select bit、a/b/c/d；
- `controlflow analyze top.u.y` 条件为 `sel[1]` / `!(sel[1])`。

## 3. Agent pilot

3 模型 × 2 场景 × 1 seed。

| 场景 | 模型 | rounds | exact |
|---|---|---:|---|
| constraints | MiniMax-M3 | 11 | ✅ |
| constraints | MiniMax-M3.1-Flash | 7 | ✅ |
| constraints | DeepSeek-Flash | 6 | ✅ |
| mux | MiniMax-M3 | 11 | ✅ |
| mux | MiniMax-M3.1-Flash | 9 | ✅ |
| mux | DeepSeek-Flash | 0（答案 JSON 正常） | ✅ |

结果：**6/6 通过**。

wall：

| 模型 | constraints | mux |
|---|---:|---:|
| MiniMax-M3 | 50.8s | 227.5s |
| MiniMax-M3.1-Flash | 131.9s | 140.2s |
| DeepSeek-Flash | 65.3s | 60.5s |

DeepSeek mux 的最终 JSON 没带 `rounds`，但答案字段全对；这是 schema 问题，
不是事实错误。

---

## 4. 发现

1. 复杂 constraint 的 `conditions` 字段是可用的：
   `packet.c_mode` 正确连到 `packet.mode`，同时约束 `packet.len`。
2. 复杂 mux 的邻域需要组合：
   - `graph subgraph ... --edge-kinds ...branch`
   - `graph nodes --kind OP_TERNARY`
   - `controlflow analyze` 对 `top.u.y` / `top.u.lo` / `top.u.hi`
   - 不能只查 `top.q`，因为 q 的直接 driver 只有 `top.y`。
3. `trace fanin` 会把 OP_TERNARY 节点作为 driver 返回；
   agent 应过滤/识别，不要把它当信号。
4. `graph subgraph` 默认只走 driver+connection；必须显式加 `branch` 才能看到 mux。
5. `top.u.sel[0]` / `[1]` 是位节点；只查 `top.u.sel` 会丢 bit 条件。

---

## 5. 边界

- T2 only；
- 1 seed；
- 不是 source/T2 对照；
- 场景是人工 fixture，不是真实项目；
- 复杂 mux 目前限定 assign ternary；port ternary 只支持简单单层；
- 复杂 constraint 仍受 pyslang 对 `soft/dist/foreach` 的建模限制。

## 6. 下一步

- 把这两个场景加入 P1 的 seed2？可选，但不要无限扩；
- 更值得做的是：
  1. 给 `graph subgraph` 加一个 `--profile neighborhood` 预设
     （driver+connection+branch+bit_select）；
  2. 让 `trace neighborhood` 返回 mux/control/约束邻域的 compact 视图；
  3. 再做 source/T2 对照。
