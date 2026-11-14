# 语义契约 (Semantic Contracts)

> **本文是 `AGENTS.md` 的细则文件之一。**
> 目的: 把"路径、驱动、verified、snapshot、完成"这些词从**口头共识**变成**可执行契约**。
> **状态**: 规范已立; P158 逐项落地。未落地的条目必须标记为“目标契约”，不得假装已生效。
> **最后修订**: 2026-11-15

---

## 0. 为什么需要这份文件

2026-11-11 的四角度评审发现了一个结构性事实：

```text
8 个机械门禁全绿，仍然可以有 P0 语义错误。
```

原因不是规则没执行，而是规则只检查了**形式**：

- 命令是否注册；
- 层方向；
- regex 位置；
- CC 阈值；
- 文档链接；
- 计划格式。

它们不检查：

- 一条路径是不是**数据**路径；
- 两次构建是不是同一张图；
- `verified` 是否覆盖全部证据；
- `snapshot supported` 到底支持哪些命令；
- `filelist prune` 会不会覆盖 RTL。

本文定义这些**语义边界**。代码必须服从本文；如果代码与本文冲突，
以本文为目标、代码为缺陷，并登记到 P158。

---

## 1. 唯一概念权威

1. 术语含义**只允许**在 [GLOSSARY.md](../GLOSSARY.md) 定义一次。
2. 同一个概念在代码里**只允许**有一个常量/枚举/策略函数。
3. 文档、CLI help、`capabilities`、`json_contract` 不得各自发明第二种说法。
4. 发现“同一个词两种实现”时，**先停下来统一**，不要分别修。
5. 本文只定义**跨命令的语义**；单词层面的命名仍归 GLOSSARY。

**判定**：

```text
如果两个命令对同一个输入给出不同的 edge/path/status 语义，
不是“实现差异”，是契约违反。
```

---

## 2. Edge 分类契约

所有信号图边必须归入以下三类之一，不允许“某命令自己觉得算”：

| 类别 | EdgeKind | 用途 |
|---|---|---|
| **数据边 (data)** | `DRIVER`, `CONNECTION` | fanin/fanout、data path、dataflow、verify path |
| **控制边 (control)** | `CLOCK`, `RESET`, `BRANCH_CONDITION`, `BRANCH_TRUE`, `BRANCH_FALSE`, `BRANCH_RESULT`, `CASE_SELECT`, `CASE_ITEM`, `CASE_RESULT` | 时序/条件元数据；不能单独构成数据路径 |
| **结构边 (structural)** | `BIT_SELECT`, `MEMBER_SELECT` | 位/成员聚合、层级定位；不能冒充数据驱动 |
| **类/约束边** | `CONSTRAINS`, `HAS_*`, `CONTAINS_MEMBER`, `IS_INSTANCE_OF`, `SUPER_CALL` | class/constraint 图；不参与信号路径 |

### 2.1 唯一策略

代码里必须有**唯一**的：

```python
DATA_EDGE_KINDS = {DRIVER, CONNECTION}
CONTROL_EDGE_KINDS = {CLOCK, RESET, BRANCH_*, CASE_*}
STRUCTURAL_EDGE_KINDS = {BIT_SELECT, MEMBER_SELECT}
```

所有消费者（`SignalTracer`、`PathResolver`、`DataFlowGraph`、`frontier`、`verify`）
必须引用同一组常量，不允许各自写 `edge.kind in (...)`。

### 2.2 各命令的语义

| 命令 | edge 范围 | 说明 |
|---|---|---|
| `drivers` / `loads` | data | 默认只回答数据驱动/负载；控制边需显式 opt-in |
| `trace fanin/fanout` | data | `include_clock/reset/conditional` 是显式扩展；扩展结果必须标注 |
| `paths --directed` | data | **只沿数据方向**；不能包含 CLOCK/RESET/BIT_SELECT |
| `paths`（无向） | structural connectivity | 必须标注 `mode:"structural"`；不能用于 verify 证明 |
| `dataflow analyze` | data | CLOCK/RESET 只能作为时序注解，不能成为路径节点 |
| `verify claim type=path` | data | 与 `paths --directed` 同一策略 |
| `trace frontier` | structural | 可以跨 BIT_SELECT，但输出必须说明是结构前沿 |
| `verify consistency reciprocity` | data | 只比较 DRIVER/CONNECTION 对 |

### 2.3 已修复的历史违反（P158.1，保留作回归对照）

- `PathResolver` 曾接受所有 edge kind，`clk → ready_q` 被判为数据路径；
- `paths --directed` 与 `verify claim path` 曾对 CLOCK 边返回 `verified`；
- 三条消费者曾各自维护 edge 策略。

