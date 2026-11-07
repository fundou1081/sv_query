# Iteration 393: 查询成本归因（P90）

**状态**: ✅
**日期**: 2026-11-07

## 测量

3 个 T2 cell：AXI / SERV / Pico；冷 cache vs warm 重放。

## 结果

- SERV：query 7.4s / wall 61.7s（12%）；模型 residual 54.4s；
- Pico：query 3.1s / wall 23.9s（13%）；residual 20.8s；
- AXI：cold 27.3s；`connections` warm 26.8s；query sum > wall → self-report 不可信。

## 决策

暂停 serve/batch；先修：
1. real tool telemetry；
2. `paths`/`connections` cache/build 路径。
