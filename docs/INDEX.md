# sv_query 文档索引 (DOCS INDEX)

> **唯一文档入口** — 所有文档从本文件进入;新增文档必须在本文件登记
> (由 `tools/check_docs.py` 强制检查)。
> **最后整理**: 2026-11-21（公开仓库裁剪；历史记录已移入私有归档）。

---

## 📌 当前基线 (单一真相源 — 计数只写在这里)

| 项 | 值 | 说明 |
|---|---|---|
| 源码规模 | 159 文件 / 53,548 行 | `find src -name "*.py"`（2026-11-16 实测） |
| 测试规模 | 489 测试文件 / 73,410 行 + 192 SV fixture | `find sim/tests -name "*.py"` / `-name "*.sv"`（2026-11-16 实测） |
| 全量 (canonical) | **3373 passed / 0 failed** ✅ (`sim/tests/`, `-m "not opensource"`; **0 skipped** / **0 unexecuted** / 123 `deferred` (opensource suite); 35 subtests) | **2026-11-26 P197.10 全量复核（3373）**（本机；deferred 口径）。**0 skipped 与 0 failed 都不是健康指标**，状态口径见 TESTING §语义测试 |
| CLI / integration 子集 | 不再单独维护 | 旧 `2129` / `810` 是 2026-09-08 的子集快照，已过期；一律看全量行 |
| 缓存目录 | 可用 `SVQ_CACHE_DIR` 覆盖 (默认顺序: 显式 > env > `$XDG_CACHE_HOME/svq` > `~/.svq/cache`); 不可写自动降级内存缓存 | iter_172 |
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
| [RELEASE.md](../RELEASE.md) | PyPI 发布清单 / 校验 / 回滚 |

## 🛠️ 开发纪律与流程 (`docs/dev/` — 细则层)

> 入口在 [AGENTS.md](../AGENTS.md)；本节是它链接到的细则文件。
> 规则变更必须**同一次改动**里同步检查器或测试。

