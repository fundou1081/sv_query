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
| 源码规模 | 137 文件 / 49,377 行 | `find src -name "*.py"`（2026-11-11 实测） |
| 测试规模 | 378 测试文件 / 64,311 行 + 192 SV fixture | `find sim/tests -name "*.py"` / `-name "*.sv"`（2026-11-11 实测） |
| 全量 (canonical) | **2724 passed / 0 failed** ✅ (`sim/tests/`, `-m "not opensource"`; **0 skipped** / 123 deselected = `unexecuted`; 35 subtests) | **2026-11-12 独立复核**（iter_495，P158.12.6 后干净工作树，36min）；含 R-026 自环清除后的 golden 重捕；**0 skipped 与 0 failed 都不是健康指标**，状态口径见 [REPORT_STATUS](dev/REPORT_STATUS.md) / TESTING §语义测试 |
| CLI / integration 子集 | 不再单独维护 | 旧 `2129` / `810` 是 2026-09-08 的子集快照，已过期；一律看全量行 |
| 缓存目录 | 可用 `SVQ_CACHE_DIR` 覆盖 (默认顺序: 显式 > env > `$XDG_CACHE_HOME/svq` > `~/.svq/cache`); 不可写自动降级内存缓存 | iter_172 |
| 迭代记录 | `docs/task_tree/iterations/` (485 份, 只增不改) | 每次迭代一份（2026-11-12 实测） |
| 文档卫生 | `python3 tools/check_docs.py` 必须 ✅ | 死链 / 归档越界 / 未登记 三项 |
| 静默失败纪律 | `python3 tools/check_except_pass.py` 必须 ✅ | `except ...: pass` 计数 = 0 (iter_190 起) |
| 语义 regex 纪律 | `python3 tools/check_semantic_regex.py` 必须 ✅ | 仅 UVM 宏例外；class/constraint/covergroup 语义走 slang (iter_368) |

> ⚠️ 其他文档**不要**再写死 passed/测试计数 — 计数会漂移;统一引用本表。

---

## 🚪 根目录入口 (项目级)

| 文档 | 作用 |
|---|---|
| [README.md](../README.md) | 项目介绍 + 能力声明 + 快速开始 |
| [AGENTS.md](../AGENTS.md) | **协作入口 (强制)**: 流程 + 铁律速查 + 细则索引 (细则在 `docs/dev/`) |
| [PLAN.md](../PLAN.md) | **全局唯一计划树**: 所有代码修改计划的登记 + 状态 (校验 `tools/check_plan.py`) |
| [CURRENT_TODO.md](../CURRENT_TODO.md) | **此刻在做的事** (唯一当前任务追踪点) |
| [TESTING.md](../TESTING.md) | 测试流程 / marker / 命令 (唯一测试入口) |
| [CHANGELOG.md](../CHANGELOG.md) | 变更日志 (历史记录) |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | 贡献指南 |
| [DEVELOPMENT.md](../DEVELOPMENT.md) | 开发环境与工作流 |
| [memory/](../memory/) | 经验沉淀索引 (`memory/` 按日) |

## 🛠️ 开发纪律与流程 (`docs/dev/` — 细则层)

> 入口在 [AGENTS.md](../AGENTS.md)；本节是它链接到的细则文件。
> 规则变更必须**同一次改动**里同步检查器或测试 (见 WORKFLOW §5)。

