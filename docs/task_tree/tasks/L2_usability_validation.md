# Task: 可用性验证包 — 性能 + 反幻觉 walkthrough（P67）

**状态**: 进行中
**方豆选择 (2026-11-04)**: 先做性能 + 反幻觉 walkthrough；HWE-Bench/VeriBugBench 对照实验延后到环境具备后。

## 交付

- `tools/benchmark/query_perf.py`：可复现查询性能 harness；
- ≥3 个设计（picorv32 / verilog-axi / SERV）冷启动/图内查询延迟 + 峰值内存；
- `examples/anti_hallucination_cdc/`：错误假设、反驳查询、ground truth；
- README + 结果文档；
- 全量回归与机械检查。

## 边界

- 不伪造 benchmark/agent 实验结果；
- 不在本机跑 HWE-Bench（无 Docker/磁盘不足）或 VeriBugBench 全量（无 VCS）；
- 性能数据明确标注机器/版本，不声称跨机器可移植。
