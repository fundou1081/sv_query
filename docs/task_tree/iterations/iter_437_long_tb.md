# Iteration 437: 长任务回归 + testbench 角

**状态**: ✅
**日期**: 2026-11-09

## 长任务

原 12 direct tasks ×2 模型：24/24 exact。

## Testbench 角

候选 I2C `rcont`：random + constraint + RTL 可答，coverage 不能 elaborate。
UART noise filter/parity 也受 inherited base/coverage 阻塞。

## 决策

testbench 端到端需要 v0.4；先做 P131 covergroup elaboration spike。
