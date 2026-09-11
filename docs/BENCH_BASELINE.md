# Bench 深结构基准 (BENCH BASELINE)

> **创建**: 2026-09-08 (iter_180, C 路线第二项)
> **背景**: `axi_xbar_intf` 默认参数 `Cfg = '0` → NoSlvPorts/NoMstPorts = 0 →
> **空壳树** (2 实例 / 168 nodes / clk fanout 0), 原结构断言只能弱化
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

## 基准值 (2026-09-08 实测, depth=4, runs=1)

| 层 | 指标 | 空壳 (默认 Cfg) | **wrapper (真实 Cfg)** |
|---|---|---|---|
| L1 | instance_count | 2 | **2** (`pr5_wrap.i_xbar` → axi_xbar_intf; `pr5_wrap.i_xbar.i_xbar` → axi_xbar) |
| L2 | nodes | 168 | **2,814** |
| L2 | edges | — | **3,114** |
| L2 | instantiated_modules | — | **271** |
| L2 | depth_distribution 最大键 | — | **11** (depth 8 处 785 节点) |
| L3 | `pr5_wrap.clk_i` fanout | **0** | **187** ← iter_145 TODO 的链断言恢复 |
| L4 | edge_count / top_ports | 0 / {} | 0 / {} (wrapper 顶层只有 clk/rst, 无 AXI 端口 — 预期) |

断言阈值 (留余量): L1 实例 ≥2 且 defs 含 axi_xbar_intf + axi_xbar;
L2 nodes ≥1,000 / instantiated_modules ≥100 / 最大深度 ≥10;
L3 clk fanout ≥50。

## 已知限制 (登记, 非静默)

1. **flakiness 阶段对该 wrapper 失败**: flakiness 按整份 filelist 编译 (不带
   `top_modules`) → free-floating type-param 模块报
   `CouldNotResolveHierarchicalPath` (iter_145 同类) → rc≠0。结构基准因此用
   `--skip-flakiness` (结构 ≠ 抖动基准)。
2. **`--runs > 1` 复跑结果退化 (新发现, 待专项)**: 同命令 `runs=1` → 2 实例 /
   2,814 nodes / clk 187;`runs=2` → 0 实例 / 3,915 nodes / clk 0。疑同进程内
   二次 build 状态泄漏 (与 iter_164 P2 观察同类但此处可复现)。**benchmark 复跑
   稳定性 = 独立 backlog 项**。
