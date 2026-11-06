# Task: P1 交互式 debug 稳定性（P79）

**状态**: 已完成
**目标**: 3 场景 × 3 模型 × 2 seed；seed1 复用 P0/P74，seed2 新跑。

## seed2 验收

- 3 场景 × 3 模型；
- 隔离 workspace、≥4 轮；
- deep: 12 nodes/11 hops + mux_node/control；
- constraints: c_base+c_packet / both_vars_block=packet.c_packet；
- coverage: cp_addr/cp_len bins/cross/uncovered=[]。

## 边界

- seed1 来自 P0/P74，协议略有差异；
- 不宣称模型排名；
- 只做 T2。
