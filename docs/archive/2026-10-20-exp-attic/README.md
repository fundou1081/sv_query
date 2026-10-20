# 归档: exp 创意区（2026-10-20 整体退役）

**来源**: `src/cli/exp/`（4,347 行）+ `src/applications/`（3,724 行）+ 相关测试（30 个文件）
**原因**: 方豆 2026-10-20 — "这些 exp 都是当时想到的创意想法，但没有实际落地，
以后未来逐个再做，现在做好文档，只记录想法、解决问题场景……在现阶段减法可以简洁掉。"

## 里面是什么

| 目录 | 内容 |
|---|---|
| `cli_exp/` | exp 的 24 个命令（bus / verif / struct 三域） |
| `applications/` | 支撑这些命令的库：`bus`（协议识别 / 握手 / 反压 / 结构化信号提取） |
| `tests/` | 这些命令与库的测试（unit / cli / integration / usage） |
| `trace_libs/` | [iter_264] exp 退役后失去唯一调用方的 14 个 trace 库模块：
`coverage_generator`(950) / `uvm_testbench_extractor`(592) / `pattern_matcher`(470) /
`handshake_detector`(456) / `call_graph_builder`(388) / `mig_validator`(326) /
`cdc_analyzer` / `timing_analyzer` / `covergroup_analyzer`(221) / `constraint_visitor`(226) /
`expression_builder`(165) / `stage_inferrer`(105) / `covergroup_binding`(98) /
`cli/core/locate/stats`(273, 与 main.py 内联 stats 重复) |

## 为什么退役而不是保留

这些能力都停在"demo 能跑"的程度：没有真实项目验证、没有锁定的判定语义、
也没有写清失效场景。留在 CLI 里会让使用者误以为可用，而输出可能是错的
——这比没有这个命令更糟。

## 想法去哪了

想法与它要解决的问题场景，记录在 [docs/EXP_IDEAS.md](../../EXP_IDEAS.md)（10 条）。
将来要重做时，**按那份清单重新设计**，不要把这里的代码直接搬回去 ——
它们是第一版探索，不是可复用的实现。

## 还想看代码

`git log --follow` 可追到移动前的历史；本目录保留原相对结构。
测试同步归档在这里，恢复时连同测试一起恢复。
