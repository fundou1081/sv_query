# Interactive P0：post-P77 deep_chain 行为验证

**日期**: 2026-11-06
**状态**: P78.1 完成
**目的**: 验证 P77 的 port ternary 子图是否让 agent 能从 `unknown` 升级为
可查询的 mux 事实，而不只是工具结构测试通过。

---

## 1. 设置

- Fixture: `deep_chain.sv`
- Workspace: `/private/tmp/lr_p0_*`，只放 fixture，无 ground truth；
- 模型：MiniMax-M3 / MiniMax-M3.1-Flash / DeepSeek-Flash；
- T2 only，1 seed；
- prompt 要求至少 4 轮 query；最终 JSON 明确字段。

验收：

| 字段 | 期望 |
|---|---|
| path | 12 节点，含 `...u_leaf.d.ternary_sel` |
| hop_count | 11 |
| register | `top.u_mid.u_stage.u_leaf.q` |
| xor_node | `top.u_mid.u_stage.mixed` |
| mux_control | `top.u_mid.u_stage.sel` |
| mux_node | `top.u_mid.u_stage.u_leaf.d.ternary_sel` |
| combinational | false |

---

## 2. 指标

| 模型 / 运行 | rounds | input tokens | output tokens |
|---|---:|---:|---:|
| MiniMax-M3 / 第一次 | 7 | 291,798 | 6,004 |
| MiniMax-M3 / clarified | 7 | 460,667 | 4,594 |
| MiniMax-M3.1-Flash | 5 | 396,937 | 10,852 |
| DeepSeek-Flash | 8 | 232,619 | 17,374 |

---

## 3. 结果

### MiniMax-M3：第一次未通过，clarify 后通过

第一次 prompt 的字段定义不够明确：

- `combinational` 被理解成“除 register 外其余 hop 是否组合” → 返回 **true**；
- `mux_control` 返回 `sel`，不是 canonical id；
- `xor` 返回表达式，不是 node id。

这是 **prompt contract 问题**，不是 P77 工具问题。  
用明确的字段定义重跑后：

```text
rounds = 7
path = 12 nodes / 11 hops
mux_node = top.u_mid.u_stage.u_leaf.d.ternary_sel
mux_control = top.u_mid.u_stage.sel
combinational = false
```

全部通过。

### MiniMax-M3.1-Flash

```text
rounds = 5
path = 12 nodes / 11 hops
mux_node = ...ternary_sel
mux_control = top.u_mid.u_stage.sel
combinational = false
```

全部通过。

### DeepSeek-Flash

```text
rounds = 8
path = 12 nodes / 11 hops
mux_node = ...ternary_sel
mux_control = top.u_mid.u_stage.sel
combinational = false
```

全部通过。

---

## 4. 关键观察

1. **P77 生效了**：三个模型都能从 `graph nodes --kind OP_TERNARY` /
   `graph edges` / `controlflow` 看到 mux；
2. 不再需要 `search` 从源码恢复 `mux_control`；
3. `paths --canonical` 稳定选择 **12 节点 / 11 hops**，并包含 OP 节点；
4. `controlflow` 返回 `complete`，条件为 `sel` / `!(sel)`；
5. `~d` 仍没有独立节点，只作为 false 分支条件出现在 DRIVER 上；
6. **字段定义必须写死**：`combinational` 的“整条链”语义、`mux_control` 的
   canonical id、`xor_node` 的 node id，都会影响 agent 最终 JSON。

---

## 5. 结论

```text
P77 工具验证: ✅
P0 agent 验证: ✅（clarified prompt 后 3/3）
无 source-only mux 回退: ✅
```

但：

- 只有 1 seed；
- M3 第一次失败说明模型对字段语义仍有歧义；
- 不是模型排名，也不证明真实 bug 修复率。

下一步：

1. 用 clarified prompt 跑 **3 场景 × 3 模型 × 2 seed**；
2. 观察 M3 的 `combinational` 是否稳定；
3. 再评估外部 benchmark / warm service。
