# 交互式 debug 场景 pilot

**日期**: 2026-11-06
**状态**: P74 pilot（3 模型；不是全量 benchmark）
**模型**: MiniMax-M3 / MiniMax-M3.1-Flash / DeepSeek-Flash
**臂**: T2（sv_query）
**工作区**: `/private/tmp/lr_interactive_ws`（仅 fixture，无 ground truth）

---

## 1. 三个场景

| id | 任务 | 需要连续追问的原因 |
|---|---|---|
| `deep_drive_chain` | `top.din -> top.dout` 完整 drive 链、register/XOR/mux | `paths` 有两个合法变体；register/control 要跨查询确认 |
| `rand_constraints` | `addr` / `len` 的 rand、继承约束、共同 block | 先 class → member → 实例级 constraints |
| `rand_coverage_mapping` | rand var → coverpoint/bins/cross/constraints | 需要正向 + 反向 coverpoint 查询；bins 原 CLI 只有计数 |

Fixture 在 [examples/interactive_debug/](../../examples/interactive_debug/)，ground truth 在
[tools/benchmark/interactive_debug/scenarios.json](../../tools/benchmark/interactive_debug/scenarios.json)。
模型列表见 [models.json](../../tools/benchmark/interactive_debug/models.json)；M3.1 的 headless patch 见[minimax31.patch.yml](../../tools/benchmark/interactive_debug/minimax31.patch.yml)。

---

## 2. 运行

- 每个场景一个 agent，要求 **至少 4 轮实际 query**；
- 隔离工作区只放 `deep_chain.sv` / `rand_coverage.sv`，不放 `scenarios.json`；
- 最终 JSON 记录 `rounds`、`answer`、`confidence`、`evidence`；
- 第一次 pilot 中 DeepSeek 读过 fixture 目录下的 `scenarios.json`（ground truth），
  该结果**作废**；将 ground truth 移出 fixture 目录后重新跑 6 个 agent；
  MiniMax-M3.1-Flash 是后续补充的第三模型（3 场景）。

### 指标

| 场景 | 模型 | rounds | tool calls | input tokens | output tokens | wall |
|---|---:|---:|---:|---:|---:|---:|
| deep_drive_chain | MiniMax-M3 | 20 | 65 | 959,242 | 13,490 | 139.9s |
| deep_drive_chain | DeepSeek-Flash | 7 | 30 | 749,848 | 15,744 | 118.5s |
| rand_constraints | MiniMax-M3 | 14 | 35 | 326,056 | 6,687 | 46.8s |
| rand_constraints | DeepSeek-Flash | 7 | 12 | 162,549 | 8,451 | 54.2s |
| rand_coverage_mapping | MiniMax-M3 | 10 | 28 | 252,557 | 7,304 | 53.5s |
| rand_coverage_mapping | DeepSeek-Flash | 7 | 14 | 216,147 | 6,115 | 45.0s |
| deep_drive_chain | MiniMax-M3.1-Flash | 16 | — | 1,394,304 | 19,976 | — |
| rand_constraints | MiniMax-M3.1-Flash | 14 | — | 403,985 | 10,782 | — |
| rand_coverage_mapping | MiniMax-M3.1-Flash | 6 | — | 300,480 | 9,847 | — |

> token 是 DSH child session 的 `uncachedInput + cacheRead`；不含人工。

---

## 3. 结果

### 3.1 Deep drive chain

| 模型 | path | hop | register | xor | mux | comb | 结论 |
|---|---|---:|---|---|---|---|---|
| MiniMax | 11 节点（含 `u_stage.d`） | 10 | ✅ `u_leaf.q` | ✅ `mixed` | `top.sel`（源） | false | **完整（接受 11 节点变体）** |
| DeepSeek | 11 节点 | 10 | `true`（不是节点） | `true`（不是节点） | `top.sel` | false | **部分**：路径/时序对，字段类型错 |
| MiniMax-M3.1-Flash | 11 节点 | 10 | ✅ `u_leaf.q` | `leaf_q ^ 8'hA5`（表达式） | `sel`（源） | **true（错）** | **部分**：路径/寄存器对，xor/mux 非节点，combinational 自相矛盾 |

