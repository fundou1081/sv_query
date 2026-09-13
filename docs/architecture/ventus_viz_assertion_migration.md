# 待决: Ventus viz 断言从 DOT 语义迁移到当前输出 (13 个 skip)

| 字段 | 内容 |
|---|---|
| **时间** | 2026-09-08 GMT+8 (iter_195) |
| **状态** | 🟡 **待方豆拍板** (本文件只做"决策就绪"整理, 未改任何断言) |
| **触发** | iter_188 把 14 failed 转成 0 failed + 13 个明确 skip; 这些 skip 的前提是断言基于 V100 之前的 DOT 输出 |

## 背景

`src/cli/commands/visualize.py:192` 起 `--svg` / `--dot` 是同一选项且**输出 SVG**
("was DOT before V100"), 而 `sim/tests/usage/test_ventus_all_viz_validation.py` 的历史
断言基于 DOT 文本 (`digraph` / `rankdir=LR` / `subgraph cluster_stage*` / `shape=diamond`)。
iter_188 的处理: artifact 内容判定为 SVG → `pytest.skip` 并说明原因 (不假装绿)。

## 逐条迁移评估 (实测证据)

实测方法: 跑生成器产出 artifact, 在 SVG 文本里搜原断言依赖的标记
(`stroke-dasharray` / 文本关键词 / 颜色 / `<polygon>` / `width:height` 比例)。

| 原断言 (测试) | 原依赖的 DOT 特征 | 当前 SVG 里能不能验 | 建议 |
|---|---|---|---|
| `test_chain_anomaly_orphan_wire_flagged` | `shape=diamond` / `fillcolor="#cc8800"` | ✅ **能**: SVG 有 `<polygon>` + `#cc8800` + 图例文本 | 迁移为 polygon/颜色断言 |
| `test_chain_anomaly_unused_reg_flagged` | `shape=diamond` / 红色 | ✅ **能** (同上, 图例含 DANGLING) | 同上 |
| `test_chain_diamond_shape_used_for_anomalies` | 所有异常节点 diamond | ✅ 能 (polygon 计数) | 迁移为"异常节点用 polygon 且非矩形" |
| `test_chain_normal_intermediate_still_blue` | 普通节点蓝色 | ⚠️ 需确认取色 | 若渲染器保留蓝色系则可迁移 |
| `test_pipeline_output_file_has_stages` / `stages_preserved` | `subgraph cluster_stage\d+` | ❌ 当前 SVG **无** "stage" 文本/命名簇 | 需产品确认"阶段"在图上的表现形式后重写 |
| `test_pipeline_dot_has_controls_cluster` / `limits_control_nodes` / `nocontrol_dot_has_no_controls` | `cluster_control_header` | ❌ 当前 SVG **无** "control" 文本 | 同上 (或改断 CLI stdout 的统计行) |
| `test_pipeline_default_is_lr_layout` | `rankdir=LR` | ❌ SVG 无 rankdir; 实测宽高比 **0.28 (竖版)** | **原断言早就不成立** → 需先定"pipeline 该横还是竖" |
| `test_pipeline_excludes_clock_reset_from_regs` | `dashed` + "control" | ❌ 同上 | 同上 |
| `test_timing_dot_has_paths` / `critical_path_highlighted` / `includes_mem_core_path` | `critical` 文本 / 高亮边 | ❌ 当前 SVG **无** "critical" 文本 | 需产品确认高亮表现 (颜色/边宽) 后重写 |
| `test_trace_fanout_top_level_signal_returns_empty` | 文件里含 `0 loads` | ❌ 该文本来自 **CLI stdout**, 不在产物里 | **改为断言 stdout** (最简且更正确) |
| `test_trace_fanin_returns_digraph` | `digraph trace` | ❌ trace 已改 `--format dot --output` 产 DOT | 改用 `--format dot` 并断言 DOT (⚠️ 与全局"产物是 SVG"不一致, 需一并决定) |
| `test_d1_arch_has_correct_sub_instances` | `sched_d1.dot` 里子实例 | ⚠️ `visualize module --dot` **仍输出 DOT** (iter_189 曾因其对 filelist 崩而无法生成, 已修) | 重新生成 + 保留 DOT 断言 |
| `test_pipeline_png_size_reduced` / `test_timing_png_size_reasonable` | PNG 高度 | ❌ `visualize pipeline` **没有 `--png`** (只有 chain 有) | 要么给 pipeline 加 `--png`, 要么改断 SVG 宽高 |

**统计**: 可**直接迁移** 3~4 条 (chain 异常类 + trace stdout); **必须先定产品语义** 7~8 条
(pipeline 阶段/控制簇/方向、timing 高亮); **需先补 CLI 能力** 2 条 (pipeline `--png`)。
另: `--dot` 在 `visualize module` 输出 DOT、在 `visualize pipeline/chain` 输出 SVG、
在 `trace` 不存在 (改 `--format dot --output`) —— **同一 CLI 内三种语义**, 是这批断言
集体失效的根因, 建议一并决定是否统一。

## 需要方豆决定的三件事

1. **pipeline / timing 图的产品契约**: 阶段划分、控制信号簇、critical path 高亮分别
   以什么形式呈现 (文本? 颜色? 子图?), 决定后我按契约重写断言 (而不是按实现反推)。
2. **是否统一 viz 输出 flag**: 建议所有 viz 子命令同时提供 `--svg`(渲染) 与
   `--dot`(原始 DOT), 三个子命令语义一致; `trace` 的 `--format dot` 保持不变或并入。
3. **PNG**: 给 pipeline 加 `--png` (与 chain 对齐), 还是把 PNG 断言删掉/改为 SVG 尺寸断言。

## 前置与关联

- `sim/tests/usage/test_ventus_all_viz_validation.py` (13 skip, 0 failed, iter_188)
- CLI 语义: `src/cli/commands/visualize.py:192`、`src/cli/commands/trace.py:611`
- 相关记录: `docs/task_tree/iterations/iter_188_ventus_viz_suite_triage.md`
