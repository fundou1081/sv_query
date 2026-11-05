# Iteration 372: 长程结构查询 12-task 对照（PLAN P69.3/P69.4）

**Metadata**:
- **Iteration #**: 372
- **Task Tree Level**: L2（PLAN `P69`）
- **Created**: 2026-11-05 GMT+8
- **Author**: 方豆 / AI 助手
- **Outcome**: ✅ 12 题完成；准确率有信号，成本未降

## 🎯 动作

- 将任务扩到 12 个：
  - AXI 4：fanin/fanout；
  - SERV 4：direct fanout / fanin / path；
  - PicoRV32 4：direct fanout / fanin / 6-load fanout / bit fanin。
- 48 个 agent：2 模型 × 2 臂 × 12 题。
- source 臂：临时移走全局 `sv_query` 二进制，使用 `/tmp/lr_pilot` 源码 copy；
- T2 臂：同一 copy + `sv_query`。
- 评分：`tools/benchmark/score_long_range.py`。

## 📊 结果

| 模型 / 臂 | Exact | High-conf wrong | Mean wall |
|---|---:|---:|---:|
| MiniMax-M3 / source | 7/12 | 2/12 | 51.4 s |
| MiniMax-M3 / svq | 12/12 | 0/12 | 130.6 s |
| DeepSeek-Flash / source | 6/12 | 1/12 | 57.2 s |
| DeepSeek-Flash / svq | 12/12 | 0/12 | 74.9 s |

## 🔍 结论

- sv_query 让两个模型都到 12/12，明显减少 canonical ID/path/fanout 错误；
- 但 T2 的 wall time **没有下降**（MiniMax 130.6 s，DeepSeek 74.9 s）；
  agent 会多做验证/查边，cold build 也计入；
- 首次 T2 的 Pico bit 假失败来自混合 filelist；单文件重跑后两个模型都正确；
- source 臂仍有污染：MiniMax 输出引用了 sv_query 源码的 ID 规则。

## ⚠️ 不能声称

- 准确率提升百分比；
- 成本更低；
- 模型能力排名；
- HWE/VeriBug 修复能力。

## 🔜 下一步

P69.5：token/tool-call 统计、多 seed、真正隔离 source；任务输入污染由复验脚本约束。