| 文档 | 作用 |
|---|---|
| [dev/DISCIPLINE.md](dev/DISCIPLINE.md) | **开发纪律 (强制)**: 产品不变量 I1~I5 + 5 条硬规则 + 归因顺序 + 例外 + 违规处置 |
| [dev/HANDOFF.md](dev/HANDOFF.md) | **交接**: 当前状态 / 剩余工作 / worker 协议 / 交回 checklist |
| [dev/HANDOFF_2026-11-12.md](dev/HANDOFF_2026-11-12.md) | **会话交接快照 (2026-11-12)**: P158.9.2→12.6 三次提交 / 设计裁决 / 待拍板 / 踩坑 / 接手 checklist |
| [sessions/2026-11-11_sv_query_session_log.md](sessions/2026-11-11_sv_query_session_log.md) | **P163**: 对话/工作事实记录（非逐字） |
| [dev/SEMANTIC_CONTRACTS.md](dev/SEMANTIC_CONTRACTS.md) | **语义契约**: 数据边 / 路径 / verified / snapshot / 完成判定 |
| [dev/REPORT_STATUS.md](dev/REPORT_STATUS.md) | **绿色口径统一 (P158.12.6)**: 7 类状态 / canonical+opensource 合并视图 / false_confident 分母 |
| [dev/SNAPSHOT_SURFACE.md](dev/SNAPSHOT_SURFACE.md) | **快照能力面矩阵 (P158.9.2)**: 字段级保真 / 命令级支持面 / 显式不保证清单 |
| [dev/CLAIMS.md](dev/CLAIMS.md) | **claim 台账**: 公开能力的证据与状态 |
| [dev/CODING_STYLE.md](dev/CODING_STYLE.md) | 编码风格与设计决策: 先探索后决策 / 单一实现 / 修根因 / 函数职责 / 结构化数据 / 影响面 / 协作规则 |
| [dev/WORKFLOW.md](dev/WORKFLOW.md) | 开发流程: 任务生命周期 / 迭代记录 / 文档卫生 / 测试与冒烟 / 机械检查 / ADR / 提交合并 |
| [dev/PROJECT_ADAPTATION.md](dev/PROJECT_ADAPTATION.md) | **项目适配理念**: core 不自动推断特定项目；外部 adapter 模板 |
| [agent/GUIDED_TRACE.md](agent/GUIDED_TRACE.md) | **P139 guided trace**: frontier + next probes；不分类 FIFO |
| [agent/AGENT_FEATURE_MAP.md](agent/AGENT_FEATURE_MAP.md) | **P143**: core 40 个 schema 命令的能力地图 |
| [agent/AGENT_TASK_CORPUS.md](agent/AGENT_TASK_CORPUS.md) | **P145**: 13 个可执行 agent 任务 + false-confident/found 指标 |
| [validation/P145_VALIDATION_BASELINE_2026-11-10.md](validation/P145_VALIDATION_BASELINE_2026-11-10.md) | **P145**: full gate 环境 skip + agent corpus |
| [validation/P145_WORKER_REVIEW_2026-11-10.md](validation/P145_WORKER_REVIEW_2026-11-10.md) | **P145 worker replay**: APPROVE WITH NITS；nits 已修 |
| [validation/P146_REAL_MATRIX_2026-11-10.md](validation/P146_REAL_MATRIX_2026-11-10.md) | **P146**: UART/I2C real matrix；问题清单与修复 |
| [validation/P147_SPI_HOST_2026-11-10.md](validation/P147_SPI_HOST_2026-11-10.md) | **P147**: 第三 block SPI_HOST snapshot + 6-task smoke |
| [validation/P148_VERIFY_WIDTH_2026-11-10.md](validation/P148_VERIFY_WIDTH_2026-11-10.md) | **P148**: single-bit width sentinel 修复 |
| [validation/P149_CONSISTENCY_SNAPSHOT_2026-11-10.md](validation/P149_CONSISTENCY_SNAPSHOT_2026-11-10.md) | **P149**: consistency --from-snapshot；MIG 缺失显式 unknown |
| [validation/P150_ID_PARENT_2026-11-10.md](validation/P150_ID_PARENT_2026-11-10.md) | **P150**: id_parent 误报修复；SPI bit 171→0 |
| [validation/P151_SNAPSHOT_MIG_2026-11-10.md](validation/P151_SNAPSHOT_MIG_2026-11-10.md) | **P151**: snapshot 持久化 MIG；connection 可离线检查 |
| [validation/P152_SPI_CORPUS_2026-11-10.md](validation/P152_SPI_CORPUS_2026-11-10.md) | **P152**: SPI_HOST 9-task corpus |
| [validation/P153_TRANSITIVE_FANIN_2026-11-10.md](validation/P153_TRANSITIVE_FANIN_2026-11-10.md) | **P153**: wrapper_passthrough transitive fanin 修复 |
| [validation/P154_SNAPSHOT_PROBES_2026-11-10.md](validation/P154_SNAPSHOT_PROBES_2026-11-10.md) | **P154**: snapshot probes 可执行 |
| [validation/P155_RECIPROCITY_2026-11-10.md](validation/P155_RECIPROCITY_2026-11-10.md) | **P155**: reciprocity BIT_SELECT 误报；SPI 128→0 |
| [validation/P156_SNAPSHOT_MIG_METADATA_2026-11-11.md](validation/P156_SNAPSHOT_MIG_METADATA_2026-11-11.md) | **P156**: snapshot MIG 可用性元数据 |
| [validation/P157_SKIP_CLEANUP_2026-11-11.md](validation/P157_SKIP_CLEANUP_2026-11-11.md) | **P157**: canonical skip 清理；12→0 |
| [validation/P158_REMEDIATION_2026-11-11.md](validation/P158_REMEDIATION_2026-11-11.md) | **P158 wave1**: data-edge / bounds / determinism / corpus |
| [validation/P160_OPENSOURCE_TRIAGE_2026-11-11.md](validation/P160_OPENSOURCE_TRIAGE_2026-11-11.md) | **P160**: 38 opensource failures classified |
| [validation/P161_OPENSOURCE_REMEDIATION_2026-11-11.md](validation/P161_OPENSOURCE_REMEDIATION_2026-11-11.md) | **P161**: opensource 38 failed → 0 failed |
| [validation/P167_OPENSOURCE_SKIP_DISPOSITION_2026-11-12.md](validation/P167_OPENSOURCE_SKIP_DISPOSITION_2026-11-12.md) | **P167**: 8 retired tests archived; 9 explicit env skips |
| [lessons/2026-11-11_pitfalls.md](lessons/2026-11-11_pitfalls.md) | **P159**: 22 个踩坑/误判/经验，含对外分享版 |
| [validation/REVIEW_2026-11-11.md](validation/REVIEW_2026-11-11.md) | **P158 输入**: 4-angle review + 28 项修复账本 |
| [validation/P139_FRONTIER_2026-11-09.md](validation/P139_FRONTIER_2026-11-09.md) | **P139 frontier**: 断点 + next probes；不分类 FIFO |
| [validation/P139_WORKER_REVIEW_2026-11-09.md](validation/P139_WORKER_REVIEW_2026-11-09.md) | **P139 worker review**: APPROVE WITH NITS；nits 已修 |
| [validation/P140_GUIDED_BOUNDARY_2026-11-09.md](validation/P140_GUIDED_BOUNDARY_2026-11-09.md) | **P140**: 显式 boundary map 跑通 I2C S1 |
| [validation/P140_WORKER_REVIEW_2026-11-09.md](validation/P140_WORKER_REVIEW_2026-11-09.md) | **P140 worker review**: APPROVE WITH NITS；nits 已修 |
| [validation/P141_DEEP_PATHS_2026-11-09.md](validation/P141_DEEP_PATHS_2026-11-09.md) | **P141**: 三模块深层 from/to |
| [validation/P142_CONSTRAINT_CHAIN_2026-11-09.md](validation/P142_CONSTRAINT_CHAIN_2026-11-09.md) | **P142**: random 变量 constraint 链 |
| [dev/REVIEW_CHECKLIST.md](dev/REVIEW_CHECKLIST.md) | 提交前检查清单: 机械检查命令 + 纪律/设计/影响面/记录四组自检 + 反模式表 |

