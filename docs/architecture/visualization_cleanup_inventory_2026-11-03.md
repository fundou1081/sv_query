# 旧可视化资产盘点（P59.1）

**日期**: 2026-11-03
**状态**: 盘点完成；待 P59.2 删除/归档
**依据**: [structural_review_plan_2026-11-02.md](structural_review_plan_2026-11-02.md) §8

> 本文件只做清理决策，不是新的计划源；状态以 [PLAN.md](../../PLAN.md) 为准。

---

## 1. 结论

- 全设计图命令全部退役；
- 保留 `SignalGraph`、`trace overview`、`trace fanin/fanout --format dot`（过渡期局部查询图）；
- `detect_pipeline` 是 core 语义，保留；`pipeline_viz` 的渲染部分删除；
- 旧 ELK/VizData/DOT 渲染器全部删除；P62 若需要，重新实现最小局部渲染器；
- 旧可视化测试/文档随命令删除或归档。

---

## 2. CLI 命令

| 命令 | 处置 | 原因 |
|---|---|---|
| `visualize graph` | 删除 | 全设计图 |
| `visualize dataflow` | 删除 | 全图 dataflow 渲染 |
| `visualize pipeline` | 删除 | 全图 pipeline 渲染（`detect_pipeline` 保留） |
| `visualize datapath` | 删除 | 0 测试，全图渲染 |
| `visualize chain` | 删除 | 旧路径渲染 |
| `visualize module` | 删除 | 架构图；hierarchy/ports 已覆盖 |
| `visualize teach` | 删除 | 教学视图，非产品 |
| `arch show` | 删除 | 全图架构；`hierarchy` 覆盖文本需求 |
| `design show` | 删除 | 低覆盖 IP 叙述；与 review 目标不符 |
| `trace overview` | **保留** | 叙述型 review 摘要，不是全图 |
| `trace fanin/fanout --format dot` | **保留（过渡）** | 局部查询图；P62 后再评估替换 |

---

## 3. 源码资产

### 3.1 删除

| 文件/目录 | 约行数 | 说明 |
|---|---:|---|
| `src/cli/view/visualize.py` | 67 | 命令注册 |
| `src/cli/view/visualize_plots.py` | 397 | graph/dataflow/pipeline/datapath |
| `src/cli/view/visualize_chain.py` | 793 | chain |
| `src/cli/view/visualize_module.py` | 294 | module |
| `src/cli/view/visualize_teach.py` | 427 | teach |
| `src/cli/view/visualize_common.py` | 419 | 旧渲染共享 |
| `src/cli/view/arch.py` | 966 | arch show |
| `src/cli/view/design.py` | 485 | design show |
| `src/cli/_viz_common.py` | — | visualize 共享 |
| `src/sv_query/trace/core/graph/viz/` | ~5k | VizData/ELK/checker/engine/expression tree |
| `src/sv_query/trace/core/graph/analyzer/dataflow_viz.py` | 206 | 旧 dataflow DOT |
| `src/sv_query/trace/core/graph/analyzer/viz_legend.py` | 174 | 旧图例 |
| `src/sv_query/trace/core/graph/analyzer/_dot_common.py` | — | 旧 DOT 共享 |
| `src/sv_query/trace/core/graph/viz/elk_layout.js` | — | ELK 布局资源 |

### 3.2 保留 / 拆分

| 文件 | 处置 |
|---|---|
| `src/sv_query/trace/core/graph/analyzer/pipeline_viz.py` | **拆分**：保留 `detect_pipeline`；删除 DOT 渲染函数 |
| `src/sv_query/trace/core/graph/analyzer/signal_classifier.py` | 保留（core 分类） |
| `src/sv_query/trace/core/graph/dataflow.py` | 保留（只保留 `detect_pipeline` 调用） |
| `src/cli/core/semantic/trace_common.py` | 保留 `_generate_trace_dot`（过渡局部图） |
| `src/cli/core/semantic/trace_overview.py` | 保留 |

