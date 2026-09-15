# sv_query 文档索引 (DOCS INDEX)

> **唯一文档入口** — 所有文档从本文件进入;新增文档必须在本文件登记
> (由 `tools/check_docs.py` 强制检查)。
> **最后整理**: 2026-09-08 (iter_171 文档清理 — 63 份过期/重复文档归档至
> `docs/archive/2026-09-08-cleanup/`,原 INDEX / DOC_INDEX / LLM_INDEX 三份
> 索引合并为本文件)。

---

## 📌 当前基线 (单一真相源 — 计数只写在这里)

| 项 | 值 | 说明 |
|---|---|---|
| 源码规模 | 162 文件 / 62,871 行 | `find src -name "*.py"` |
| 测试规模 | 362 测试文件 / 78,383 行 + 117 SV fixture | `sim/tests/` |
| 回归基线 | **2129 passed + 35 subtests** (unit + regression, `-m "not opensource"`) | 2026-09-08 实测 (iter_190 后) |
| 全量 (canonical) | **3278 passed / 37 failed** ⚠️ (`sim/tests/`, `-m "not opensource"`; 8 skipped / 164 deselected) | 2026-09-08 实测 (iter_216): **彻底移除 strict** 批次 2 后 34 个失败 — 16 个可视化 (`test_visualize_teach_nested_mux.py`, 按方豆指示暂缓) + 一批 fixture 在严格模式下暴露真错 (如 `test_snapshot_compare_flags.py`); 待批 3/4/5 修完 |
| CLI / integration | **810 passed / 0 failed** (`sim/tests/cli sim/tests/integration`, `-m "not opensource"`) | 2026-09-08 实测 (iter_185 修复后) |
| 缓存目录 | 可用 `SVQ_CACHE_DIR` 覆盖 (默认顺序: 显式 > env > `$XDG_CACHE_HOME/svq` > `~/.svq/cache`); 不可写自动降级内存缓存 | iter_172 |
| 迭代记录 | `docs/task_tree/iterations/` (210 份, 只增不改) | 每次迭代一份 |
| 文档卫生 | `python3 tools/check_docs.py` 必须 ✅ | 死链 / 归档越界 / 未登记 三项 |
| 静默失败纪律 | `python3 tools/check_except_pass.py` 必须 ✅ | `except ...: pass` 计数 = 0 (iter_190 起) |

> ⚠️ 其他文档**不要**再写死 passed/测试计数 — 计数会漂移;统一引用本表。

---

## 🚪 根目录入口 (项目级)

| 文档 | 作用 |
|---|---|
| [README.md](../README.md) | 项目介绍 + 能力声明 + 快速开始 |
| [AGENTS.md](../AGENTS.md) | **开发纪律 (强制)**: 禁 --no-strict / 禁 silent fallback / 文档卫生规则 |
| [CURRENT_TODO.md](../CURRENT_TODO.md) | **此刻在做的事** (唯一当前任务追踪点) |
| [TESTING.md](../TESTING.md) | 测试流程 / marker / 命令 (唯一测试入口) |
| [CHANGELOG.md](../CHANGELOG.md) | 变更日志 (历史记录) |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | 贡献指南 |
| [DEVELOPMENT.md](../DEVELOPMENT.md) | 开发环境与工作流 |
| [MEMORY.md](../MEMORY.md) | 经验沉淀索引 (`memory/` 按日) |

## 📜 能力与边界 (对外声明)

| 文档 | 作用 |
|---|---|
| [PRIMARY_FEATURES.md](PRIMARY_FEATURES.md) | 主推功能 (3): dataflow / controlflow / visualize |
| [EXPERIMENTAL_FEATURES.md](EXPERIMENTAL_FEATURES.md) | 实验功能 (6): cdc / verify gap / risk / timing / coverage generate / deadlock — **不承诺** |
| [architecture/signal_graph_accuracy_audit.md](architecture/signal_graph_accuracy_audit.md) | **Accuracy Claim 分层声明** (L1/L2/L3 + 反例表 + covergroup 观察域) |
| [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) | 已知限制 (含 pyslang 侧限制) |
| [EXTRACTION_COVERAGE.md](EXTRACTION_COVERAGE.md) | SV 语法抽取覆盖率总表 (逐语法 ✅/⚠️/❌) |
| [EXTRACTION_FAILURES.md](EXTRACTION_FAILURES.md) | 提取失败路径集中表 |

## 🏗️ 架构