关键观察：

- `paths --directed` 返回 **10 节点（9 hops）** 的 wrapper 折叠路径；
- `paths --directed --all` 的第一个路径是 **11 节点（10 hops）**，包含 `top.u_mid.u_stage.d`；
- 两个都是图里的合法路径；任务没有规定粒度，导致 hop_count 不可比；
- `sel ? d : ~d` 没有被建模成条件边：`controlflow analyze` 返回空，
  三个模型都靠 `search`/源码确认 mux；
- MiniMax 明确说明三元 mux 没有 expression node，DeepSeek 也用源码证据。

### 3.2 Rand constraints

| 模型 | rand/type | constraints | inherited | both_vars_block | 结论 |
|---|---|---|---|---|---|
| MiniMax | ✅ | ✅ c_base + c_packet | ✅ | ❌ `cg`（把 covergroup 当 block） | 部分 |
| DeepSeek | ✅ | ✅ c_base + c_packet | ✅ | ✅ `c_packet` | **完整** |
| MiniMax-M3.1-Flash | ✅ | ✅ c_base + c_packet | ✅ | ✅ `packet.c_packet` | **完整**（并验证 14 轮） |

观察：

- 三个模型都能通过 `class --relations` / `trace constraints` 找到继承约束；
- MiniMax 把“共同 block”误解成 covergroup，说明 prompt 需要明确
  **constraint block**；已修正 prompt/ground truth；
- `trace constraints p.addr`（相对名）不工作，必须 `top.e.p.addr`；
  三个模型都撞到这个边界，DeepSeek/M3.1 明确记录。

### 3.3 Rand ↔ coverage mapping

| 模型 | coverpoints | bins | cross | constraints | uncovered | 结论 |
|---|---|---|---|---|---|---|
| MiniMax | ✅ cp_addr/cp_len | ✅ low/high/len_small/len_large | ✅ | ✅ | [] | **完整** |
| DeepSeek | ✅ | ✅ | ✅ | ✅ | [] | **完整** |
| MiniMax-M3.1-Flash | ✅ | ✅ | ✅ | ✅ | [] | **完整** |

关键观察：

- **修复前** `trace covergroups` 只返回 `bins: 2`，不返回 bin 名称；
  MiniMax 在第一次 pilot 里为了拿 `low/high` 直接 import 了 `CovergroupExtractor`；
- 本轮新增 `bin_details`（name/kind/values/bin_type）后，三个模型都能直接从 CLI 得到
  `low/high`、`len_small/len_large`，不需要内部 API；
- 三个模型都发现 `cg` 没有 `sample()`/clock；这是源码事实，不影响 mapping；
- DeepSeek 的 `uncovered_rand_vars=[]` 正确；MiniMax 也是 `[]`（输出中曾用空串，语义等价）。

---

## 4. 场景是否成立

**成立，但需要协议约束**：

- 三个任务都需要 **5–20 轮**查询，不是一次 `drivers` 能完成；
- deep chain 需要 `paths` + profile + controlflow/search；
- constraints 需要 class/member/instance 三次跳转；
- coverage 需要正向/反向 coverpoint + bins + constraints；
- 但 deep chain 的“路径粒度”和 mux 语义目前不稳定，不能直接作为严格 ground truth。

### 发现的真实产品缺口

1. **路径粒度不唯一**：`paths --directed` 10 节点 vs `--all` 11 节点；
   需要 `paths --canonical` 或 `--include-wrapper-ports` 明确语义。
2. **三元 mux 未建模**：`controlflow analyze` 空，agent 必须读源码；
   应补 condition/control edge，或明确 `unknown`。
3. **bin 名称缺失**：已修 `bin_details`；这是场景 3 逼出来的真实修复。
4. **class relative name 不解析**：`trace constraints p.addr` not_found；
   应支持 class-relative 或给出 canonical 提示。
