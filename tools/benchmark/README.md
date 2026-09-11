# sv_query Benchmark

[PR5 2026-06-15] 端到端 benchmark 工具 — 4 维能力数据收集 + 报告

## 用途

跑端到端 benchmark 在真实项目上, 收集 L1 (module 抽取) + L2 (graph) + L3 (trace) + L4 (跨 instance 边) 的数据, 输出 JSON + Markdown 报告.

## 工具

| 文件 | 用途 |
|------|------|
| `run_benchmark.py` | 主入口 — 跑单个项目, 收集 4 维数据 |
| `inputs.py` | [iter_187] **唯一输入构建点** (从 `~/my_dv_proj/openrtl/` 现场生成 filelist) |
| `regen_baselines.py` | [iter_187] 重新生成 baseline + `--check` 漂移检测 |
| `baselines/` | baseline 数据 (PR6 regression check 用) |
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
  --files /Users/fundou/my_dv_proj/openrtl/picorv32/picorv32.v \
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

[iter_187] baseline **必须与当前行为一致**, 否则 `check_regression.py` 会报假
regression。当前可复现的 baseline (全部由 `regen_baselines.py` 生成, flakiness
阶段 `node_stdev = 0.0`):

| baseline | 输入 | target | L1 | nodes | edges | IM |
|---|---|---|---|---|---|---|
| `picorv32.json` | `--files openrtl/picorv32/picorv32.v` | picorv32 | 0 | 438 | 1,096 | 0 |
| `verilog_axi.json` | filelist (`openrtl/verilog-axi/rtl/*.v`) | axi_dp_ram | 6 | 715 | 1,034 | 6 |
| `pr5_wrap.json` | axi+common_cells filelist + 深结构 wrapper | pr5_wrap | 2 | 4,946 | 5,808 | 516 |

**重新生成 / 检测漂移**:

```bash
python3 tools/benchmark/regen_baselines.py            # 全部重生成 (--runs 3)
python3 tools/benchmark/regen_baselines.py picorv32   # 单个
python3 tools/benchmark/regen_baselines.py --check    # 只对比: rc=2 表示检出漂移
```

`pulp_axi_xbar.json` — **不可复现 (历史快照)**: 其 target `axi_xbar_dp_ram` 在
当前 axi 语料里已不存在; 采集于 iter_145 (`top_modules=[target]`) 之前, 那时的
节点数被 free-floating elaboration 虚高。保留作历史, 不要用于 regression check。

> ⚠️ **2026-09-08 iter_187 更正**: 三个 baseline 之前全部与当前行为不符
> (picorv32 708→438, verilog-axi 8,221→715, IM 51→6), 原因是它们采集于
> iter_145 之前 + 长期未重测。已全部重生成, 并由
> `sim/tests/integration/test_benchmark_picorv32.py` 的 "baseline == 活体" 测试锁死。

CI regression check (PR6) 应该 focus 在 L2 数据 (节点数, IM 数), L1/L3/L4 作为辅助参考.

## 关于"结果不稳定" — 真因已修 (iter_185)

[PR1 2026-06-15] 当时观察到 8GB 机器上 benchmark 结果跨次漂移 (nodes 2076~5200,
乱码符号名, L1/L4 有时为 0), 归因于 "内存不足导致 pyslang 静默返回 partial AST",
并加了 `reclaim_memory()` (分配 4GB bytearray) 技巧缓解。

**2026-09-08 iter_185 更正**: 真因是 **`SourceManager` 生命周期 bug** ——
`SVCompiler._do_compile()` 把 `pyslang.SourceManager` 存成局部变量, parse 循环
结束后被 GC → 源文件 buffer 释放 → 符号名/token (指向 buffer 的 `string_view`)
读到垃圾字节。修复后同一输入 3 次**完全一致** (stdev = 0.0), 乱码名归零。
详见 `docs/task_tree/iterations/iter_185_slang_sourcemanager_lifetime.md` 与
`docs/PYSLANG_MEMORY_ISSUE.md`。

`reclaim_memory()` 仍在 `run_benchmark.py` 里 (每次 +3s) — iter_185 后不再必要,
保留与否待定; 它现在的价值仅是降低极端内存压力下的失败率。