| 文档 | 作用 |
|---|---|
| [dev/SEMANTIC_CONTRACTS.md](dev/SEMANTIC_CONTRACTS.md) | **语义契约**: 数据边 / 路径 / verified / snapshot / 完成判定 |
| [dev/SNAPSHOT_SURFACE.md](dev/SNAPSHOT_SURFACE.md) | **快照能力面矩阵 (P158.9.2)**: 字段级保真 / 命令级支持面 / 显式不保证清单 |
| [dev/CLAIMS.md](dev/CLAIMS.md) | **claim 台账**: 公开能力的证据与状态 |
| [dev/CODING_STYLE.md](dev/CODING_STYLE.md) | 编码风格与设计决策: 先探索后决策 / 单一实现 / 修根因 / 函数职责 / 结构化数据 / 影响面 / 协作规则 |
| [dev/LOCAL_GRAPH_SESSION.md](dev/LOCAL_GRAPH_SESSION.md) | **P194.2d**: GraphSession + stdio graph server + snapshot hydrate |
| [dev/WIDTH_CONVENTION.md](dev/WIDTH_CONVENTION.md) | **P195.3**: scalar width `(0,0)` / width 1; `[1:0]` remains width 2 |
| [validation/reviews/2026-11-24_36b0a0d.md](validation/reviews/2026-11-24_36b0a0d.md) | **P197.4** initial review: FAIL (x/z shift literal P1) |
| [validation/reviews/2026-11-24_618cc16.md](validation/reviews/2026-11-24_618cc16.md) | **P198.2** initial review: FAIL (unary minus / element select) |
| [validation/reviews/2026-11-24_5c396b2.md](validation/reviews/2026-11-24_5c396b2.md) | **P198.3** initial review: FAIL (instance-path IR attach) |
| [validation/reviews/2026-11-24_d594e4d.md](validation/reviews/2026-11-24_d594e4d.md) | **P198.4** initial review: FAIL (legacy concat fallback/dynamic select) |
| [validation/reviews/2026-11-24_d4fe6c3.md](validation/reviews/2026-11-24_d4fe6c3.md) | **P198.5** initial review: FAIL (gate/IR fallback/scope) |
| [validation/reviews/2026-11-25_f4e7e9f.md](validation/reviews/2026-11-25_f4e7e9f.md) | **P198.6** initial review: FAIL (false migration claim) |
| [validation/reviews/2026-11-25_57011a0.md](validation/reviews/2026-11-25_57011a0.md) | **P198.8** initial review: FAIL (little-endian reversed; single-bit refs) |
| [validation/reviews/2026-11-25_703148a.md](validation/reviews/2026-11-25_703148a.md) | **P198.8** re-audit: FAIL (descending split lost per-bit) |
| [validation/reviews/2026-11-25_7e66098.md](validation/reviews/2026-11-25_7e66098.md) | **P198.10c** audit: PASS WITH CAVEATS; depth=1 duplicate aggregate |
| [validation/reviews/2026-11-26_5c5e9d8.md](validation/reviews/2026-11-26_5c5e9d8.md) | **P197.13** first audit: FAIL; ascending slice P1 |
| [validation/reviews/2026-11-26_9057ba7.md](validation/reviews/2026-11-26_9057ba7.md) | **P197.13** re-audit: FAIL; descending slice P1 |
| [validation/reviews/2026-11-27_586bc4fd.md](validation/reviews/2026-11-27_586bc4fd.md) | **P197.23** first audit: FAIL; array width mutation dropped driver |
| [validation/reviews/2026-11-27_201df6e9.md](validation/reviews/2026-11-27_201df6e9.md) | **P197.24** worker review: PASS WITH CAVEATS; array precision/cache; P197 complete |
| [validation/reviews/2026-11-27_916002aa.md](validation/reviews/2026-11-27_916002aa.md) | **P197.23** re-audit: PASS WITH CAVEATS; P1 closed |
| [validation/reviews/2026-11-27_45e14fb0.md](validation/reviews/2026-11-27_45e14fb0.md) | **P197.22** worker review: PASS WITH CAVEATS; unpacked array range |
| [validation/reviews/2026-11-26_e0b76e49.md](validation/reviews/2026-11-26_e0b76e49.md) | **P197.21** worker review: PASS WITH CAVEATS; IR/cache version bump |
| [validation/reviews/2026-11-26_d162812a.md](validation/reviews/2026-11-26_d162812a.md) | **P197.20** worker review: PASS WITH CAVEATS; out-of-graph parity/CC |
| [validation/reviews/2026-11-26_df994b8e.md](validation/reviews/2026-11-26_df994b8e.md) | **P197.19** worker review: PASS WITH CAVEATS; nested shift inverse |
| [validation/reviews/2026-11-26_30f0b8ec.md](validation/reviews/2026-11-26_30f0b8ec.md) | **P197.18** worker review: PASS WITH CAVEATS; literal driver crash fixed |
| [validation/reviews/2026-11-26_76857a21.md](validation/reviews/2026-11-26_76857a21.md) | **P197.17** worker review: PASS WITH CAVEATS; sign-fill closed |
| [validation/reviews/2026-11-26_c903078f.md](validation/reviews/2026-11-26_c903078f.md) | **P197.16** worker review: PASS WITH CAVEATS; depth/confidence/cache env |
| [validation/reviews/2026-11-26_e64f1c89.md](validation/reviews/2026-11-26_e64f1c89.md) | **P197.15** worker review: PASS WITH CAVEATS; cache CC/privacy/except policy |
| [validation/reviews/2026-11-26_281ab86c.md](validation/reviews/2026-11-26_281ab86c.md) | **P197.14** worker review: PASS WITH CAVEATS; evidence reset/RHS tokens |
| [validation/reviews/2026-11-26_a0b2c73f.md](validation/reviews/2026-11-26_a0b2c73f.md) | **P197.13** re-audit 2: PASS WITH CAVEATS; both slice P1s closed |
| [validation/reviews/2026-11-26_e65b5a2.md](validation/reviews/2026-11-26_e65b5a2.md) | **P197.12** worker review: PASS WITH CAVEATS; verify parity P2s closed |
| [validation/reviews/2026-11-25_37bed29.md](validation/reviews/2026-11-25_37bed29.md) | **P197.10** worker review: PASS WITH CAVEATS; claims/audit reconciliation |
| [validation/reviews/2026-11-25_e16240f.md](validation/reviews/2026-11-25_e16240f.md) | **P197.9** worker review: PASS WITH CAVEATS; semantic bit/gate |
| [validation/reviews/2026-11-25_5e7789d.md](validation/reviews/2026-11-25_5e7789d.md) | **P197.8** worker review: PASS WITH CAVEATS; quiet context/argv |
| [validation/reviews/2026-11-25_cf5cb44.md](validation/reviews/2026-11-25_cf5cb44.md) | **P197.7** worker review: PASS WITH CAVEATS; MIG cache round-trip |
| [validation/reviews/2026-11-25_12f312d.md](validation/reviews/2026-11-25_12f312d.md) | **P197.6** worker review: PASS WITH CAVEATS; real alias fixture restores C-64 |
| [validation/reviews/2026-11-25_c20796a.md](validation/reviews/2026-11-25_c20796a.md) | **P197.5** worker review: PASS WITH CAVEATS; reset/evidence P1s closed |
| [validation/reviews/2026-11-25_360706f.md](validation/reviews/2026-11-25_360706f.md) | **P198.11** worker review: PASS WITH CAVEATS; concat IR enabled |
| [validation/reviews/2026-11-25_f55fb94.md](validation/reviews/2026-11-25_f55fb94.md) | **P198.10c** re-audit: PASS WITH CAVEATS; depth caveat closed |
| [validation/reviews/2026-11-25_21722a6.md](validation/reviews/2026-11-25_21722a6.md) | **P198.9** worker review: PASS WITH CAVEATS; scoped Slice/Cast/Ternary |
| [validation/reviews/2026-11-25_03073e4.md](validation/reviews/2026-11-25_03073e4.md) | **P198.8** final re-audit: PASS WITH CAVEATS |
| [validation/reviews/2026-11-25_e3a14b8.md](validation/reviews/2026-11-25_e3a14b8.md) | **P198.7** worker review: PASS WITH CAVEATS; generate IR refs |
| [validation/reviews/2026-11-25_809f041.md](validation/reviews/2026-11-25_809f041.md) | **P198.6** re-audit: PASS WITH CAVEATS; P1 closed, R1/R2 text fixed |
| [validation/reviews/2026-11-24_c3e8e9f.md](validation/reviews/2026-11-24_c3e8e9f.md) | **P198.5** final review: PASS; shift-only scope complete |
| [validation/reviews/2026-11-24_22c4f2a.md](validation/reviews/2026-11-24_22c4f2a.md) | **P198.5** re-audit: PASS WITH CAVEATS; P1s closed; parity/P198.9 remain |
| [validation/reviews/2026-11-24_c8c31ef.md](validation/reviews/2026-11-24_c8c31ef.md) | **P198.4** re-audit: PASS WITH CAVEATS; F1/F2 closed |
| [validation/reviews/2026-11-24_a163963.md](validation/reviews/2026-11-24_a163963.md) | **P198.3** re-audit: PASS WITH CAVEATS; F1 closed |
| [validation/reviews/2026-11-24_c2b13b7.md](validation/reviews/2026-11-24_c2b13b7.md) | **P198.2** re-audit: PASS WITH CAVEATS; P1s closed |
| [validation/reviews/2026-11-24_1817145d.md](validation/reviews/2026-11-24_1817145d.md) | **P198.1** independent worker review: PASS WITH CAVEATS; P2 strictness/tests fixed |
| [validation/reviews/2026-11-24_99c243f.md](validation/reviews/2026-11-24_99c243f.md) | **P197.4** re-audit: PASS WITH CAVEATS; P1 closed |
| [validation/reviews/2026-11-24_353d687a.md](validation/reviews/2026-11-24_353d687a.md) | **P197.3** independent worker review: PASS WITH CAVEATS (P2-1 fixed post-review) |
| [validation/reviews/2026-11-23_229320f.md](validation/reviews/2026-11-23_229320f.md) | **P197.2** independent worker review: PASS WITH CAVEATS (P2 only) |
| [validation/reviews/2026-11-23_7250285.md](validation/reviews/2026-11-23_7250285.md) | **P197.1** independent worker review: PASS WITH CAVEATS (P2 only) |
| [validation/reviews/README.md](validation/reviews/README.md) | **P197**: worker review artifact location; no P0/P1 open rule |
| [dev/EXPRESSION_IR.md](dev/EXPRESSION_IR.md) | **P198**: typed semantic expression DAG, concat layout, migration contract |
| [dev/CODE_REVIEW_PROTOCOL.md](dev/CODE_REVIEW_PROTOCOL.md) | **P197**: worker-only review, P0/P1 rework/re-audit, release blocking |
| [dev/API_FACADE.md](dev/API_FACADE.md) | **P194.3**: QueryClient/Session/GraphSession tiers; deprecation policy |
| [dev/CACHE_CONTRACT.md](dev/CACHE_CONTRACT.md) | **P194.2a**: BuildIdentity/capability manifest; cache default-off; invalidation rules |
| [dev/WIDE_EXCEPT_AUDIT.md](dev/WIDE_EXCEPT_AUDIT.md) | **P193.4**: 核心查询路径宽 except 审计 + 静态门禁；无静默空结果 |
| [dev/REPOSITORY_LAYOUT.md](dev/REPOSITORY_LAYOUT.md) | **开发位置规则**: public 是唯一开发主线；private 是冻结归档 |
| [dev/P193_ASSET_INVENTORY.md](dev/P193_ASSET_INVENTORY.md) | **P193.2**: 私有资产清单、迁移规则、git 历史策略待确认 |
| [dev/REPO_HYGIENE.md](dev/REPO_HYGIENE.md) | **P193.1**: 禁止 tracked absolute-path symlink；clone/Windows 安全 |
| [dev/BIT_SELECT_HINTS.md](dev/BIT_SELECT_HINTS.md) | **P191**: drivers/loads + dataflow 双向 bit-select hint 契约；false/empty 语义不变 |
| [dev/COMMAND_SURFACE_RATCHET.md](dev/COMMAND_SURFACE_RATCHET.md) | **P185.4**: 45/39/2/32/13 命令面 baseline；增删/别名/可见性漂移 gate |
| [dev/ENVELOPE_INVENTORY.md](dev/ENVELOPE_INVENTORY.md) | **P182.1a**: 45 命令 envelope 只读盘点；32 standard（26 core + 6 exp）/ 13 direct；snapshot list 根类型不一致；P182.1b 增加 7-case canary gate；P182.1c 增加 26-case core standard 成功矩阵（当前 26 PASS） |
| [dev/ENVELOPE_FAILURE_INVENTORY.md](dev/ENVELOPE_FAILURE_INVENTORY.md) | **P182.1d**: 26 个 core standard 各一条最小失败输入；只读观测 rc/ok/error_code/errors/result；当前 22 operational rc1 + 4 business rc0/okfalse；不是 gate |
| [dev/ENVELOPE_STATS_COMPLETENESS.md](dev/ENVELOPE_STATS_COMPLETENESS.md) | **P182.3**: stats 成功无 elaboration errors；malformed JSON 结构化失败；stats-completeness gate |
| [dev/ENVELOPE_RESULT_TYPES.md](dev/ENVELOPE_RESULT_TYPES.md) | **P182.2c/2d**: 26 个 core standard 顶层值类型/enum + 2 变体；28/28 PASS |
| [dev/ENVELOPE_RESULT_SCHEMA.md](dev/ENVELOPE_RESULT_SCHEMA.md) | **P182.2b**: 26 个 core standard 的 result 必需键 schema；optional fields 已登记 |
| [dev/ENVELOPE_JSON_SCHEMA.md](dev/ENVELOPE_JSON_SCHEMA.md) | **P182.2**: 从 JSON_CONTRACT 生成 standard success 顶层 schema；26/26 matrix 可执行校验 |
| [dev/ENVELOPE_DIRECT_CONTRACT.md](dev/ENVELOPE_DIRECT_CONTRACT.md) | **P182.1e**: 13 个 direct 命令的显式根契约；snapshot list 双根；静态 direct-contract gate |
| [dev/ENVELOPE_FAILURE_CONTRACT.md](dev/ENVELOPE_FAILURE_CONTRACT.md) | **P182.1f**: 严格失败契约（非 allowlist 必须 rc1+okfalse）；恰好 4 条 hybrid 例外（drivers/loads/trace evidence/trace profile，rc0+okfalse+E_SIGNAL_NOT_FOUND）；`--matrix-failure` gate 当前 26/26 PASS |
| [dev/PROJECT_ADAPTATION.md](dev/PROJECT_ADAPTATION.md) | **项目适配理念**: core 不自动推断特定项目；外部 adapter 模板 |
| [agent/GUIDED_TRACE.md](agent/GUIDED_TRACE.md) | **P139 guided trace**: frontier + next probes；不分类 FIFO |
| [agent/CAPABILITIES_GENERATED.md](agent/CAPABILITIES_GENERATED.md) | **P182.4**: 从 `capabilities --json` 生成的 39 core 命令索引；gate `gen_agent_skill.py --check` |
| [agent/AGENT_FEATURE_MAP.md](agent/AGENT_FEATURE_MAP.md) | **P143 历史快照**（P182.4 起由 [CAPABILITIES_GENERATED](agent/CAPABILITIES_GENERATED.md) 取代） |
| [agent/AGENT_TASK_CORPUS.md](agent/AGENT_TASK_CORPUS.md) | **P145**: 15 个可执行 agent 任务 + false-confident/found 指标 |
| [validation/CODE_SMELL_AUDIT_2026-11-23.md](validation/CODE_SMELL_AUDIT_2026-11-23.md) | **P197**: verify/cache/semantic heuristics audit; P194.5d blocked |
| [validation/P19810_PART_SELECT_2026-11-25.md](validation/P19810_PART_SELECT_2026-11-25.md) | **P198.10** part-select investigation; fix split into 10a/10b/10c |
| [validation/P1945_AUDIT_2026-11-23.md](validation/P1945_AUDIT_2026-11-23.md) | **P194.5 audit**: P1 compact/controlflow/paths defects; P194.5d blocked |
| [validation/P1945_LOCAL_MEASURE_2026-11-23.md](validation/P1945_LOCAL_MEASURE_2026-11-23.md) | **P194.5**: local 3-corpus session/cache/token evidence; explicitly not external |
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
| [validation/P165_4_FILECLOSURE_2026-11-12.md](validation/P165_4_FILECLOSURE_2026-11-12.md) | **P165.4**: .core closure; UART/I2C/SPI 0 elaboration errors |
| [validation/P165_3_EXTERNAL_ORACLE_2026-11-12.md](validation/P165_3_EXTERNAL_ORACLE_2026-11-12.md) | **P165.3.1**: independent Verilator oracle; no OpenTitan git history |
| [validation/P165_3_2_MUTATION_FAULTS_2026-11-12.md](validation/P165_3_2_MUTATION_FAULTS_2026-11-12.md) | **P165.3.2**: mutation pilot; 4/4 passed with Verilator oracle |
| [validation/P165_2_PACKAGING_2026-11-13.md](validation/P165_2_PACKAGING_2026-11-13.md) | **P165.2**: trace→sv_query.trace; wheel/console verified |
| [validation/P171_CI_EVIDENCE_2026-11-13.md](validation/P171_CI_EVIDENCE_2026-11-13.md) | **P171**: hermeticity + structural coverage; CI green at 4d58d7fb (CLAIMS C-16) |
| [validation/P171_4_DRIVERS_CONTROL_2026-11-14.md](validation/P171_4_DRIVERS_CONTROL_2026-11-14.md) | **P171.4.1**: drivers include-clock/reset |
| [validation/P171_5_DESELECTED_METRIC_2026-11-14.md](validation/P171_5_DESELECTED_METRIC_2026-11-14.md) | **P171.5**: 123 deselected are opensource tests |
| [validation/P171_6_BENCHMARK_FAIL_2026-11-14.md](validation/P171_6_BENCHMARK_FAIL_2026-11-14.md) | **P171.6**: benchmark rc -> fail; timeout skip |
| [validation/P171_7_RISK_MODEL_2026-11-14.md](validation/P171_7_RISK_MODEL_2026-11-14.md) | **P171.7**: dataflow risk_model label |
| [validation/P171_4_2_MERGE_ATTEMPT_2026-11-14.md](validation/P171_4_2_MERGE_ATTEMPT_2026-11-14.md) | **P171.4.2**: attempted merge, reverted (CC=32) |
| [validation/P171_4_2_FULL_MERGE_2026-11-14.md](validation/P171_4_2_FULL_MERGE_2026-11-14.md) | **P171.4.2**: merged facts/formatter; worker PASS WITH NITS |
| [validation/P62_2_INTERACTIVE_DEBUG_GATE_2026-11-14.md](validation/P62_2_INTERACTIVE_DEBUG_GATE_2026-11-14.md) | **P62.2**: gate blocked; no review-time/session evidence |
| [validation/P173_STATUS_CLEANUP_2026-11-15.md](validation/P173_STATUS_CLEANUP_2026-11-15.md) | **P173**: CLI/exp truth + status docs + zombie test cleanup |
| [validation/P174_REVIEW_FIXES_2026-11-15.md](validation/P174_REVIEW_FIXES_2026-11-15.md) | **P174**: independent review follow-up |
| [validation/P175_SKILL_REWRITE_2026-11-15.md](validation/P175_SKILL_REWRITE_2026-11-15.md) | **P175**: skill rewrite from 64 short/long tasks |
| [validation/P176_SKILL_REVIEW_FIXES_2026-11-15.md](validation/P176_SKILL_REVIEW_FIXES_2026-11-15.md) | **P176**: skill re-review fixes |
| [validation/P177_SKILL_CORPUS_FIDELITY_2026-11-15.md](validation/P177_SKILL_CORPUS_FIDELITY_2026-11-15.md) | **P177**: paths/driver_count/evidence/class corpus fidelity |
| [validation/P178_PRODUCT_FIXES_2026-11-15.md](validation/P178_PRODUCT_FIXES_2026-11-15.md) | **P178**: consistency/evidence/error fixes |
| [validation/P179_CONTROL_EVIDENCE_2026-11-16.md](validation/P179_CONTROL_EVIDENCE_2026-11-16.md) | **P179**: control alias + evidence source text |
| [validation/P180_NIT_CLEANUP_2026-11-16.md](validation/P180_NIT_CLEANUP_2026-11-16.md) | **P180**: shared assignment scanner + nit cleanup |
| [validation/P180_WORKER_REVIEW_2026-11-16.md](validation/P180_WORKER_REVIEW_2026-11-16.md) | **P180**: worker review record |
| [validation/P181_DISCIPLINE_REMEDIATION_2026-11-16.md](validation/P181_DISCIPLINE_REMEDIATION_2026-11-16.md) | **P181**: discipline remediation |
| [validation/P172_1_COVERAGE_GEN_RETIRE_2026-11-14.md](validation/P172_1_COVERAGE_GEN_RETIRE_2026-11-14.md) | **P172.1**: retire stale coverage-gen workflow |
| [validation/P172_2_CHECK_CRAP_BASE_2026-11-14.md](validation/P172_2_CHECK_CRAP_BASE_2026-11-14.md) | **P172.2**: local gate defaults --base HEAD~1 |
| [validation/P171_6_2_MUTATION_GATE_2026-11-14.md](validation/P171_6_2_MUTATION_GATE_2026-11-14.md) | **P171.6.2**: 20-task repo-only mutation gate |
| [validation/P171_8_DOCS_CLAIMS_2026-11-14.md](validation/P171_8_DOCS_CLAIMS_2026-11-14.md) | **P171.8**: 17→9; 132→9+123 deferred; claims |
| [validation/P171_7_2_ROLE_SOURCE_2026-11-14.md](validation/P171_7_2_ROLE_SOURCE_2026-11-14.md) | **P171.7.2**: audit role_source=name_heuristic |
| [validation/P171_9_REVIEW_FIX_2026-11-14.md](validation/P171_9_REVIEW_FIX_2026-11-14.md) | **P171.9**: worker review fixes; opensource 112/11/0 |
| [validation/P165_3_3_MUTATION_COVERAGE_2026-11-13.md](validation/P165_3_3_MUTATION_COVERAGE_2026-11-13.md) | **P165.3.3**: 10 mutation tasks; driver/path/condition/CDC/bit |
| [validation/P165_3_4_MUTATION_COVERAGE_2026-11-13.md](validation/P165_3_4_MUTATION_COVERAGE_2026-11-13.md) | **P165.3.4**: 14 mutations; detection_rate/by_query |
| [validation/P165_3_5_MUTATION_COVERAGE_2026-11-13.md](validation/P165_3_5_MUTATION_COVERAGE_2026-11-13.md) | **P165.3.5**: 20 mutations; multi/generate/wrapper/case |
| [validation/P165_3_6_MULTI_DRIVER_CONFLICT_2026-11-13.md](validation/P165_3_6_MULTI_DRIVER_CONFLICT_2026-11-13.md) | **P165.3.6**: driver_count/multi_driver/driver_conflict mutation |
| [validation/REVIEW_2026-11-11.md](validation/REVIEW_2026-11-11.md) | **P158 输入**: 4-angle review + 28 项修复账本 |
| [validation/P139_FRONTIER_2026-11-09.md](validation/P139_FRONTIER_2026-11-09.md) | **P139 frontier**: 断点 + next probes；不分类 FIFO |
| [validation/P139_WORKER_REVIEW_2026-11-09.md](validation/P139_WORKER_REVIEW_2026-11-09.md) | **P139 worker review**: APPROVE WITH NITS；nits 已修 |
| [validation/P140_GUIDED_BOUNDARY_2026-11-09.md](validation/P140_GUIDED_BOUNDARY_2026-11-09.md) | **P140**: 显式 boundary map 跑通 I2C S1 |
| [validation/P140_WORKER_REVIEW_2026-11-09.md](validation/P140_WORKER_REVIEW_2026-11-09.md) | **P140 worker review**: APPROVE WITH NITS；nits 已修 |
| [validation/P141_DEEP_PATHS_2026-11-09.md](validation/P141_DEEP_PATHS_2026-11-09.md) | **P141**: 三模块深层 from/to |
| [validation/P142_CONSTRAINT_CHAIN_2026-11-09.md](validation/P142_CONSTRAINT_CHAIN_2026-11-09.md) | **P142**: random 变量 constraint 链 |