## 📜 能力与边界 (对外声明)

| 文档 | 作用 |
|---|---|
| [PRIMARY_FEATURES.md](PRIMARY_FEATURES.md) | 主推功能: 查询/追踪/校验（visualize 已退役） |
| [EXPERIMENTAL_FEATURES.md](EXPERIMENTAL_FEATURES.md) | 实验功能说明（**正文为 2026-07-04 快照，命令名已失效**；当前 exp 5 个命令以 `capabilities --include-exp` 为准） |
| [EXP_IDEAS.md](EXP_IDEAS.md) | **exp 创意清单 (未落地)**: 10 条想法 + 各自要解决的问题场景 |
| [EXP_NAMESPACE.md](EXP_NAMESPACE.md) | exp 层已退役说明 (代码归档在 archive/2026-10-20-exp-attic) |
| [poc/2026-10-23_native_connectivity.md](poc/2026-10-23_native_connectivity.md) | **POC**: slang-native 连通性 vs 现有两套路径实现 (影子节点 30~38%、0 可达; PathResolver 终点错误 60%+) |
| [architecture/signal_graph_accuracy_audit.md](architecture/signal_graph_accuracy_audit.md) | **Accuracy Claim 分层声明** (L1/L2/L3 + 反例表 + covergroup 观察域) |
| [architecture/trace_capability_review_2026-10-27.md](architecture/trace_capability_review_2026-10-27.md) | **信号追踪能力评审** (2026-10-27): 现状矩阵 + P0~P3 缺口 backlog（含缓存模式 P0 bug） |
| [architecture/condition_analysis_plan_2026-10-31.md](architecture/condition_analysis_plan_2026-10-31.md) | **条件化简/互斥设计评估** (2026-10-31, 未排期): L1 局部布尔 / L2 来源互斥 / L3 真值表-BDD |
| [architecture/json_contract_2026-10-31.md](architecture/json_contract_2026-10-31.md) | **Agent JSON 契约** (schema v1): envelope + trace signal/node 字段/版本策略/示例 |
| [architecture/product_direction_2026-10-31.md](architecture/product_direction_2026-10-31.md) | **产品方向**: agent RTL 查询+客观校验；debug/design 场景、P0 grounding、波形元数据、非目标 |
| [architecture/structural_review_plan_2026-11-02.md](architecture/structural_review_plan_2026-11-02.md) | **可视化重定位/结构审查计划** (2026-11-02): 全设计图退役；动态子图 core；finding 局部 review；P59 清理 → P60~P62 |
| [architecture/visualization_cleanup_inventory_2026-11-03.md](architecture/visualization_cleanup_inventory_2026-11-03.md) | **P59.1 旧可视化资产盘点**: 命令/源码/测试/文档 keep/delete 决策与清理顺序 |
| [architecture/graph_subgraph_contract_2026-11-03.md](architecture/graph_subgraph_contract_2026-11-03.md) | **`graph subgraph` 契约**: 参数/边类型/JSON/预算/boundary/确定性 |
| [architecture/structural_findings_contract_2026-11-03.md](architecture/structural_findings_contract_2026-11-03.md) | **`verify structural` 契约**: symmetry.port_set findings/evidence/subgraph/边界 |
| [architecture/review_artifact_2026-11-03.md](architecture/review_artifact_2026-11-03.md) | **finding 局部 review artifact**: review render SVG/HTML、missing stub、确定性、边界 |
| [architecture/class_constraint_covergroup_contract_2026-11-03.md](architecture/class_constraint_covergroup_contract_2026-11-03.md) | **class/constraint/covergroup 契约**: relations 增强、constraint blocks、covergroup Q1/Q2/Q3 |
| [validation/QUERY_PERF_2026-11-04.md](validation/QUERY_PERF_2026-11-04.md) | **查询性能基准**: picorv32 / verilog-axi / SERV 的 build、warm query、cold CLI、峰值内存 |
| [validation/LONG_RANGE_PILOT_2026-11-05.md](validation/LONG_RANGE_PILOT_2026-11-05.md) | **长程结构查询 pilot**: MiniMax-M3 / DeepSeek-Flash 的 source-only vs sv_query；4 题、含隔离缺陷 |
| [validation/LONG_RANGE_12_2026-11-05.md](validation/LONG_RANGE_12_2026-11-05.md) | **长程结构查询 12-task 对照**: 48 agents；exact 6–7/12 → 12/12；wall time 未下降；输入污染已审计 |
| [validation/LONG_RANGE_SEED2_2026-11-05.md](validation/LONG_RANGE_SEED2_2026-11-05.md) | **seed-2 全 12 题**: T2 两 seed 12/12；source 6–10/12；软隔离但仍有 artifact 污染 |
| [validation/HARD_ISOLATION_2026-11-05.md](validation/HARD_ISOLATION_2026-11-05.md) | **硬隔离 PoC + 审计**: canonical path 泄漏已修；两模型单题正确；硬隔离方差未评估 |
| [architecture/project_audit_2026-11-06.md](architecture/project_audit_2026-11-06.md) | **项目审计**: 原始目标/计划状态/未完成开发/测试缺口/下一步排序 |
| [architecture/arch_eval_2026-11-11.md](architecture/arch_eval_2026-11-11.md) | **架构/产品评估（讨论底稿，2026-11-11）**: 只读评审；不构成已登记计划，采纳需先登记 PLAN |
| [validation/INTERACTIVE_DEBUG_2026-11-06.md](validation/INTERACTIVE_DEBUG_2026-11-06.md) | **交互式 debug pilot**: 3 场景 × 3 模型；5–20 轮；发现路径粒度/mux/bin 名称/class relative 问题 |
| [validation/INTERACTIVE_P0_2026-11-06.md](validation/INTERACTIVE_P0_2026-11-06.md) | **P0 post-P77**: 3 模型 × deep_chain；clarify 后 3/3 正确；12 节点/11 hops |
| [validation/INTERACTIVE_P1_2026-11-06.md](validation/INTERACTIVE_P1_2026-11-06.md) | **P1**: 3 场景 × 3 模型 × 2 seed；17/18 完整；constraints 1 个字段歧义；429 重跑 |
| [validation/EXPERIMENT_INVENTORY_2026-11-06.md](validation/EXPERIMENT_INVENTORY_2026-11-06.md) | **实验资产盘点**: multi-turn runner / long-range 12 / pilot / hard isolation 的路径与缺口 |
| [validation/LONG_RANGE_RUNNER_2026-11-06.md](validation/LONG_RANGE_RUNNER_2026-11-06.md) | **P81 runner**: hard-isolated source/T2 long-range；单题 smoke exact；未跑矩阵 |
| [validation/LONG_RANGE_4TASK_2026-11-07.md](validation/LONG_RANGE_4TASK_2026-11-07.md) | **P82 4-task pilot**: 32 cells；source 11/16 vs T2 10/16；pico direct fanout 0/8；agent 协议问题 |
| [validation/LONG_RANGE_4TASK_FIXED_2026-11-07.md](validation/LONG_RANGE_4TASK_FIXED_2026-11-07.md) | **P83 修复后**: T2 16/16 vs source 11/16；T2 0 high-conf；query log 11/16 |
| [validation/INTERACTIVE_NEIGHBORHOOD_2026-11-07.md](validation/INTERACTIVE_NEIGHBORHOOD_2026-11-07.md) | **P84 邻域场景**: complex constraints / nested mux；3 模型 ×2 场景 6/6 |
| [validation/NEIGHBORHOOD_SOURCE_T2_2026-11-07.md](validation/NEIGHBORHOOD_SOURCE_T2_2026-11-07.md) | **P85 source/T2**: canonical 0 vs4/12；semantic 11 vs11/12；T2 只有 canonical 优势 |
| [validation/DUAL_SCORING_2026-11-07.md](validation/DUAL_SCORING_2026-11-07.md) | **P86 双评分**: canonical + semantic 统一；direct semantic=n/a；P85 重算 |
| [validation/LONG_RANGE_12_FIXED_2026-11-07.md](validation/LONG_RANGE_12_FIXED_2026-11-07.md) | **P87 12-task fixed**: T2 48/48 vs source 32/48；source high-conf 9；hard-isolated |
| [validation/FINAL_VALIDATION_SUMMARY_2026-11-07.md](validation/FINAL_VALIDATION_SUMMARY_2026-11-07.md) | **最终验证摘要（P89）**: 已支持/未验证/不可宣称；外部 VeriBug 放弃 |
| [validation/QUERY_COST_ATTRIBUTION_2026-11-07.md](validation/QUERY_COST_ATTRIBUTION_2026-11-07.md) | **P90 成本归因**: query 仅 12–13%；模型生成主导；暂停 serve |
| [validation/SESSION_TELEMETRY_2026-11-07.md](validation/SESSION_TELEMETRY_2026-11-07.md) | **P90.3 telemetry 修正**: 真实 sv_query 48/48；`queries` 是 lossy；tool 19–28% |
| [validation/FILELIST_PRUNE_2026-11-07.md](validation/FILELIST_PRUNE_2026-11-07.md) | **P91 top-aware prune**: AXI 55→3, 27.3s→0.84s；SERV 24→17, 3.4→1.23s |
| [validation/SNAPSHOT_2026-11-07.md](validation/SNAPSHOT_2026-11-07.md) | **P92 snapshot D**: AXI 18MB / load 0.54s；paths from snapshot；connections 不支持 |
| [validation/A_D_TEST_2026-11-07.md](validation/A_D_TEST_2026-11-07.md) | **P93 A/D tests**: prune fallback、snapshot paths、8-task matrix；当时全量基线 2571（历史，不代表当前） |
| [validation/MODEL_COMPARISON_AD_2026-11-07.md](validation/MODEL_COMPARISON_AD_2026-11-07.md) | **P94 A+D vs 原版**: T2 准确率不变 24/24；延迟反而更慢（seed1）；不设为默认 |
| [validation/A_D_STRICT_ATTEMPT_2026-11-07.md](validation/A_D_STRICT_ATTEMPT_2026-11-07.md) | **P95 严格 A/D**: query-only/deny repo 失败；agent 搜索/读 JSON；放弃 |
| [validation/SKILL_PILOT_2026-11-07.md](validation/SKILL_PILOT_2026-11-07.md) | **P96 skill pilot**: 3 cells ×2 条件；skill 未被加载；无收益 |
| [validation/SKILL_INLINE_PILOT_2026-11-07.md](validation/SKILL_INLINE_PILOT_2026-11-07.md) | **P97 inline skill**: 3 cells；prompt78.3s vs inline111.8s；无稳定收益 |
| [validation/TOOL_PILOT_2026-11-07.md](validation/TOOL_PILOT_2026-11-07.md) | **P98 受限工具**: DeepSeek 3/3，4–6s，单次 svq_query；MiniMax 429 阻塞 |
| [validation/TOOL_PILOT_12_2026-11-08.md](validation/TOOL_PILOT_12_2026-11-08.md) | **P98 12 题**: 48/48；MiniMax 9.0s / DeepSeek 4.7s；单次工具调用 |
| [validation/WORKER_TOOL_HARDENING_2026-11-08.md](validation/WORKER_TOOL_HARDENING_2026-11-08.md) | **P99 worker 硬化**: compact.js + 12 Node tests；3-cell smoke 6/6 |
| [validation/TOOL_DETAILS_2026-11-08.md](validation/TOOL_DETAILS_2026-11-08.md) | **P100 details**: kind/condition/distance；mux 结构基本正确但 alias/条件语义未解 |
| [validation/TOOL_NEIGHBORHOOD_2026-11-08.md](validation/TOOL_NEIGHBORHOOD_2026-11-08.md) | **P100.3/P101 neighborhood**: bounded fanin BFS；conditions + condition_atoms；mux depth5 结构与条件 2 条 |
| [validation/WORKER_BFS_TESTS_2026-11-08.md](validation/WORKER_BFS_TESTS_2026-11-08.md) | **P102 worker BFS tests**: neighborhood.js 可注入；22 Node tests；3-cell 6/6 |
| [validation/DEEP_CHAIN_TOOL_PROBE_2026-11-08.md](validation/DEEP_CHAIN_TOOL_PROBE_2026-11-08.md) | **P103 deep_chain**: 3-step 协议执行，path 绕过 ternary，xor/combinational 错 |
| [validation/GRANULAR_PATH_2026-11-08.md](validation/GRANULAR_PATH_2026-11-08.md) | **P104 granular path**: deep 12 nodes/11 hops；除 xor_node 外正确；3-cell 6/6 |
| [validation/TOOL_EVIDENCE_2026-11-08.md](validation/TOOL_EVIDENCE_2026-11-08.md) | **P105 evidence**: file/line/source_context；deep 7/7；xor 修复 |
| [validation/TOOL_EVIDENCE_DEFAULT_REGRESSION_2026-11-08.md](validation/TOOL_EVIDENCE_DEFAULT_REGRESSION_2026-11-08.md) | **P106 回归**: evidence 默认关闭；12 题 24/24；Mini 5.1s / Deep 4.0s |
| [validation/WORKER_EVIDENCE_TESTS_2026-11-08.md](validation/WORKER_EVIDENCE_TESTS_2026-11-08.md) | **P107 evidence tests**: evidence.js 注入式；13 tests / 36 total |
| [validation/TOOL_EVIDENCE_COST_2026-11-08.md](validation/TOOL_EVIDENCE_COST_2026-11-08.md) | **P108 evidence 成本**: 3-cell 6/6；token +2.1% |
| [validation/TOOL_DEFAULT_DECISION_2026-11-08.md](validation/TOOL_DEFAULT_DECISION_2026-11-08.md) | **P109 默认决策**: opt-in profile；不做全局默认 |
| [validation/BLIND_REALISTIC_2026-11-08.md](validation/BLIND_REALISTIC_2026-11-08.md) | **P110 blind**: fresh 9/10，false-confident 0；path 默认 bug 修复 |
| [validation/SNAPSHOT_SETUP_2026-11-08.md](validation/SNAPSHOT_SETUP_2026-11-08.md) | **P111 snapshot setup**: 新 snapshot 5 任务 10/10；0 false-confident |
| [validation/UNKNOWN_CONTRACT_2026-11-08.md](validation/UNKNOWN_CONTRACT_2026-11-08.md) | **P112 unknown 合同**: ok/status/found；空 vs not_found；3-cell 6/6 |
| [validation/CONTRACT_BLIND_2026-11-08.md](validation/CONTRACT_BLIND_2026-11-08.md) | **P113 contract**: 10/10；false-confident/false-found 0；F1-F4、deep_path、source root |
| [validation/BLIND_D_2026-11-08.md](validation/BLIND_D_2026-11-08.md) | **P114 fresh blind**: 10/10；false-confident/false-found 0；5 个新任务 |
| [validation/P115_10TASK_2SEED_2026-11-08.md](validation/P115_10TASK_2SEED_2026-11-08.md) | **P115 10-task ×2-seed**: 39/40 valid JSON；false 0；1 单引号格式失败 |
| [validation/ANSWER_FORMAT_2026-11-08.md](validation/ANSWER_FORMAT_2026-11-08.md) | **P116 answer JSON**: strict + single-quote repair；P115 重放 40/40，1 repaired |
| [validation/VERIFY_CLAIM_2026-11-08.md](validation/VERIFY_CLAIM_2026-11-08.md) | **P117 verify**: snapshot claim + tool intent；6/6，单次 verify |
| [validation/OPENTITAN_PILOT_2026-11-09.md](validation/OPENTITAN_PILOT_2026-11-09.md) | **P118 OpenTitan UART**: 4803 nodes；6/10；核心问题是 edge evidence |
| [validation/EDGE_EVIDENCE_2026-11-09.md](validation/EDGE_EVIDENCE_2026-11-09.md) | **P119 edge evidence**: snapshot edge source_location；OpenTitan T3 2/2 |
| [validation/opentitan_uart/agent_results_after_fixes.json](validation/opentitan_uart/agent_results_after_fixes.json) | **P120 OpenTitan final**: 10/10；T3 edge evidence + T5 schema 修复 |
| [validation/OPENTITAN_CONTINUOUS_2026-11-09.md](validation/OPENTITAN_CONTINUOUS_2026-11-09.md) | **P121 continuous**: 9/10；唯一失败是 canonical path 歧义 |
| [validation/CANONICAL_PATH_2026-11-09.md](validation/CANONICAL_PATH_2026-11-09.md) | **P122 canonical path**: 连续 10/10；0 false；runner timeout 修复 |
| [validation/OPENTITAN_I2C_2026-11-09.md](validation/OPENTITAN_I2C_2026-11-09.md) | **P123 I2C**: 9370 nodes；6/6；纠正 worker 两处语义误判 |
| [validation/TASK_DISTRIBUTION_2026-11-09.md](validation/TASK_DISTRIBUTION_2026-11-09.md) | **Task distribution**: 38 tasks；50% direct；discovery 2；非用户研究 |
| [architecture/PENDING_INVENTORY_2026-11-09.md](architecture/PENDING_INVENTORY_2026-11-09.md) | **待做盘点**: 代码 TODO 0；文档债过期；P125 intake 执行优先 |
| [validation/OPENTITAN_INTAKE_RESULTS_2026-11-09.md](validation/OPENTITAN_INTAKE_RESULTS_2026-11-09.md) | **P125 intake results**: 6/6；discovery/verify/path 均通过 |
| [validation/OPENTITAN_P127_2026-11-09.md](validation/OPENTITAN_P127_2026-11-09.md) | **P127 two more DV tasks**: initial 2/4；alias schema fix 4/4 |
| [validation/FREEZE_V0_3_0_AGENT_QUERY_2026-11-09.md](validation/FREEZE_V0_3_0_AGENT_QUERY_2026-11-09.md) | **Freeze v0.3.0-agent-query**: baseline/tag/limits/rules |
| [validation/FREEZE_SMOKE_2026-11-09.md](validation/FREEZE_SMOKE_2026-11-09.md) | **P129 freeze smoke**: clean tag clone + query/verify ✅ |
| [validation/LONG_REGRESSION_2026-11-09.md](validation/LONG_REGRESSION_2026-11-09.md) | **P130 long regression**: 12 tasks ×2 模型 24/24 |
| [validation/OPENTITAN_TB_ANGLE_2026-11-09.md](validation/OPENTITAN_TB_ANGLE_2026-11-09.md) | **P130 TB angle**: candidates exist；coverage 阻塞；v0.4 gate |
| [validation/COVERAGE_LIMITATION_2026-11-09.md](validation/COVERAGE_LIMITATION_2026-11-09.md) | **P131 coverage limitation**: strict；schema 标注 pyslang 限制 |
| [validation/CONSTRAINT_NEIGHBORHOOD_2026-11-09.md](validation/CONSTRAINT_NEIGHBORHOOD_2026-11-09.md) | **P132 constraint neighborhood**: 跨 block 关系图 + importance |
| [validation/ARCHITECTURE_GRAPH_2026-11-09.md](validation/ARCHITECTURE_GRAPH_2026-11-09.md) | **P133 architecture graph**: 实例级真实 net 连接 + SVG |
| [validation/P134_REAL_USE_2026-11-09.md](validation/P134_REAL_USE_2026-11-09.md) | **P134 real-use pilot**: 3 场景；FIFO 断链；architecture 修复 |
| [validation/P135_FIFO_CONNECTIVITY_2026-11-09.md](validation/P135_FIFO_CONNECTIVITY_2026-11-09.md) | **P135 FIFO**: 父总线聚合；`--through-fifo`；I2C 端到端 |
| [validation/P136_FALSE_MISSING_WARNING_2026-11-09.md](validation/P136_FALSE_MISSING_WARNING_2026-11-09.md) | **P136.1 false warning**: source-known 判定；I2C warning=0 |
| [validation/P136_ARCH_SNAPSHOT_2026-11-09.md](validation/P136_ARCH_SNAPSHOT_2026-11-09.md) | **P136.2 architecture snapshot**: `--from-snapshot` |
| [validation/P136_TB_JOIN_2026-11-09.md](validation/P136_TB_JOIN_2026-11-09.md) | **P136.3 TB join**: candidate/ambiguous；I2C 实测 |
| [validation/P136_UNKNOWN_FLAG_2026-11-09.md](validation/P136_UNKNOWN_FLAG_2026-11-09.md) | **P136.4 unknown flag**: machine-readable unknown_kind |
| [validation/DISCIPLINE_AUDIT_2026-11-09.md](validation/DISCIPLINE_AUDIT_2026-11-09.md) | **Discipline audit remediation**: F1–F14 修复 |
| [validation/P138_PROJECT_ADAPTATION_2026-11-09.md](validation/P138_PROJECT_ADAPTATION_2026-11-09.md) | **P138**: 删除自动 FIFO；外部 adapter 模板 |
| [validation/P136_SOLVE_DIST_2026-11-09.md](validation/P136_SOLVE_DIST_2026-11-09.md) | **P136.5 solve/dist**: `solve_before` + `dist` |
| [validation/opentitan_intake/REPORT.md](validation/opentitan_intake/REPORT.md) | **P124 intake**: 3 个 OpenTitan DV 任务；discovery/verify/path |
| [validation/opentitan_uart/WORKER_REPORT.md](validation/opentitan_uart/WORKER_REPORT.md) | **P118 worker onboarding**: filelist/snapshot/tasks/11 issues |
| [validation/COMPARISON_RECORD_2026-11-05.md](validation/COMPARISON_RECORD_2026-11-05.md) | **对比结果冻结记录**: 哈希、模型、指标、单独复验脚本与已知缺陷 |
| [validation/long_range_12_usage_2026-11-05.json](validation/long_range_12_usage_2026-11-05.json) | **token/tool-call 汇总**: 四臂 token、tool calls、tokens/correct |
| [architecture/long_range_structural_benchmark_2026-11-05.md](architecture/long_range_structural_benchmark_2026-11-05.md) | **长程结构查询对照基准**: B0/B1/T1/T2 对照、任务族、ground truth 冻结与准确度/成本指标 |
| [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) | 已知限制 (含 pyslang 侧限制) |
| [EXTRACTION_COVERAGE.md](EXTRACTION_COVERAGE.md) | SV 语法抽取覆盖率总表 (逐语法 ✅/⚠️/❌) |
| [EXTRACTION_FAILURES.md](EXTRACTION_FAILURES.md) | 提取失败路径集中表 |

