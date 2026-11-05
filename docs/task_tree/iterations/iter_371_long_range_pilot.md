# Iteration 371: 长程结构查询 4-task pilot（PLAN P69.2/P69.4）

**Metadata**:
- **Iteration #**: 371
- **Task Tree Level**: L2（PLAN `P69`）
- **Created**: 2026-11-05 GMT+8
- **Author**: 方豆 / AI 助手
- **Outcome**: ⚠️ pilot 完成；协议受污染，不外推

## 🎯 动作

用 workflow 启动 16 个 subagent：

- 任务：axi_fanin / serv_fanout / pico_fanout / serv_path；
- 模型：MiniMax-M3 / DeepSeek-Flash；
- 臂：source-only / sv_query；
- 每题 exact canonical ID / path / count；
- 确定性评分脚本。

## 📊 结果

| 模型 / 臂 | exact | high-conf wrong | mean wall |
|---|---:|---:|---:|
| MiniMax-M3 / source | 1/4 | 2/4 | 68.7 s |
| MiniMax-M3 / svq | 4/4 | 0/4 | 28.3 s |
| DeepSeek-Flash / source | 2/4 | 0/4 | 62.6 s |
| DeepSeek-Flash / svq | 3/4 | 0/4 | 21.9 s |

## ⚠️ 有效性威胁（结论前置）

- source 臂未完全隔离：MiniMax 输出引用了 sv_query 源码的 canonical 规则；
- 4 题、单 seed、手工挑选；
- 空输出计错（MiniMax axi/source、DeepSeek pico/svq）；
- 只有 wall time，没有 token；cold/warm 未拆分；
- ground truth 是双来源但非双盲；
- 不能声称“准确率提升 X%”。

## 🔧 产出

- [pilot JSON](../../validation/long_range_pilot_2026-11-05.json)
- [pilot 报告](../../validation/LONG_RANGE_PILOT_2026-11-05.md)
- [评分脚本](../../../tools/benchmark/score_long_range.py)

## 🔜 下一步

P69.3：隔离 source 工作区、扩到 12–15 题、多 seed、token/tool-call 统计，再决定是否扩 30–50。