**现状（2026-11-11 复测）**：三者共用 `src/sv_query/trace/core/graph/contracts.py`；
回归 `sim/tests/unit/test_p158_data_edge_contract.py`（含 mutation）；
`paths top_minimal.sa1.clk top_minimal.sa1.ready_q --directed` → `found:false, mode:"data"`，
`verify claim type=path` 同一对 → `contradicted`。

**回归必须同时满足（三者一致）**：

```text
paths --directed        → found:false（或 is_data_path:false）
verify claim type=path  → contradicted/unknown，绝不能 verified
dataflow analyze        → 不生成该路径、不报 latency_cycles
```

---

## 3. 路径与有界搜索契约

1. 任何**枚举**路径（`--all`、`--canonical`、dataflow 内部路径）必须有：
   - visit/work budget；
   - 可选 wall-clock timeout；
   - 达到上限时返回 `truncated:true` + `truncation_reason`。
2. 不允许用“降低默认 depth”假装有界；depth 不是 work budget。
3. 超限时**不能**返回 `found:false`；必须返回：
   - `ok:false` + `unknown_kind:"search_budget_exhausted"`，或
   - `found:true` + `truncated:true`（如果已找到部分证据）。
4. 无向 `paths` 默认是危险模式，必须文案+输出双重提示；大图应引导 `--directed`。
5. 所有长查询必须有明确上界；没有上界的查询视为缺陷。

**验收**：P158.2 在 SPI 7.6k 节点快照上，任意无向查询必须在声明的预算内返回，
并有明确 `truncated` 或 `unknown`，不得静默卡死。
P158.11.2b 起 `dataflow analyze` 同样有界：`SearchBudget`（共享自 MIG 的
`_SearchBudget`），CLI 暴露 `--max-expansions` / `--timeout`，截断时输出
`truncated:true + truncation_reason + expansions`；机械 gate 见
`sim/tests/unit/test_p158_11_dataflow_budget.py`（diamond fixture，
覆盖 max_paths 截断 / expansions 耗尽 / timeout=0 → unknown）。

**快照保真（P158.9.2，2026-11-11）**：路径/条件语义在 `--from-snapshot`
路径上与 live 等价的前提是快照往返不丢字段。字段级与命令级快照能力面的
权威矩阵见 [SNAPSHOT_SURFACE.md](SNAPSHOT_SURFACE.md)；缺失字段要么补齐、
要么显式声明不保证，不许中间态。

---

## 4. 验证状态契约

`verified` / `contradicted` / `unknown` 不是形容词，是状态机。

### 4.1 verified

只有同时满足以下全部条件，才允许 `verified:true`：

```text
请求的检查全部执行
覆盖范围完整（不是 sample/truncated）
没有 unknown check
violations == 0
证据链覆盖完整
```

否则：

```text
verified: false
status: partial / unknown
coverage: {mode, checked, total, truncated, reason}
```

### 4.2 contradicted

`contradicted` 必须有**反例**：

```text
明确输入 + 明确期望 + 实际反例
```

仅仅是“在 depth=1 没找到”“在 sample 里没出现”**不能**算 contradicted；
应返回 `unknown` 或 `partial`。

### 4.3 unknown / not_found

- 查询失败、预算耗尽、MIG 缺失、snapshot 不兼容 → `unknown`，不是 `not_found`。
- `not_found` 只在**完整搜索后确认不存在**时使用。
- `found:false` 与 `ok:false` 不能混用；消费者必须能区分“没有”与“没查完”。

### 4.4 顶层与单项

顶层 `verified` 是所有 requested checks 的聚合；不能把某一项 `pass` 当成全部
`verified`。`unknown_checks` 非空时，顶层必须 false。

**验收**：P158.6 增加截断/sample/unknown 状态机测试；SPI reciprocity
默认 sample 结果不得再顶层 `verified:true`。

---

## 5. Snapshot 契约

1. 新 snapshot 必须同时持久化：
   - `SignalGraph`；
   - `ModuleInstanceGraph`（`module_graph`）；
   - 构建元数据（版本、source filelist、build hash）。
2. `snapshot list/show` 必须显式报告：
   - `module_graph_present`；
   - `module_graph_instances` / `module_graph_ports`；
   - 构建是否完整。
3. 旧 snapshot 缺 MIG → 相关命令显式 `unknown`/失败，**不自动重建、不伪造**。
4. snapshot 支持范围必须是一张**能力矩阵**，不能“按需加一个命令”：
   - 支持：graph-only 查询；
   - 支持：graph+MIG 查询；
   - 不支持：需要 semantic adapter 的命令。
5. `--from-snapshot` 的 help / `capabilities` / `json_contract` 必须与矩阵一致。
6. 同一输入重复构建必须得到同一 canonical graph hash；不一致时显式失败，
   不能声称 “byte-identical”。

**验收**：P158.3/P158.7/P158.9；SPI 连续 3 次构建 hash 一致；
旧 snapshot 的 connection unknown 有回归测试。