## 🏗️ 架构

| 文档 | 作用 |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 架构总览 (四层 L1-L4) ⚠️ **部分过期**, 见 `CLI_SURFACE.md`/iter_230 |
| [CLI_SURFACE.md](CLI_SURFACE.md) | **CLI 能力清单 (生成物, 勿手改)** — 分层/契约/成本/`--json`/filelist; `tools/gen_cli_surface.py` 重新生成 |
| [EXP_NAMESPACE.md](EXP_NAMESPACE.md) | **exp 降级区政策** — 五条硬约束 + 晋升门槛 (含 cdc/timing 专项) |
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
| [VISUALIZATION.md](VISUALIZATION.md) | ⚠️ 历史: V5 可视化总览（全图命令已退役） |
| [VIZ_COMMANDS.md](VIZ_COMMANDS.md) | ⚠️ 历史: 画图命令参考（命令已删除） |
| [VIZ_DESIGN_SPEC.md](VIZ_DESIGN_SPEC.md) | ⚠️ 历史: 可视化设计规范 v2.0（旧渲染层） |
| [VIZ_GOLDEN_PLAN.md](VIZ_GOLDEN_PLAN.md) | ⚠️ 历史: VIZ golden 计划（已停） |

## 📖 使用与参考

| 文档 | 作用 |
|---|---|
| [USER_GUIDE.md](USER_GUIDE.md) | 用户指南 |
| [CLI_COMMAND_CHEATSHEET.md](CLI_COMMAND_CHEATSHEET.md) | CLI 速查 |
| [ARCH_EXAMPLES.md](ARCH_EXAMPLES.md) | arch 命令实战案例 |
| [SIGNAL_TRACING_EXAMPLES.md](SIGNAL_TRACING_EXAMPLES.md) | 信号追踪实战案例 |
| [FILELIST.md](FILELIST.md) | filelist 格式支持 |
| [TEST_MAP.md](TEST_MAP.md) | 全量测试地图 |
| [GLOSSARY.md](GLOSSARY.md) | **术语表** (领域术语的唯一命名处: 分层/查询/门禁/工具四组) |
| [BENCH_BASELINE.md](BENCH_BASELINE.md) | bench 深结构基准 (pr5_wrap: 真实 Cfg wrapper + 指标表 + 已知限制) |
| [OPENTITAN_HOWTO.md](OPENTITAN_HOWTO.md) | OpenTitan 跑通 HOWTO |
| [NAPLESPU_HOWTO.md](NAPLESPU_HOWTO.md) | NaplesPU 跑通 HOWTO |
| [PROJECT_PLAN.md](PROJECT_PLAN.md) | 开源 RTL 验证问题生成计划 (独立工作流) |
| [TODO.md](TODO.md) | 版本级功能待办 (月~季) |