| 文档 | 作用 |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 架构总览 (四层 L1-L4) |
| [ARCHITECTURE_EVOLUTION.md](ARCHITECTURE_EVOLUTION.md) | 架构演进历史 |
| [ARCHITECTURE_TODOLIST.md](ARCHITECTURE_TODOLIST.md) | 架构改造 7 项长期追踪 |
| [SIGNAL_GRAPH_SPEC.md](SIGNAL_GRAPH_SPEC.md) | SignalGraph 输入输出 Spec |
| [SV_SYNTAX_MAPPING.md](SV_SYNTAX_MAPPING.md) | SV 语法 ↔ 图节点/边 对应 |
| [PYSLANG_SEMANTIC_USAGE.md](PYSLANG_SEMANTIC_USAGE.md) | pyslang semantic API 使用模式 |
| [architecture/filelist_loader_unification.md](architecture/filelist_loader_unification.md) | filelist 加载器合并决策 (iter_193, 单一解析实现) |
| [architecture/ventus_viz_assertion_migration.md](architecture/ventus_viz_assertion_migration.md) | 🟡 待决: Ventus viz 断言迁移 (iter_195, 13 skip 逐条评估) |
| [PYSLANG_V11.md](PYSLANG_V11.md) | pyslang v11-only 策略 (D5) |
| [PYSLANG_MEMORY_ISSUE.md](PYSLANG_MEMORY_ISSUE.md) | pyslang 内存边界 (大设计) |

### 架构决策记录 (ADR, `docs/architecture/`)

| 决策 | 主题 |
|---|---|
| [case27_signal_graph_completeness_decision.md](architecture/case27_signal_graph_completeness_decision.md) | D1-D5 图完整性 + v11-only 锁定 |
| [class_tracing_architecture_decision.md](architecture/class_tracing_architecture_decision.md) | class/constraint 纳入追踪 (D1-D5) |
| [class_tracing_plan.md](architecture/class_tracing_plan.md) | class 追踪规划 (C1-C5, 已闭环) |
| [covergroup_tracing_plan.md](architecture/covergroup_tracing_plan.md) | covergroup 联系规划 (方案 B / G1-G4, 已闭环) |
| [bitselect_semantic_api_decision.md](architecture/bitselect_semantic_api_decision.md) | BitSelect 提取改用 semantic API |
| [inline_constraint_semantic_unavailable.md](architecture/inline_constraint_semantic_unavailable.md) | inline 约束语义不可达 (暂缓决策) |
| [pyslang11_native_api_g3_plan.md](architecture/pyslang11_native_api_g3_plan.md) | pyslang 11 native API 替换 (G3) |
| [signal_graph_mig_port_to_internal.md](architecture/signal_graph_mig_port_to_internal.md) | MIG port_to_internal 架构 |
| [semantic_adapter_split_plan.md](architecture/semantic_adapter_split_plan.md) | **方案 (待讨论)**: adapter 层拆解 (base.py 死层 + SemanticAdapter 分域) + 回归测试计划 |
| [GRAPH_DIFF_DESIGN.md](architecture/GRAPH_DIFF_DESIGN.md) | graph diff 查询模式 |
| [CORE_RESTRUCTURE.md](architecture/CORE_RESTRUCTURE.md) | core/ 目录重组方案 |
| [CONNECTION_vs_MIG_analysis.md](architecture/CONNECTION_vs_MIG_analysis.md) | ConnectionExtractor vs MIG 分析 |
| [CLASS_CONSTRAINT_PLAN.md](architecture/CLASS_CONSTRAINT_PLAN.md) | class & constraint 拆解方案 |
| [SV_SYNTAX_ROADMAP.md](architecture/SV_SYNTAX_ROADMAP.md) | 语法扩展路线图 |
| [AI_REQUIREMENTS.md](architecture/AI_REQUIREMENTS.md) | AI 功能需求 |
| [code_framework_analysis.md](architecture/code_framework_analysis.md) | 核心模块职责分析 |
| [architecture.md](architecture/architecture.md) | 早期架构设计稿 |

## 🔧 功能文档

| 文档 | 功能 |
|---|---|
| [DATAFLOW.md](DATAFLOW.md) | dataflow 路径分析 |
| [CONTROL_FLOW.md](CONTROL_FLOW.md) | controlflow 分析 |
| [COVERAGE_GENERATOR.md](COVERAGE_GENERATOR.md) | coverage 生成 |
| [RANDOMIZE_COVERGROUP.md](RANDOMIZE_COVERGROUP.md) | randomize / covergroup 分析 |
| [PROTOCOL_DETECTION.md](PROTOCOL_DETECTION.md) | 协议识别 |
| [bus_protocol_detector.md](bus_protocol_detector.md) | Bus 协议检测设计 |
| [SVA_ANALYSIS.md](SVA_ANALYSIS.md) | SVA 分析 |
| [SPEC_UVM_TESTBENCH_EXTRACTOR.md](SPEC_UVM_TESTBENCH_EXTRACTOR.md) | UVM TB 骨架提取 Spec |
| [EVIDENCE_FEATURE.md](EVIDENCE_FEATURE.md) | evidence 追踪 |
| [condition_branch_design.md](condition_branch_design.md) | 条件分支数据层设计 |
| [select_group_design.md](select_group_design.md) | select_group 数据结构 |
| [spec_datapath.md](spec_datapath.md) | 定点数计算功能 Spec |
| [DESIGN_expr_tree_builder.md](DESIGN_expr_tree_builder.md) | expression tree builder 设计 |
| [VISUALIZATION.md](VISUALIZATION.md) | 可视化 (L4) 总览 |
| [VIZ_COMMANDS.md](VIZ_COMMANDS.md) | 画图命令参考 |
| [VIZ_DESIGN_SPEC.md](VIZ_DESIGN_SPEC.md) | 可视化设计规范 v2.0 |
| [VIZ_GOLDEN_PLAN.md](VIZ_GOLDEN_PLAN.md) | VIZ golden 细化计划 |

