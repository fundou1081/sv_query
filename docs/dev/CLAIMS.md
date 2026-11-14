# Claim Ledger

> **公开 claim 的唯一登记处。** 纪律依据: [SEMANTIC_CONTRACTS.md](SEMANTIC_CONTRACTS.md) §8。
> 没有 gate 的 claim = `unverified`；已知反例 = `known-broken`；不得写成“已支持”。
> **最后更新**: 2026-11-14 (P171 evidence-chain repair)

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
| C-07 | `verify consistency` 的 verified 覆盖全部请求证据 | fixture/snapshot | `test_verify_truncated` | `verified` |
| C-08 | 新 snapshot 可从 MIG 离线执行 connection 检查 | fixture | `test_verify_consistency_snapshot` / `test_snapshot_robust` | `verified` |
| C-09 | 旧 snapshot 缺 MIG 时显式 unknown，不静默 fallback | fixture | `test_verify_consistency_snapshot` legacy case | `verified` |
| C-10 | canonical 0 skipped 代表测试健康 | CI | `run_gates.sh` + opensource 114/9/0 | `scoped`（canonical 与 opensource 分开；0 skip 仍不是健康指标） |
| C-11 | SPI `verify consistency` 的 bit/connection/reciprocity 全绿 | real-corpus | `--full` 实测 3152/3261/1734，0 violations | `scoped`（外部 snapshot） |
| C-12 | worker `APPROVE` 等于真实项目通过 | 过程 | 无 | **known-broken**（需主会话复现） |
| C-13 | 安装包不含 top-level `trace`，查询引擎为 `sv_query.trace` | packaging | `test_packaging_rename` + worker wheel install | `scoped`（CI 尚未构建/安装 wheel；人工 target install 已验证） |
| C-14 | 20 个 repo-only mutation 能被查询事实检测，并有独立 Verilator oracle | mutation | `tools/run_mutation_gate.py` + `test_p171_mutation_gate` | `scoped`（注入故障，不是历史 bug benchmark） |
| C-15 | `.core` → 可 elaborate filelist 对 UART/I2C/SPI 成立 | real-corpus | `filelist_closure` profiles + 0 elaboration errors | `scoped`（OpenTitan adapter/profile 特定） |
| C-16 | Tests workflow 在 `6ae1d947` 为绿色 | CI | GitHub Actions Tests run 6ae1d947 | `scoped`（时点证据；后续提交需重跑） |

---

## 维护规则

1. 新增能力先加 claim，再加实现；没有 claim 的能力不得对外宣传。
2. 修复 P0/P1 后，必须把 claim 从 `known-broken` 移到 `verified` 或 `scoped`，
   并给出 gate 命令。
3. 删除/降级能力时，把 claim 标 `scoped`/归档，不得静默删除。
4. 文案中的 “支持 / 保证 / 已验证 / byte-identical” 必须能对应到本表一行。
