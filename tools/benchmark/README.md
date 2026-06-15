# sv_query Benchmark

[PR5 2026-06-15] 端到端 benchmark 工具 — 4 维能力数据收集 + 报告

## 用途

跑端到端 benchmark 在真实项目上, 收集 L1 (module 抽取) + L2 (graph) + L3 (trace) + L4 (跨 instance 边) 的数据, 输出 JSON + Markdown 报告.

## 工具

| 文件 | 用途 |
|------|------|
| `run_benchmark.py` | 主入口 — 跑单个项目, 收集 4 维数据 |
| `baselines/` | 历史 baseline 数据 (PR6 regression check 用) |
| `check_regression.py` | [PR6] 对比 baseline, fail if regression |

## 用法

### 单项目 (filelist)

```bash
python tools/benchmark/run_benchmark.py \
  --filelist /tmp/pulp_axi_xbar_pr2.f \
  --target axi_xbar_dp_ram \
  --depth 4 \
  --runs 5 \
  --output bench.json \
  --markdown
```

### 单项目 (单文件, [PR7])

```bash
python tools/benchmark/run_benchmark.py \
  --files /Users/fundou/my_dv_proj/picorv32/picorv32.v \
  --target picorv32 \
  --depth 2 \
  --traces picorv32.clk picorv32.resetn \
  --output bench_pico.json
```

### 跳过 flakiness

```bash
python tools/benchmark/run_benchmark.py \
  --files picorv32.v --target picorv32 \
  --skip-flakiness
```

## 输出格式

JSON:
```json
{
  "metadata": {
    "tool": "sv_query benchmark",
    "version": "PR5+PR7 2026-06-15",
    "input_type": "files",
    "project_input": "/path/to/file.v",
    "target": "picorv32",
    "depth": 2,
    "build_time_seconds": 0.64
  },
  "L1_module_extraction": {"instance_count": 0, ...},
  "L2_graph_topology": {"nodes": 527, "edges": 1199, "instantiated_modules": 2, ...},
  "L3_signal_traces": {
    "picorv32.clk": {"fanin": 0, "fanout": 1},
    "picorv32.resetn": {"fanin": 0, "fanout": 11},
    "picorv32.mem_busy": {"fanin": 10, "fanout": 0}
  },
  "L4_cross_instance_edges": {"edge_count": 0, ...},
  "flakiness": {
    "runs": 3, "node_counts": [...], "im_counts": [...],
    "node_min": 512, "node_max": 527, "node_stdev": 8.4,
    "im_min": 2, "im_max": 2, "deterministic_ratio_im": 1.0
  }
}
```

## Baseline

`baselines/` 目录有 2 个已知 baseline:
- `picorv32.json` — 稳定, 用于 regression check
- `pulp_axi_xbar.json` — 注意: L1/L4 在内存压力下可能为 0 (pyslang elaboration partial failure)

CI regression check (PR6) 应该 focus 在 L2 数据 (节点数, IM 数), L1/L3/L4 作为辅助参考.

## 内存警告

[PR1 2026-06-15] 8GB MacBook Air 上 pyslang elaboration 在内存不足时会静默返回 partial AST.

**修复** (PR1 用户提出):
```bash
python3 -c "import time; a=bytearray(4*1024**3); time.sleep(3); del a"
```

`run_benchmark.py` 跑前自动执行这个 trick. 但连续跑多次 benchmark 时, 内存会再次填满, 需要重复执行.