## 📖 使用与参考

| 文档 | 作用 |
|---|---|
| [USER_GUIDE.md](USER_GUIDE.md) | 用户指南 |
| [CLI_COMMAND_CHEATSHEET.md](CLI_COMMAND_CHEATSHEET.md) | CLI 速查 |
| [ARCH_EXAMPLES.md](ARCH_EXAMPLES.md) | arch 命令实战案例 |
| [SIGNAL_TRACING_EXAMPLES.md](SIGNAL_TRACING_EXAMPLES.md) | 信号追踪实战案例 |
| [FILELIST.md](FILELIST.md) | filelist 格式支持 |
| [TEST_MAP.md](TEST_MAP.md) | 全量测试地图 |
| [BENCH_BASELINE.md](BENCH_BASELINE.md) | bench 深结构基准 (pr5_wrap: 真实 Cfg wrapper + 指标表 + 已知限制) |
| [OPENTITAN_HOWTO.md](OPENTITAN_HOWTO.md) | OpenTitan 跑通 HOWTO |
| [NAPLESPU_HOWTO.md](NAPLESPU_HOWTO.md) | NaplesPU 跑通 HOWTO |
| [PROJECT_PLAN.md](PROJECT_PLAN.md) | 开源 RTL 验证问题生成计划 (独立工作流) |
| [TODO.md](TODO.md) | 版本级功能待办 (月~季) |

## 📓 记录类 (按 AGENTS.md 设施表)

| 位置 | 内容 |
|---|---|
| [task_tree/overview.md](task_tree/overview.md) | 任务树 + 迭代汇总表 |
| [task_tree/iterations/](task_tree/iterations/) | **每次迭代一份** (只增不减, 历史快照) |
| [task_tree/tasks/](task_tree/tasks/) | 任务定义 (L1/L2/L3) |
| [debugging_lessons/debug-mindset-skill.md](debugging_lessons/debug-mindset-skill.md) | 调试复盘 + 调试思路技能 |
| [refactoring/README.md](refactoring/README.md) | 重构计划索引 (2026-06 一轮) |
| [refactoring/2026-06-26_refactoring_roadmap.md](refactoring/2026-06-26_refactoring_roadmap.md) | 拆解计划 |
| [refactoring/2026-06-26_bad_smell_audit.md](refactoring/2026-06-26_bad_smell_audit.md) | Bad smell 报告 |
| [refactoring/2026-06-26_extract_refactoring.md](refactoring/2026-06-26_extract_refactoring.md) | DriverExtractor.extract 拆解 |
| [refactoring/2026-06-26_b-phase_1-2_baseline.md](refactoring/2026-06-26_b-phase_1-2_baseline.md) | B-Phase 1-2 基线 |
| [debugging_lessons/2026-08-25_picorv32_render_tree_cycle.md](debugging_lessons/2026-08-25_picorv32_render_tree_cycle.md) | 调试案例: 渲染树递归 |
| [debugging_lessons/2026-08-25_plan_b_step_g_picorv32_wb_port.md](debugging_lessons/2026-08-25_plan_b_step_g_picorv32_wb_port.md) | 调试案例: ELK dangling port |
| [archive/2026-09-08-cleanup/README.md](archive/2026-09-08-cleanup/README.md) | **归档区** (过期报告 / 重复稿 — 只归档不删除) |
| [archive/README_legacy.md](archive/README_legacy.md) | 早期归档 (2026-07 前) |

---

## 🧹 文档卫生规则 (强制, 与 AGENTS.md 一致)

1. **新增文档必须登记在本文件** — `tools/check_docs.py` 检查 (未登记 = 失败)。
2. **过期报告 / 被取代的稿子 → 归档不删** — 移到 `docs/archive/<日期>-cleanup/`,
   并在该目录 `README.md` 说明原因 (信息不丢, 历史可追)。
3. **计数只写在"当前基线"一节** — 其他文档引用本表, 不写死 passed 数。
4. **提交前跑** `python3 tools/check_docs.py` — 死链 / 归档越界 / 未登记 三项必须 ✅。