## 📜 能力与边界 (对外声明)

| 文档 | 作用 |
|---|---|
| [PRIMARY_FEATURES.md](PRIMARY_FEATURES.md) | 主推功能: 查询/追踪/校验（visualize 已退役） |
| [EXPERIMENTAL_FEATURES.md](EXPERIMENTAL_FEATURES.md) | **当前 exp 层**: 6 个 hidden 直接命令，无 `svq exp` 统一入口 |
| [EXP_IDEAS.md](EXP_IDEAS.md) | **exp 创意清单 (未落地)**: 10 条想法 + 各自要解决的问题场景 |
| [EXP_NAMESPACE.md](EXP_NAMESPACE.md) | **当前 exp 层**: 6 个 hidden 直接命令；`svq exp` 统一入口已退役 |
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
| [architecture/agent_interface_review_2026-11-16_revised.md](architecture/agent_interface_review_2026-11-16_revised.md) | **面向 agent 的交付层评审 v2（2026-11-16，HEAD `8da675b3`）**: 修正 v1 的 direct/缺参/计数错误；只读评审，建议已登记 P182 |
| [architecture/dto_mapping_audit_2026-11-17.md](architecture/dto_mapping_audit_2026-11-17.md) | **DTO 映射审计（D9 / P183.3）**: snapshot/CLI/core 精确字段集；每上下文一份 canonical projection，不做全局合并 |
| [architecture/p1834_session_seam_decision_2026-11-17.md](architecture/p1834_session_seam_decision_2026-11-17.md) | **P183.4 决策（D15）**: 保留 Session/runner/hidden session；不重写 Typer run() 全量 dispatch |
| [architecture/p1942_cold_start_investigation_2026-11-21.md](architecture/p1942_cold_start_investigation_2026-11-21.md) | **P194.2**: cold-start benchmark; graph cache narrow; snapshot 0.6–0.8s after 46s build |
| [architecture/p1861_shadow_measure_2026-11-19.md](architecture/p1861_shadow_measure_2026-11-19.md) | **P186.1**: 5 fixture 实测 shadow=0；不新增 drop_shadows，保留测量工具 |
| [architecture/p1825_snapshot_cache_session_eval.md](architecture/p1825_snapshot_cache_session_eval.md) | **P182.5**: 13 个命令暴露 --from-snapshot（12 可源替代；tb-join 仍需 TB 源）；不扩 source-dependent / 不做 serve / 不改 cache 默认 |
| [architecture/p1835_candidate_decision_2026-11-18.md](architecture/p1835_candidate_decision_2026-11-18.md) | **P183.5 决策**: DesignView 拒绝全量；ASTFrontend 仅采纳 Phase 0（inventory + degraded） |
| [architecture/agent_review_2026-11-18_intake.md](architecture/agent_review_2026-11-18_intake.md) | **2026-11-18 review intake**: 事实核对；采纳 P185–P190，拒绝旧快照数字与 CLI 压到 10 条 |
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
| [validation/p187_cva6_2026-11-19/README.md](validation/p187_cva6_2026-11-19/README.md) | **P187 local archive**: CVA6 parent/fix blobs, portable filelists, scripts, results, checksums |
| [validation/P187_VALUE_CASES_CVA6_2026-11-19.md](validation/P187_VALUE_CASES_CVA6_2026-11-19.md) |
| [validation/P187_FOLLOWUPS_2026-11-19.md](validation/P187_FOLLOWUPS_2026-11-19.md) |
| [validation/P192_blind_3404/README.md](validation/P192_blind_3404/README.md) |
| [validation/P192_blind_3404/TASK.md](validation/P192_blind_3404/TASK.md) |
| [validation/P192_BLIND_COMPARE_2026-11-20.md](validation/P192_BLIND_COMPARE_2026-11-20.md) |
| [validation/p192_blind_compare_2026-11-20/source_only/ANSWER.md](validation/p192_blind_compare_2026-11-20/source_only/ANSWER.md) | **P192.2 source-only** 盲解答案与证据 |
| [validation/p192_blind_compare_2026-11-20/sv_query/ANSWER.md](validation/p192_blind_compare_2026-11-20/sv_query/ANSWER.md) | **P192.2 sv_query** 盲解答案与证据 | **P192.2**: source-only vs sv_query 盲对照；两臂精确 root cause，sv_query 最小 patch，source-only 动态验证 |
 **P192.1 blind task**: issue #3404 symptom-only task statement（无 fix） |
 **P192.1 blind package**: issue #3404 symptom-only, parent RTL, portable filelist, checksums |
 **P187 follow-ups**: bit-select 查询、dataflow unknown、evidence source、snapshot/filelist 建议 |
 **P187 CVA6 value cases**: 2 个历史 fix 的 grep vs sv_query 对照；位选下钻命中 / 总线级漏报 |