5. **class instance 不是 scope**：`scope top.e` not_found；agent 需要知道用
   `trace covergroup --instance`，应有错误提示。
6. **stdout 噪声**：部分命令在 JSON 前输出 `[Phase 4]`，agent 要过滤；
   应统一 stderr/quiet。

---

## 5. 后续修复（P76，2026-11-06）

针对 pilot 发现的问题，先修了 3 项：

### 5.1 `paths --canonical`

新增：

```bash
sv_query paths top.din top.dout --directed --canonical --json
```

策略：

```text
max_nodes_then_lexicographic
```

- 在结构变体中选节点数最多的；
- 输出 `canonical=true`、`canonical_policy`、`candidate_count`、`candidate_truncated`；
- `--canonical` 与 `--all` 互斥。

P76 时 deep_chain 固定为 **11 节点 / 10 hops**。P77 加入
`OP_TERNARY` 后，规范路径变为 **12 节点 / 11 hops**，并显式包含 mux 节点：

```text
...u_stage.u_leaf.d.ternary_sel
```

### 5.2 未建模 control 显式 unknown

P76 时 `sel ? d : ~d` 只标 unknown。P77 已把**简单 input-port ternary**
lower 成 `OP_TERNARY + BRANCH_CONDITION/TRUE/FALSE/RESULT`，并生成条件 DRIVER：

- `controlflow analyze` → `condition_status="complete"`，条件含 `sel` / `!(sel)`；
- 复杂/不支持表达式仍返回 `unknown`，不猜测。

### 5.3 class relative name / class instance scope 提示

- `trace constraints p.addr` 失败时返回：
  - `hint`：使用 `top.e.p.addr` / `packet.addr`；
  - `suggestions`：`class <type> --member addr`。
- `scope top.e` 失败时明确提示：
  - RTL scope 只支持 module/instance；
  - class instance 用 `class <type>` 或 `trace covergroup <cg> --instance top.e`。
- `trace coverpoints` 0 match 时给 instance-qualified 提示。

### 5.4 测试

新增 `sim/tests/cli/test_interactive_followups.py`：

- canonical 路径（P77 后 12 节点 /11 hops）；
- controlflow 读 port ternary；
- class relative/scope/coverpoint hints。

P77 新增 `sim/tests/cli/test_port_ternary.py`：

- `OP_TERNARY` 节点存在；
- `controlflow` complete；
- fanin 条件驱动。

全量 **2542 passed / 0 failed**。

---

### 5.5 P77：port-map ternary 已 lower

实现：

```text
semantic PortConnection.expression (ConditionalOp)
  -> OP_TERNARY
  -> BRANCH_CONDITION / TRUE / FALSE / RESULT
  -> conditional DRIVER
```

对 deep_chain：

```text
top.u_mid.u_stage.sel --BRANCH_CONDITION-->
top.u_mid.u_stage.u_leaf.d.ternary_sel
top.u_mid.u_stage.d --BRANCH_TRUE/FALSE-->
top.u_mid.u_stage.u_leaf.d.ternary_sel
top.u_mid.u_stage.u_leaf.d.ternary_sel --BRANCH_RESULT-->
top.u_mid.u_stage.u_leaf.d
```

边界：

- 只支持 input port 的简单 ternary；
- 不支持 concat/function/复杂表达式，继续 `unknown`；
- 不新增 `EdgeKind.CONTROL`。

---

## 6. 建议

- 把这三题固定为 **interactive debug protocol**，但不冒充准确率 benchmark；
- 先补 `paths --canonical` 和 mux/control 的显式语义，再做 2 模型 × 3 题 × 2 seed；
- `bin_details` 已落地，补契约/测试；
- 下一轮再看 warm query service，而不是先做全量。

## 7. 边界

- 6 个 agent，单 seed，T2 only；
- 不是 HWE/VeriBug，不声称真实 bug 修复率；
- 不比较模型能力排名；这里只验证“场景是否需要连续追问”和“工具是否支撑”。
