# Iteration 369: 查询性能 + 反幻觉 walkthrough（PLAN P67）

**Metadata**:
- **Iteration #**: 369
- **Task Tree Level**: L2（PLAN `P67`）
- **Created**: 2026-11-04 GMT+8
- **Author**: 方豆 / AI 助手
- **Outcome**: ✅ 完成；2529 passed

## 🎯 方豆选择

先做性能 + 反幻觉 walkthrough；HWE-Bench/VeriBugBench 对照实验延后。

## 🔧 交付

### 1. 查询性能 harness

`tools/benchmark/query_perf.py`：

- 独立子进程构图 → `build_ms`；
- 图内 `trace_fanin/fanout` → `query_ms`；
- 新进程 `sv_query --no-cache` → `cold_cli_ms`；
- `ru_maxrss` → `peak_rss_mb`；
- 缺语料显式 `skipped`，`ok` 不会因 skipped 假通过。

### 2. 三个设计实测

| 设计 | nodes | build | 图内查询 | cold CLI | peak RSS |
|---|---:|---:|---:|---:|---:|
| picorv32 | 1,842 | 1.83 s | 2–4 ms | 1.98 s | 72 MB |
| verilog-axi | 13,808 | 25.82 s | 5–15 ms | 26.29 s | 169 MB |
| SERV | 4,305 | 3.10 s | 3–9 ms | 3.33 s | 80 MB |

结论：构图主导冷启动；warm query 毫秒级。明确不宣称 cold CLI 秒级。

### 3. 反幻觉 CDC walkthrough

- fixture：`examples/anti_hallucination_cdc/cdc_bug.sv`
- 错误假设：“dst_valid 有两级同步器”
- 反驳：`trace fanin dst_valid` 直接驱动只有 `src_valid`（distance=1）和 const0；
  `trace fanout src_valid` 只负载 `dst_valid`；
- ground truth：line 15 单拍 CDC，无 meta。
- README 顶层加入 5 分钟命令/输出。

### 4. 测试

- `sim/tests/unit/test_query_perf_harness.py`：case/query 结构、缺语料显式 skipped；
- 全量 **2529 passed / 0 failed**。

## ⚠️ 边界

- 单机 macOS 数据，不可跨机移植；
- 未跑 HWE-Bench（无 Docker/200GB）或 VeriBugBench 全量（无 VCS）；
- 性能只测查询，不测多线程/门级；
- walkthrough 只证明结构事实，不替代 CDC 规则/时序/仿真。

## 🔗 相关

- 性能文档: [QUERY_PERF_2026-11-04.md](../../validation/QUERY_PERF_2026-11-04.md)
- walkthrough: [examples/anti_hallucination_cdc/README.md](../../../examples/anti_hallucination_cdc/README.md)
- 计划: [PLAN.md P67](../../../PLAN.md)