---

## 6. 写入契约

1. `core` 只读；任何写能力必须在 `tools/` 或显式 CLI 写命令中。
2. 写用户工程文件必须：
   - 默认 dry-run；
   - `--apply` 才写；
   - 写已有文件要 `--force` 或备份；
   - 输出路径必须校验不是 RTL/用户文件。
3. 禁止“参数名叫 output 就直接 write_text”。
4. 只读行为用目录 sha256 指纹测试证明，不能只靠静态检查。

**验收**：P158.5；`filelist prune --output` 不再覆盖已有 RTL。

---

## 7. 确定性与构建契约

1. 同一 source root + filelist + 代码版本 → 同一 canonical graph。
2. canonical graph 必须排序节点/边/属性；hash 可复现。
3. snapshot 的 `node_count`/`edge_count` 不能依赖 set/dict 遍历顺序。
4. 真实项目 baseline 必须由 reproducible build 产生；一次构建不能当证据。
5. 任何 “byte-identical / deterministic” 文案必须有对应测试，否则删除。

**验收**：P158.3；连续 3 次构建 `canonical_hash` 相同；不同则测试红。

---

## 8. Evidence / Claim 契约

### 8.1 证据等级

每个结论必须标注证据等级：

```text
fixture      小型手写 SV，带独立 oracle
snapshot     真实项目图快照，可重复加载
real-corpus  真实项目 + 可执行 corpus/runner
runtime      CLI 现场输出（一次性的，不能当回归）
```

禁止把 `runtime` 一次性观察写成 `real-corpus` 通过。

### 8.2 Claim ledger

每个对外 claim 必须登记到 [CLAIMS.md](CLAIMS.md)，字段：

```text
claim
证据等级
执行命令
对应 gate
状态: verified / known-broken / unverified
```

没有 gate 的 claim 只能是 `unverified`，不能写成“已支持”。

### 8.3 反事实测试

每个验证器/检查器必须有：

1. **true-negative**：没有错误时不报；
2. **true-positive**：构造真实错误，必须报；
3. **mutation**：关闭检查实现，测试必须红；
4. **independent oracle**：期望不是由同一实现反向生成。

只有 true-negative 的测试不算验证。

---

## 9. 完成契约

一项工作只有同时满足以下条件才可以标 `已完成`：

```text
代码
+ 测试（含反事实/独立 oracle）
+ 文档
+ 语义契约影响说明
+ claim ledger 更新（如果是公开能力）
+ 真实 corpus 执行（如果声称 real-project）
```

只有代码 + 单元测试 = 进行中，不是完成。

---

## 10. 评审契约

worker / reviewer 的 `APPROVE` 不是证据。必须提供：

1. 可复现命令；
2. 实际输出（不是总结）；
3. 至少一个反例或反事实检查；
4. 明确区分“观测”与“推断”；
5. 主会话至少独立复现 P0；
6. 一次 fresh parse 不能证明 determinism；
7. “独立”指 **oracle 独立**，不只是访问独立。

---

## 11. 门禁落地状态

截至 2026-11-11（P158 波次 1~3 收口后）：

| 契约 | 机械 gate | 状态 |
|---|---|---|
| 数据边分类 | `test_p158_data_edge_contract` | ✅ P158.1 |
| 路径有界 | `test_p158_data_edge_contract`（paths budget/timeout） | ✅ P158.2 |
| 确定性 | `test_determinism` + SPI 3× | ✅ P158.3 |
| SPI corpus | `tools/agent/run_spi_corpus.py` 9/9 | ✅ P158.4 |
| 写入安全 | `test_filelist_prune` | ✅ P158.5 |
| verified 状态机 | `test_verify_truncated` | ✅ P158.6 |
| snapshot 构造 | `test_snapshot_robust` / `load_snapshot` | ✅ P158.7 |
| true-positive/mutation | `test_p158_data_edge_contract`（mutation）+ legacy snapshot 回归 | ✅ P158.8 |
| snapshot surface/schema | `cli/test_json_contract.py` + `regression/test_schema_contract_resolution.py`（9.1）+ `unit/test_p158_9_2_snapshot_surface.py`（9.2 往返保真/parity） | ✅ P158.9（矩阵见 [SNAPSHOT_SURFACE.md](SNAPSHOT_SURFACE.md)） |
| CI 一致性 | `.github/workflows/tests.yml` → `bash tools/run_gates.sh`（同一命令，`SVQ_GATE_BASE`） | ✅ P158.10 |
| 长查询有界 | `test_p158_11_dataflow_budget`（dataflow budget/timeout）+ paths/frontier gate | ✅ P158.11 |
| P2 清理 | — | ✅ P158.12 |

**规则**：没有机械 gate 的契约，在 P158 完成前只能算“目标契约”，
不得在汇报中写成“已保证”。