| [architecture/long_range_structural_benchmark_2026-11-05.md](architecture/long_range_structural_benchmark_2026-11-05.md) | **长程结构查询对照基准**: B0/B1/T1/T2 对照、任务族、ground truth 冻结与准确度/成本指标 |
| [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) | 已知限制 (含 pyslang 侧限制) |
| [EXTRACTION_COVERAGE.md](EXTRACTION_COVERAGE.md) | SV 语法抽取覆盖率总表 (逐语法 ✅/⚠️/❌) |
| [EXTRACTION_FAILURES.md](EXTRACTION_FAILURES.md) | 提取失败路径集中表 |

## 🏗️ 架构

| 文档 | 作用 |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 架构总览 (四层 L1-L4) ⚠️ **部分过期**, 见 `CLI_SURFACE.md`/iter_230 |
| [CLI_SURFACE.md](CLI_SURFACE.md) | **CLI 能力清单 (生成物, 勿手改)** — 分层/契约/成本/`--json`/filelist; `tools/gen_cli_surface.py` 重新生成 |
| [ARCHITECTURE_EVOLUTION.md](ARCHITECTURE_EVOLUTION.md) | 架构演进历史 |
| [SIGNAL_GRAPH_SPEC.md](SIGNAL_GRAPH_SPEC.md) | SignalGraph 输入输出 Spec |
| [SV_SYNTAX_MAPPING.md](SV_SYNTAX_MAPPING.md) | SV 语法 ↔ 图节点/边 对应 |
| [PYSLANG_ATTR_INVENTORY.md](PYSLANG_ATTR_INVENTORY.md) | **P184**: pyslang 属性/kind 清单；10 个真实 getter baseline，50 不是基线 |
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
| [PROTOCOL_DETECTION.md](PROTOCOL_DETECTION.md) | 协议识别 |
| [bus_protocol_detector.md](bus_protocol_detector.md) | Bus 协议检测设计 |
| [SVA_ANALYSIS.md](SVA_ANALYSIS.md) | SVA 分析 |
| [SPEC_UVM_TESTBENCH_EXTRACTOR.md](SPEC_UVM_TESTBENCH_EXTRACTOR.md) | UVM TB 骨架提取 Spec |
| [EVIDENCE_FEATURE.md](EVIDENCE_FEATURE.md) | evidence 追踪 |
| [condition_branch_design.md](condition_branch_design.md) | 条件分支数据层设计 |
| [select_group_design.md](select_group_design.md) | select_group 数据结构 |
| [spec_datapath.md](spec_datapath.md) | 定点数计算功能 Spec |
| [DESIGN_expr_tree_builder.md](DESIGN_expr_tree_builder.md) | expression tree builder 设计 |

