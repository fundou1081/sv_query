# Iteration 386: long-range 4-task pilot（P82）

**状态**: ✅ 完成
**日期**: 2026-11-07

## 运行

- 4 题 × 2 模型 × 2 臂 × 2 seed = 32 cells；
- hard-isolated source/T2；
- 全部 rc=0、parsed=true；无 429。

## 结果

- source 11/16；T2 10/16；
- serv_clk_path 8/8；
- axi_araddr 7/8；
- pico_rdata 6/8；
- pico_mem_valid_fanout **0/8**。

## 关键

- 直接 CLI 能返回 pico fanout 6 个 direct loads；
- agent 未用 `--depth 1`，把 terminal/内部 load 当 direct；
- T2 有 4 个 high-confidence 错误（MiniMax）；
- 之前 soft 12 题 T2 12/12 未复现。

## 下一步

修 agent 查询协议，重跑 4 题 1 seed；不要先扩 12×3。
