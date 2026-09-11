# Bench 深结构基准 (BENCH BASELINE)

> **创建**: 2026-09-08 (iter_180, C 路线第二项)
> **最近更新**: 2026-09-08 (iter_185 — 真因修复后基准重测, 见下"iter_185 重测")
> **背景**: `axi_xbar_intf` 默认参数 `Cfg = '0` → NoSlvPorts/NoMstPorts = 0 →
> **空壳树** (2 实例 / 168 nodes), 原结构断言只能弱化
> (iter_145 登记的 "wrapper 深度基准 TODO")。本文件记录**真实参数 wrapper**
> 复现的深结构基准。

## 基准 wrapper

`sim/tests/fixtures/bench_wrappers/pr5_wrap.sv` — 用真实 Cfg
(4 slave / 3 master / 32bit addr / 64bit data / PipelineStages 1) 实例化
`axi_xbar_intf`, 顶层只暴露 `clk_i` / `rst_ni`。

复现命令 (axi + common_cells 语料):

```bash
python3 tools/benchmark/run_benchmark.py \
  --filelist /tmp/pulp_axi_xbar_pr2.f --target pr5_wrap \
  --depth 4 --runs 1 --skip-flakiness --output /tmp/bench_pr5_wrap.json
```

> filelist 生成见 `sim/tests/usage/test_benchmark_pr5.py::_ensure_filelist`
> (已自动追加该 wrapper)。

## 基准值 (2026-09-08 iter_185 重测, depth=4)

| 层 | 指标 | 空壳 (默认 Cfg) | **wrapper (真实 Cfg)** |
|---|---|---|---|
| L1 | instance_count | 2 | **2** (`pr5_wrap.i_xbar` → axi_xbar_intf; `pr5_wrap.i_xbar.i_xbar` → axi_xbar) |
| L2 | nodes | 168 | **4,946** |
| L2 | edges | — | **5,808** |
| L2 | instantiated_modules | 2 | **516** |
| L2 | depth_distribution 最大键 | — | **14** |
| L3 | `pr5_wrap.clk_i` fanout | 2 | **445** |
| L4 | edge_count / top_ports | 0 / {} | 0 / {} (wrapper 顶层只有 clk/rst, 无 AXI 端口 — 预期) |

**确定性**: 同一命令连续 3 次 = 完全相同的值 (L1 2 / nodes 4,946 / IM 516 /
深度 14 / clk 445); `--runs 3` 的 flakiness 阶段 **stdev = 0.0**
(nodes 4,946–4,946)。

断言阈值 (`sim/tests/usage/test_benchmark_pr5.py::TestBenchmarkWrapperDepth`,
留 ~20% 余量容忍 pyslang 版本差异): L1 实例 ≥2 且 defs 含 axi_xbar_intf +
axi_xbar; L2 nodes ≥4,000 / IM ≥400 / 最大深度 ≥12; L3 clk fanout ≥300。

## ⚠️ iter_180~184 的"跨次波动" — 真因已定位并修复 (iter_185)

iter_180~184 记录的本语料"跨次波动"表 (保留为历史):

| 次 (iter_181 实测) | L1 实例 | L2 nodes | L2 IM | clk fanout |
|---|---|---|---|---|
| 1 | 2 | 2,814 | 271 | 187 |
| 2 | 2 | 1,945 | 207 | 88 |
| 3 | 2 | 1,778 | — | — |
| 4 | 2 | 3,057 | — | — |
| (runs=2 的一次) | **0** | 3,915 | 54 | 0 |
| (某次) | — | — | — | **无输出** (子进程崩溃) |

**当时的错误归因**: "axi 语料含非 UTF-8 identifier → pyslang 属性 getter
抛 `UnicodeDecodeError` → 部分 elaboration"。**iter_185 证伪**:
- 语料 **0 个**非 UTF-8 文件 (`axi/**/*.sv` + `common_cells/**/*.sv` 全部
  合法 UTF-8, 实测);
- 真因: `SVCompiler._do_compile()` 把 `pyslang.SourceManager` 存成**局部
  变量**, parse 循环结束后被 GC → 源文件 buffer 释放 → 符号名 / token 文本
  (指向 buffer 的 `string_view`) 变垃圾字节;
- 最小复现: 私有 SourceManager 用完即丢 → 所有 top 名 `UnicodeDecodeError`;
  只要多持有一份引用就正常 (见 `docs/task_tree/iterations/iter_185_slang_sourcemanager_lifetime.md`);
- 症状组合 (乱码名 / getter 抛错 / 部分 elaboration / 节点数漂移) 全部由
  **内存复用模式** 决定 → 这正是"跑几次结果都不同"的来源。

修复后 (`src/trace/core/compiler.py` 持有 `self._source_manager`) 本语料
指标见上节, 3/3 一致。

## 已知限制 (登记, 非静默)

1. **flakiness 阶段 (iter_185 起可用)**: iter_181 已给 flakiness 子进程补上
   `top_modules` 后, 该阶段 3 次独立运行 **stdev = 0.0**。结构基准仍用
   `--skip-flakiness` (结构 ≠ 抖动基准), 抖动由
   `--runs 3` 的独立阶段覆盖。
2. **`--runs > 1` 复跑退化 — 已消失**: iter_180 记的 "同进程复跑 L1 2→0 /
   nodes 2814→3915 / clk 187→0" 与 iter_181 的"残余波动"同属
   SourceManager 生命周期问题; iter_185 后不再复现。
3. **`tools/benchmark/run_benchmark.py` 的 `reclaim_memory()` (4GB 分配技巧)**
   是为缓解上述症状而加的经验手段 (见 `docs/PYSLANG_MEMORY_ISSUE.md`)。
   iter_185 后它不再是必要条件 — 是否移除待方豆决定 (每次 +3s)。
