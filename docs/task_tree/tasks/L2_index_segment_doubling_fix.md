# L2 索引段加倍假节点修复 — InstanceArray/嵌套 generate 路径二次拼接 (iter_117)

> **创建**: 2026-09-03 GMT+8
> **来源**: iter_116 target 模式摸底重扫 (iter_113/114 洞察驱动) 发现, 多项目真实复现:
> - **aes** Top_PipelinedCipher: 84 个 — `U_SUB.ROM[4].ROM[4]` (实例下 InstanceArray 段重复)
> - **dblclockfft** fftmain/ifftmain: 63 个/模块 — `p3.STAGES.FOR.GENSTAGES[0].GENSTAGES[0].genmpy`
>   (实例下嵌套 generate 段重复)
> 对照: genfor (顶层 gen) / CLA (实例下单层 gen) 正常 → 触发 = 索引段在**已含索引的父路径**
> 下被二次拼接。
> **父任务**: openrtl 摸底 → 缺口修复系列 (iter_109/113 同型路径构建 bug 家族)

---

## 🎯 目标

| sub-task | 验收 |
|---|---|
| 1. 诊断 | 两形态最小复现 (a) top.u_sub.ROM[k] InstanceArray (b) top.u_l.gen 嵌套 → 定位 driver walk / connection 谁二次拼接索引段 |
| 2. 修根因 | 已含索引父路径不再二次拼接 (索引段唯一); 两形态 recursive→0 |
| 3. 测试 | unit 两形态复现 + 真实验证 aes (84→0) / dblclockfft (63→0) |
| 4. 回归 + 文档 | 全量全绿; iter_117 + overview + CURRENT_TODO |

## 🔬 复现事实 (iter_116)

- aes: `Top_PipelinedCipher.U_SUB.ROM[4].ROM[4]` / `...ROM[4].ROM[4].ROM.clk`
  — U_SUB 实例内含 ROM InstanceArray (ROM[0..4]), ROM[4] 段相邻重复
- dblclockfft: `...p3.STAGES.FOR.GENSTAGES[0].GENSTAGES[0].genmpy` — 实例 p3 内
  嵌套 generate (STAGES→FOR→GENSTAGES for-gen), GENSTAGES[0] 段重复一次
- 均非无限递归 (有界加倍): 与 and0 (自环递归) 不同, 是"已含索引父路径 + 索引段
  二次拼接"; 触发层: InstanceArray (aes) 与 generate (dblclockfft) 两类索引载体
