# L1 — 位级 drive/load 精度修复（PLAN P5）

**Status**: 🟡 进行中（P5.1/P5.2/P5.3 完成；P5.4/P5.5 待定）
**Created**: 2026-10-26
**Owner**: 方豆 / AI

## 背景

iter_289 审计（[记录](../iterations/iter_289_bit_precision_audit.md)）实测：
位级映射**局部精确**，但有 3 类反例会误导 agent：

| # | 反例 | 实际 | 期望 |
|---|---|---|---|
| 1 | `assign y[7:4]=a; assign y[3:0]=4'h0;` | `fanin(y[5])={a, 4'b0}` | 不含 4'b0 |
| 2 | `assign y=a; assign y[3]=1'b1;` | `fanin(y[4])={a, 1'b1}` | 不含 1'b1 |
| 3 | `assign s=a&b; assign y=s[3];` | `fanin(y)={s[3]}` | 含 s 的源（a/b） |

## Sub-tasks

| id | 内容 | 验收 |
|---|---|---|
| P5.1 | F1：缺位回退带位索引，父总线 `BIT_SELECT` 只取包含该位的子节点 | ✅ 反例 1/2 消除（iter_290） |
| P5.2 | F2：位节点无 incoming 驱动且父总线有驱动时，补一次父总线追溯 | ✅ 反例 3 消除（iter_290） |
| P5.3 | 测试加强 | ✅ `test_bit_precision.py` 19 个（精确/防污染/防断链/粗粒度契约） |
| P5.4 | F3：slice 节点按位展开 | ✅ LHS/RHS 切片→逐位节点+偏移映射（iter_291）；verilog-axi +1.3% 节点 |
| P5.5 | F4：bus↔无位节点侧合成位桥 | 与 iter_126「不造假节点」冲突，需方豆拍板 |
| P5.6 | F5：load 方向位精度（fanout 按位） | ✅ 切片/寄存器位负载精确 + 无负载位回退父总线（iter_292）；表达式仍粗粒度 |

## 约束

1. **只修正确性**（F1/F2），不改变已文档化的"总线粒度"契约（concat/纯 bus 仍粗）
2. 每个修复必须有**负向测试**（相邻位不得串、不得出现跨位源）
3. 图基线 6 fixture 零差异（图结构不变，只改查询层）
4. 全量门禁 + 真实项目冒烟

## 参考

- 审计: [iter_289](../iterations/iter_289_bit_precision_audit.md)
- 历史契约: `docs/architecture/signal_graph_accuracy_audit.md` A2（iter_126/137/143）
