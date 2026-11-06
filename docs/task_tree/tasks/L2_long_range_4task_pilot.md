# Task: long-range 4-task pilot（P82）

**状态**: 已完成
**目标**: 用 P81 hard runner 跑 4 代表任务 × 2 模型 × 2 臂 × 2 seed = 32 agents。

## 任务

- axi_araddr_neighbors
- serv_clk_path
- pico_adapter_mem_valid_fanout
- pico_adapter_rdata_fanin

## 模型

- MiniMax-M3
- DeepSeek-Flash

## 验收

- 所有 cell 有 rc/parsed/answer；
- exact 分数 + false-confident；
- 429/超时单列；
- 不做模型排名/外推。

## 边界

- 4 题、2 seed，不是 12×3；
- 双评分未做，先 exact + raw answer；
- source/T2 预算 prompt=8，未硬限制。
