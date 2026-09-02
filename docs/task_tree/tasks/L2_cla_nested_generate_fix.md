# L2 CLA 嵌套 generate 实例缺口修复 — 两级实例层级 generate-for (iter_113)

> **创建**: 2026-09-03 GMT+8
> **来源**: openrtl 摸底 (hardware/rtl/cpa/carry_lookahead_adder.sv) 发现:
> `toplevel.u_cla.generators[i].cell4` — generate-for 位于**实例下的实例**层级
> (两级实例嵌套: top → u_cla → generators[i] → cell4) — 信号 0 提取
> (toplevel.cout 无驱动); 实例名 == 类型名时 (`cell4 cell4`) 退化为
> `cell4.generators[0].cell4...` 无限递归假节点。
> **父任务**: openrtl 工业算法摸底 → 缺口修复系列 (iter_109 同型修复的延伸)

---

## 🎯 目标

| sub-task | 验收 |
|---|---|
| 1. 诊断根因 | 对比 iter_109 修好的顶层 generate (cordic.g[i].U) vs 两级嵌套 (top.u_cla.generators[i].cell4) — 枚举/路径在哪个环节断 |
| 2. 修根因 | 两级实例嵌套的 generate-for 实例信号完整进图 (含 inst==type 不再递归) |
| 3. 测试 | unit (两级嵌套复现) + 真实验证 hardware cpa (carry_lookahead 结构可查) |
| 4. 回归 + 文档 | 全量全绿; iter_113 + overview + CURRENT_TODO |

## 🔬 复现事实 (2026-09-03 摸底)

25 行最小复现 (cell4 纯 comb / cla generate-for ×3 / toplevel 实例化 u_cla):
- 实例名 != 类型名 (`cell4 u_cell4`): cell4 相关节点 **0 个**, toplevel.cout 无驱动
- 实例名 == 类型名 (`cell4 cell4`): **18 个递归节点**
  `toplevel.cell4.generators[0].cell4.generators[1].cell4...` (索引 0/1/2 循环)
- 对照 iter_109 修复后 cordic (顶层 generate): `cordic.genblk1[i].U` 正常 — 差异 = generate 所在模块被实例化 (两级)