> 删除前必须确认 `pipeline_viz` 中除 `detect_pipeline` 外的函数无生产调用方；
> 有调用方则先迁移到 core，再删。

---

## 4. 测试

### 4.1 随命令删除/归档

- `sim/tests/cli/test_visualize_*.py`
- `sim/tests/cli/test_arch*.py`
- `sim/tests/cli/test_design.py`
- `sim/tests/cli/test_cross_viz_consistency.py`
- `sim/tests/cli/test_golden_chain_anomalies.py`
- `sim/tests/unit/test_pr4_visualize_l2.py`
- `sim/tests/unit/test_visualize_module_golden.py`
- `sim/tests/unit/test_viz_data.py`
- `sim/tests/unit/test_viz_expr_trees.py`
- `sim/tests/integration/test_real_project_viz.py`
- `sim/tests/usage/test_ventus_all_viz_validation.py` 中可视化断言
- `sim/tests/manual/regress_golden_mini.py`
- 其它只验证旧渲染产物的用例

### 4.2 保留/改写

| 测试 | 处置 |
|---|---|
| `test_trace.py` 的 `--format dot` | 保留（过渡局部图） |
| `test_trace_overview.py` | 保留 |
| `test_visualize_pipeline_json.py` 的 pipeline 检测部分 | 若依赖被删命令，迁移为 `detect_pipeline` 单测 |
| `test_cli_layering.py` | 更新：移除 visualize/arch/design 的 exp 断言 |
| `test_cli_readonly_guarantee.py` | 更新：移除已删命令 |
| `test_json_contract_adversarial.py` | 删除 visualize 相关用例，保留通用 `--json` 用例 |
| `test_cli_filelist_parity.py` | 删除 visualize parity 用例 |

---

## 5. 文档

| 文档 | 处置 |
|---|---|
| `docs/VISUALIZATION.md` | 归档（V5 era，已过期） |
| `docs/VIZ_COMMANDS.md` | 归档 |
| `docs/VIZ_DESIGN_SPEC.md` | 归档 |
| `docs/VIZ_GOLDEN_PLAN.md` | 归档 |
| `docs/PRIMARY_FEATURES.md` | 删除 visualize 主推声明与 `--no-strict` 旧示例 |
| `docs/KNOWN_LIMITATIONS.md` | 删除/改写旧可视化条目 |
| `docs/ARCHITECTURE.md` | 移除可视化层描述或标注退役 |
| `docs/INDEX.md` | 移除旧文档入口，加入归档说明 |
| `src/cli/_registry.py` | 删除 `view` 命令与 `view` LayerSpec（或标 reserved） |
| `src/cli/main.py` | 删除 `vis_app` / `arch_app` / `design_app` 注册 |

---

## 6. 冻结规则（P59.1 生效）

- 不再向旧 `src/cli/view`、`src/sv_query/trace/core/graph/viz` 添加功能；
- 不再修旧全图渲染 bug（除阻塞清理的导入错误）；
- 旧命令仍隐藏，等待 P59.2 删除；
- 新开发只允许 P60 `graph subgraph` core / P61 findings。

---

## 7. P59.2 执行顺序

1. 删除 CLI 注册与 `_registry` 条目；
2. 删除 `src/cli/view` + `_viz_common`；
3. 删除 `src/sv_query/trace/core/graph/viz` + 旧 analyzer 渲染；
4. 拆分 `pipeline_viz`，保留 `detect_pipeline`；
5. 删除/改写测试；
6. 归档/改写文档；
7. 全量 + 真实项目 smoke；
8. 独立 commit（可 revert）。

---

## 8. 风险

| 风险 | 缓解 |
|---|---|
| `pipeline_viz` 渲染函数被 core 误用 | 先 `grep` 调用方；只删渲染；`detect_pipeline` 保留 |
| 删除测试过多掩盖回归 | 保留 core 单测；P60/P61 新增子图/finding 测试 |
| 文档死链 | 归档并更新 INDEX；`check_docs` |
| 未来 P62 想复用 ELK | git 历史可恢复；先不背 2.4k 死代码 |