## 📓 记录类 (按 [WORKFLOW §0.1](dev/WORKFLOW.md) 设施表)

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
| [refactoring/2026-10-19_core_smell_review.md](refactoring/2026-10-19_core_smell_review.md) | **核心代码坏味道评审 + CLI 减法方案** (2026-10-19, 带 P0~P3 严重度) |
| [refactoring/2026-06-26_b-phase_1-2_baseline.md](refactoring/2026-06-26_b-phase_1-2_baseline.md) | B-Phase 1-2 基线 |
| [debugging_lessons/2026-08-25_picorv32_render_tree_cycle.md](debugging_lessons/2026-08-25_picorv32_render_tree_cycle.md) | 调试案例: 渲染树递归 |
| [debugging_lessons/2026-08-25_plan_b_step_g_picorv32_wb_port.md](debugging_lessons/2026-08-25_plan_b_step_g_picorv32_wb_port.md) | 调试案例: ELK dangling port |
| [archive/2026-09-08-cleanup/README.md](archive/2026-09-08-cleanup/README.md) | **归档区** (过期报告 / 重复稿 — 只归档不删除) |
| [archive/2026-10-20-exp-attic/README.md](archive/2026-10-20-exp-attic/README.md) | **归档区**: exp 区整体退役 (24 命令 + applications 库 + 30 测试文件) |
| [archive/2026-10-19-src-archived/README.md](archive/2026-10-19-src-archived/README.md) | **归档区**: `src/` 内 19 个死代码文件 (旧 DOT 渲染器 / 孤立模块 4,273 行 — iter_245) |
| [archive/README_legacy.md](archive/README_legacy.md) | 早期归档 (2026-07 前) |

---

## 🧹 文档卫生规则 (强制, 细则见 [dev/WORKFLOW.md §3](dev/WORKFLOW.md))

1. **新增文档必须登记在本文件** — `tools/check_docs.py` 检查 (未登记 = 失败)。
2. **过期报告 / 被取代的稿子 → 归档不删** — 移到 `docs/archive/<日期>-cleanup/`,
   并在该目录 `README.md` 说明原因 (信息不丢, 历史可追)。
3. **计数只写在"当前基线"一节** — 其他文档引用本表, 不写死 passed 数。
4. **提交前跑** `python3 tools/check_docs.py` — 死链 / 归档越界 / 未登记 三项必须 ✅。
