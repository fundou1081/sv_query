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

## ⚠️ 跨次波动 (2026-09-08 iter_181 实测, 未解决)

同一条命令多次运行, wrapper 基准指标**不稳定**:

| 次 | L1 实例 | L2 nodes | L2 IM | clk fanout |
|---|---|---|---|---|
| 1 | 2 | 2,814 | 271 | 187 |
| 2 | 2 | 1,945 | 207 | 88 |
| 3 | 2 | 1,778 | — | — |
| 4 | 2 | 3,057 | — | — |
| (runs=2 的一次) | **0** | 3,915 | 54 | 0 |
| (某次) | — | — | — | **无输出** (子进程崩溃) |

**根因 (定位到族)**: `filelist` 中的 axi 测试文件含**非 UTF-8 identifier**,
pyslang 属性 getter (`obj.name`) **取值本身抛 `UnicodeDecodeError`** —
命中点随 elaboration 顺序/内存压力变化 → 有的次崩溃 (无输出)、有的次
部分 elaboration (节点数偏少)。已修 2 点 (`native_adapter` walk 的两处
`top.name` → `safe_attr`), 但同类点仍存在 (实测另见 `toplevel[0].name`)。

**关键区分 (教训)**: 这类崩溃必须用 **`safe_attr(obj, "name", default)`**
(getter 级防护);`safe_str(...)` 救不了 — 实参求值即炸。

**系统化修复 (backlog)**: 对 `src/` 中所有 pyslang 符号的 `.name`/`.type`
等属性读取做一次 AST 扫描 + `safe_attr` 包装 (iter_141 同类, 但作用于
**属性 getter** 而非 `str()` 转换)。

**当前对策**: wrapper 结构基准断言取**结构性下限** (nodes ≥800 / IM ≥80 /
clk ≥30 / 深度 ≥10) — 仍能可靠区分"深结构 vs 空壳退化 (168 nodes / clk 0)",
但不作为精确基准; 精确基准需等上述系统化修复。

## 已知限制 (登记, 非静默)

1. **flakiness 阶段对该 wrapper 失败**: flakiness 按整份 filelist 编译 (不带
   `top_modules`) → free-floating type-param 模块报
   `CouldNotResolveHierarchicalPath` (iter_145 同类) → rc≠0。结构基准因此用
   `--skip-flakiness` (结构 ≠ 抖动基准)。
2. **`--runs > 1` 复跑**: iter_181 已修 flakiness 子进程缺 `top_modules` 的
   一致性问题 (与主测量对齐); 残余波动见上节 (根因 = 非 utf8 identifier 属性
   getter 崩溃族), 已登记系统化修复 backlog。
