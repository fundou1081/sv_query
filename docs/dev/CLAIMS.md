# Claim Ledger

> **公开 claim 的唯一登记处。** 纪律依据: [SEMANTIC_CONTRACTS.md](SEMANTIC_CONTRACTS.md) §8。
> 没有 gate 的 claim = `unverified`；已知反例 = `known-broken`；不得写成“已支持”。
> **最后更新**: 2026-11-19 (C-27 D12 Session 错误码单一来源 + CLI 失败 adapter)

---

## 状态词

| 状态 | 含义 |
|---|---|
| `verified` | 有 gate/runner 可复现，当前通过 |
| `known-broken` | 已复现反例，尚未修复 |
| `unverified` | 没有 gate，或只有一次性 worker 证据 |
| `scoped` | 只在明确范围内成立，范围写在 claim 里 |

---

## 当前 claims

| ID | Claim | 证据等级 | Gate | 状态 |
|---|---|---|---|---|
| C-01 | `paths --directed` 只返回数据路径，不含 CLOCK/RESET | fixture | `test_p158_data_edge_contract` | `verified` |
| C-02 | `verify claim type=path` 为 verified 时是真实数据关系 | fixture | `test_p158_data_edge_contract` | `verified` |
| C-03 | 无向 `paths` 在大图上不会静默卡死 | real-corpus | `test_p158_data_edge_contract` / SPI 0.6s truncated | `verified` |
| C-04 | 同一输入重复构建得到同一张图 | fixture/snapshot | `test_determinism` + SPI 3× | `verified` |
| C-05 | SPI corpus 是可执行的 real-project 回归 | real-corpus | `run_spi_corpus.py` 9/9 | `verified` |
| C-06 | `filelist prune` 不会修改用户 RTL | fixture | `test_filelist_prune` | `verified` |
| C-07 | `verify consistency` 的 verified 覆盖全部请求证据；unknown/truncated 时 coverage_complete=false | fixture/snapshot | `test_verify_truncated` / `test_verify_coverage` | `verified` |
| C-08 | 新 snapshot 可从 MIG 离线执行 connection 检查 | fixture | `test_verify_consistency_snapshot` / `test_snapshot_robust` | `verified` |
| C-09 | 旧 snapshot 缺 MIG 时显式 unknown，不静默 fallback | fixture | `test_verify_consistency_snapshot` legacy case | `verified` |
| C-10 | canonical 0 skipped 代表测试健康 | CI | `run_gates.sh` + opensource 112/11/0；123 deferred | `scoped`（canonical 与 opensource 分开；deferred 不等于 unexecuted；0 skip 仍不是健康指标） |
| C-11 | SPI `verify consistency` 的 bit/connection/reciprocity 全绿 | real-corpus | `--full` 实测 3152/3261/1734，0 violations | `scoped`（外部 snapshot） |
| C-12 | worker `APPROVE` 等于真实项目通过 | 过程 | 无 | **known-broken**（需主会话复现） |
| C-13 | 安装包不含 top-level `trace`，查询引擎为 `sv_query.trace` | packaging | `test_packaging_rename` + `tests.yml` wheel build/install smoke | `verified`（CI @ 6ae1d947） |
| C-14 | 20 个 repo-only mutation 能被查询事实检测，并有独立 Verilator oracle | mutation | `tools/run_mutation_gate.py` + `test_p171_mutation_gate` | `scoped`（注入故障，不是历史 bug benchmark） |
| C-15 | `.core` → 可 elaborate filelist 对 UART/I2C/SPI 成立 | real-corpus | `filelist_closure` profiles + 0 elaboration errors | `unverified`（一次性外部 OpenTitan 证据；需重复 gate） |
| C-16 | Tests 与 Benchmark workflow 在 `4d58d7fb` 为绿色；Coverage Gen 已退役 | CI | GitHub Actions runs 43576810042 / 43576809982 | `scoped`（时点证据；Coverage Gen 测试已归档，workflow 删除，不是 pass） |
| C-17 | `trace evidence` 在 source/filelist/snapshot 中选择 functional LHS 赋值行；reset/comment/comparison 不冒充 assignment | fixture | `test_evidence_stability.py` | `scoped`（启发式分支扫描，不覆盖所有 SV 语法） |
| C-18 | `trace profile.source.line` 对自带 timescale 和预处理注入 timescale 的 file-backed 源文件给出磁盘声明行 | fixture | `test_declaration_line_with_own_timescale` / `test_sequential_signal_profile` | `scoped`（in-memory source 不保证） |
| C-19 | class property evidence 使用 `ClassPropertySymbol` 声明位置，不由 regex 扫 class 文本 | fixture | `test_class_property_uses_member_declaration_line` / `test_class_comment_is_not_property_evidence` / `test_virtual_class_property_evidence` | `scoped`（class/constraint 上下文 evidence 仍非赋值） |
| C-20 | `graph subgraph --edge-kinds control` 包含 branch/ternary 和 conditional DRIVER；`control,driver` 保留无条件 DRIVER | fixture | `test_subgraph_control_includes_branch_edges` / `test_subgraph_control_plus_driver_keeps_unconditional_driver` | `scoped`（CLI 子图，不是全图语义） |
| C-21 | `build_graph` 失败时不暴露半成品图；phase=failed 且可重试 | fixture | `test_d6_build_transaction.py` | `verified`（库层；CLI 尚未暴露 phase） |
| C-22 | cache/snapshot 写入原子化；graph cache key 使用 CACHE_VERSION；损坏 cache/snapshot 显式失败/miss | fixture | `test_d7_cache_snapshot_atomic.py` | `verified`（库层） |
| C-23 | `sv_query.Session.execute` 是只读、无 CLI/环境依赖的请求接缝；`version` 返回结构化结果，非法 request/未知 op 返回结构化错误 | fixture | `test_d10_session_contract.py` | `verified`（库层；仅 version op） |
| C-24 | `sv_query.Session(handlers=...)` 可把只读 op 委派给注入 handler（`version` 不可覆盖）；handler 异常/非 mapping result 返回结构化 `E_HANDLER_FAILED`；CLI `capabilities` 经 Session 调用 `cli._registry.to_json`，六个输出 case 与 D11 前逐字节一致；P182.1c 仅改 paths registry envelope（standard→direct），其余不变 | fixture | `test_d11_capabilities_session.py` | `verified`（库层 + capabilities adapter；调用形式 `Session(...).execute(...)`；result 仅顶层拷贝；CLI 失败信封自 D12 起经 `cli._session_adapter` 映射，见 C-25） |
| C-25 | Session 三个错误码与 `error.type` 单一来源 `sv_query.errors`；`cli.errors.ErrorCode` 逐值接纳同一组码；Session 失败响应经唯一 adapter（`cli._session_adapter.fail_from_session`）映射到 CLI `fail`，未知 code → `E_INTERNAL` 且原值保留在 `session_error_code`；`capabilities` 成功输出与 D12 前逐字节一致 | fixture | `test_d12_error_envelope.py` | `verified`（capabilities 失败路径；全量 run() dispatch 评估为不采纳（D15 ADR）） |
| C-26 | `stats` 成功时 `elaboration_errors=[]`；malformed RTL 的 `--json` 返回 `E_ELABORATION_FAILED`、rc=1、无 result | fixture | `test_p182_3_stats_completeness.py` / `tools/check_stats_completeness.py` | `verified`（CLI 路径；不恢复 partial graph） |
| C-27 | `capabilities --json` 是 agent 命令索引唯一真相源；`docs/agent/CAPABILITIES_GENERATED.md` 由其生成；旧 AGENT_FEATURE_MAP 自 P182.4 起为历史快照；exp 默认不入 capabilities | fixture | `test_p182_4_agent_entry.py` / `gen_agent_skill.py --check` | `verified` |
| C-28 | 旧 snapshot 缺少 `module_graph` 时，instances/hierarchy/connections 返回 `E_SNAPSHOT_NO_MIG`，不返回 ok=true 空结果 | fixture | `test_p182_6_snapshot_mig.py` | `verified` |
| C-29 | pyslang 属性扫描只拦新增真实 getter/unknown；baseline 不是 50 处名字启发式；safe_attr 可选 on_degraded 不改变返回/default | fixture | `test_p184_pyslang_attr_scan.py` / `test_safe.py` / `scan_pyslang_attrs.py --check` | `verified`（Phase 0） |
| C-30 | CLI command surface 以 baseline 锁定 45 canonical / 39 default-visible / 2 aliases / 32 standard / 13 direct；增删/别名/默认可见性/逐命令元数据/隐藏命令漂移必须显式更新 | fixture | `test_p185_4_command_surface.py` / `check_command_surface.py --check` | `verified` |
| C-31 | 5 个 canonical fixture 当前 shadow=0，保留默认定名空间；不新增 drop_shadows API | fixture | `test_p186_1_shadow_measure.py` / `measure_shadow_nodes.py` | `verified`（fixture 范围） |
| C-32 | CVA6 2 个历史 fix 的 non-blind 对照：drivers --evidence 命中驱动表达式；bit-select 需下钻；非自动发现率、无本地动态 oracle | doc | `P187_VALUE_CASES_CVA6_2026-11-19.md` / `P187_FOLLOWUPS_2026-11-19.md` | `scoped`（non-blind，C2 总线级漏报已记录） |

---

## 维护规则

1. 新增能力先加 claim，再加实现；没有 claim 的能力不得对外宣传。
2. 修复 P0/P1 后，必须把 claim 从 `known-broken` 移到 `verified` 或 `scoped`，
   并给出 gate 命令。
3. 删除/降级能力时，把 claim 标 `scoped`/归档，不得静默删除。
4. 文案中的 “支持 / 保证 / 已验证 / byte-identical” 必须能对应到本表一行。
