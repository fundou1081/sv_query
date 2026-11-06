# Task: P0 重跑 deep_chain（P78）

**状态**: 已完成
**目标**: 验证 P77 的 port ternary 子图是否让 agent 从 `unknown` 升级为可查询 mux。

## 验收

- 3 模型：MiniMax-M3 / MiniMax-M3.1-Flash / DeepSeek-Flash；
- 1 seed；隔离 workspace（仅 fixture）；
- ≥4 轮 query；
- path 12 节点 / 11 hops；
- mux_control=`top.u_mid.u_stage.sel`；
- mux_node=`top.u_mid.u_stage.u_leaf.d.ternary_sel`；
- combinational=false；
- 至少一条 `controlflow` 或 `graph nodes --kind OP_TERNARY`；
- 不再靠 `search` 从源码恢复 mux。

## 边界

- 只跑 deep_chain，不扩到 3 场景；
- 不宣称模型排名；
- 失败如实记录。