## 📖 使用与参考

| 文档 | 作用 |
|---|---|
| [BETA_CONTRACT.md](BETA_CONTRACT.md) | **P193.9**: 外部 beta 契约：稳定面/不承诺面/evidence 等级/冷启动预期 |
| [PRIVACY.md](PRIVACY.md) | **P193.8**: no telemetry / RTL upload; local-only cache/snapshot; static gate |
| [MISS_REPORT_GUIDE.md](MISS_REPORT_GUIDE.md) | **P193.7**: desensitized miss report / minimal fixture / privacy checklist |
| [USER_GUIDE_EN.md](USER_GUIDE_EN.md) | English user guide: install → first query → evidence boundaries |
| [KNOWN_LIMITATIONS_EN.md](KNOWN_LIMITATIONS_EN.md) | English limitations summary; full Chinese doc is canonical |
| [USER_GUIDE.md](USER_GUIDE.md) | 用户指南 |
| [FILELIST.md](FILELIST.md) | filelist 格式支持 |
| [GLOSSARY.md](GLOSSARY.md) | **术语表** (领域术语的唯一命名处: 分层/查询/门禁/工具四组) |
| [BENCH_BASELINE.md](BENCH_BASELINE.md) | bench 深结构基准 (pr5_wrap: 真实 Cfg wrapper + 指标表 + 已知限制) |
| [OPENTITAN_HOWTO.md](OPENTITAN_HOWTO.md) | OpenTitan 跑通 HOWTO |
| [NAPLESPU_HOWTO.md](NAPLESPU_HOWTO.md) | NaplesPU 跑通 HOWTO |
| [PROJECT_PLAN.md](PROJECT_PLAN.md) | 开源 RTL 验证问题生成计划 (独立工作流) |
| [TODO.md](TODO.md) | 版本级功能待办 (月~季) |


1. **新增文档必须登记在本文件** — `tools/check_docs.py` 检查 (未登记 = 失败)。
   并在该目录 `README.md` 说明原因 (信息不丢, 历史可追)。
3. **计数只写在"当前基线"一节** — 其他文档引用本表, 不写死 passed 数。
4. **提交前跑** `python3 tools/check_docs.py` — 死链 / 归档越界 / 未登记 三项必须 ✅。