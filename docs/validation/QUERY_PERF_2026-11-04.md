# 查询性能基准（2026-11-04）

> **PLAN**: P67.1
> **脚本**: [tools/benchmark/query_perf.py](../../tools/benchmark/query_perf.py)
> **原始数据**: [query_perf_2026-11-04.json](query_perf_2026-11-04.json)
> **机器**: macOS 26.3.1 / arm64 / Python 3.11.4 / pyslang 11.0.0
> **性质**: 单机实测。绝对值不可跨机器移植；用于复现相对量级与查询/构图拆分。

## 方法

每个设计跑一个独立子进程：

1. `build_graph(use_cache=False)` → `build_ms`；
2. 同一进程内 `trace_fanin` / `trace_fanout` → `query_ms`；
3. 新进程执行 `sv_query trace ... --no-cache` → `cold_cli_ms`；
4. 子进程 `ru_maxrss` → `peak_rss_mb`。

语料来自本机 `~/my_dv_proj/openrtl/`，不修改任何设计文件。

## 结果

| 设计 | 输入 | nodes | build | 图内 fanin | 图内 fanout | cold CLI | peak RSS |
|---|---|---:|---:|---:|---:|---:|---:|
| picorv32 | 单文件 | 1,842 | 1.83 s | 2.1 ms | 4.4 ms | 1.98 s | 72.2 MB |
| verilog-axi | 165 实例 filelist | 13,808 | 25.82 s | 15.0 ms | 5.1 ms | 26.29 s | 169.2 MB |
| SERV | 24 文件 filelist | 4,305 | 3.10 s | 3.2 ms | 8.5 ms | 3.33 s | 80.1 MB |

查询信号：

- picorv32: `picorv32_axi.axi_adapter.mem_rdata[16]` / `picorv32_axi.mem_valid`；
- verilog-axi: `axi_adapter.axi_adapter_rd_inst.m_axi_araddr[0]` / `...m_axi_arvalid`；
- SERV: `serv_rf_top.clk`。

## 解读（不夸大）

- **构图是冷启动成本**：1.8–26.5 s；随后单查询是 **2–15 ms**。
- 对 agent 的真实价值不是“单查询比读文件快”，而是**查询可重复、可反驳、带源码证据**；
  只有多轮 debug 时，构图成本才被摊薄。
- verilog-axi 的 26 s 是当前最大成本；若后续要论证“秒级查询”，必须区分：
  - **warm query**：毫秒级；
  - **cold CLI**：构图主导，不是秒级（大多数设计）。
- 未测并发/多线程；未测门级网表；未测 HWE-Bench/VeriBugBench 故障集。
- 失败/缺语料必须显式 `skipped`，不补零、不伪造。

## 复现

```bash
cd /Users/fundou/my_dv_proj/sv_query
python3 tools/benchmark/query_perf.py \
  --output docs/validation/query_perf_2026-11-04.json --json
```

依赖本机开源语料：`~/my_dv_proj/openrtl/{picorv32,verilog-axi,serv}`。
缺任一语料时该 case 显式为 `skipped`。
