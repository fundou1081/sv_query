# 面向 agent 的交付层评审 — 修订版 v2

> **状态**: 讨论底稿 / 建议稿；**不是** PLAN，**不是**契约，**不是**排期。
> **取代**: v1 `agent_interface_review_2026-11-16.md`（已归档；v1 的时点结论保留，但部分数字/概括不准确）。
> **评审 HEAD**: `8da675b3`（2026-11-16，P181 收口后）
> **方式**: 只读代码/文档检查 + 可复现命令；**未重新 benchmark**，性能数字标注为时点/外部证据。
> **计数口径**: 以本文“证据”命令的实际输出为准；数字会漂移，引用时必须带 HEAD/日期。

---

## 1. 结论（修订）

**核心判断仍然成立，但要缩小措辞：**

```text
事实层（semantic/graph/verify 契约）明显强于交付层（envelope/schema/入口/会话）。
```

这不是“解析精度不行”，而是：

- agent 必须正确消费的 **JSON envelope 与字段 schema** 没有单一可执行契约；
- 命令入口多套并存，文档没有机械绑定到运行时 capabilities；
- 单进程/冷构图与多轮查询的产品设想有张力；
- 一些“完整性状态”与 `ok` 没有联动。

v1 中“最大风险是承诺给 agent 的稳定契约没有被机器保证”这个判断，修订后仍成立；但 v1 的 **direct 数量、缺参行为、若干计数**需要修正。

---

## 2. 已验证为事实的部分

### 2.1 命令面与 schema

`sv_query capabilities --json` 实测（HEAD `8da675b3`）：

```text
core commands (default): 39
exp commands (--include-exp): 6
total: 45
envelope: standard 27 / direct 12
json_contract.schema_version: "1"
```

因此：

- v1 的 “39 core + 6 exp” **正确**；
- v1 的 “11 类 direct” **不正确**，实际是 **12 个 direct**：
  `instances, connections, hierarchy, params, ports, class, search,
   capabilities, snapshot save, snapshot list, snapshot compare, snapshot delete`。

`src/cli/_registry.py`（1575 行）中的 `JSON_CONTRACT`：

- 是 Python dict + 描述性 `"type": "string|null"`；
- 没有 `required` / `properties` / `$ref`；
- 没有 validator 消费它；
- `tools/llm_schema.json` 只有 5 个旧别名命令（`stats`, `trace_fanin`, `trace_fanout`,
  `trace_impact`, `trace_evidence`），版本 `1.2.0`，与 `"1"` 不同；
- `tools/llm_schema_validate.py` 不在 `run_gates.sh`。

**结论：v1 B-A1 的核心事实成立。**

### 2.2 envelope / exit code

已确认：

- `snapshot list --json` 顶层是数组，没有 `ok`；
- `trace evidence --batch` 部分失败：
  ```text
  ok:false, rc=0
  ```
- 三类失败出口：
  - `_output.fail`：`{"ok":false,"error":<string>}`
  - `errors.make_error`：`errors:[<string>]` + `error_code`
  - `_common.emit_json_error`：`error:{type,message}`
- `diagnose` 缺参 rc=2。

但 v1 的“缺参数 rc=1 且完全不输出 JSON”**过度概括**：

```text
drivers --json (无参数)  -> rc=1, 输出 JSON error
search  --json (无参数)  -> rc=2, 不输出 JSON
```

所以准确说法是：**缺参行为按命令不同，rc 与 JSON 输出没有统一规则**，不是统一的 rc1/no-JSON。

### 2.3 `stats.ok` 与图完整性

属实。`src/cli/main.py` 中 `stats` 直接写：

```python
"ok": True,
"errors": [],
```

同时把 `elaboration_errors` 放进 `result`。agent 只看 `ok` 会把 partial graph 当完整图。

### 2.4 agent 入口与文档

`tools/agent/svq_query.patch.yml`、`.dsh/skills`、`skills/sv-query`、CLI 文档四套入口并存；
skill 文档与运行时命令面没有机械一致性 gate。v1 的方向判断成立。

### 2.5 结构重复与大文件

实测：

```text
src/sv_query/trace/core/pipeline.py
src/sv_query/trace/core/builder/graph_pipeline.py
```

两套 DAG 同时存在且被使用；CLI 中 `build_graph(` 约 40 处，显式 `use_cache` 约 5 处。

大文件：

```text
graph_builder.py        2298
query/signal.py         2013
class_graph_builder.py  1729
_registry.py            1575
```

这些是当前代码事实。

### 2.6 文档治理与矛盾

- `docs/` 当前约 1052 个 `.md`（含本文/归档会再变）；
- 519 份 iteration、171 份 task；
- `PLAN.md` 872 行，`check_plan` 报告 657 个计划项；
- `AGENTS.md:98` 说 P158 语义 gate 未落地，`SEMANTIC_CONTRACTS §11` 表却全 ✅；
- mutation / Verilator oracle 在 CI 独立 step，不在本地 canonical gate。

这些都是静态可核对的事实；v1 的治理体积判断成立。

---

## 3. v1 中需要修正/收缩的部分

| v1 说法 | 修订 |
|---|---|
| “11 类 direct” | 实际 **12**；若排除 `capabilities` 才是 11，但 v1 未说明口径 |
| “缺参数 rc=1 且完全不输出 JSON” | 不统一；`drivers` rc1+JSON，`search` rc2+无 JSON |
| “36 处 build_graph / 4 处 use_cache” | 当前约 **40 / 5**；v1 数字至少是时点/范围偏差 |
| “CLI→engine 79 处” | 当前静态检索约 78；时点数字，不应写死 |
| “1051 md / 656 P / 519 iter” | 519 iter 真实；md/P 随本文和 P181 变动，应带时点 |
| “P181 修了 run_gates lint no-op” | 在 `8da675b3` 已真；v1 基于 `2a004f76`，描述的是当时状态 |
| “stats 一定给不完整图” | 代码硬编码 `ok:true`，但需构造 elaboration-error fixture 才能行为级证明 |
| “性能 1.8–26s” | 未在本次评审复测；保留为历史 perf 证据，不是当前测量 |

---

## 4. 仍值得优先处理的事项

### P0：envelope 与 rc/ok 统一

- 统一 `ok/errors/error_code` 形状；
- 明确 `rc≠0 <=> ok:false`；
- 批量部分失败改用 `partial:true + failed_signals[]`，不再 rc0/ok:false 混淆；
- 加一个遍历 capabilities 的成功/失败/未知信号/截断 gate。

### P0：schema 可执行

- 从 registry 生成 input/result JSON Schema；
- capabilities 暴露 schema；
- gate 用同一份 schema 校验真实输出；
- 归档 `llm_schema.json` 的旧别名部分。

### P1：`stats` 完整性

- `elaboration_errors` 非空时：`ok:false` 或 `complete:false`，二选一并写进契约；
- 加 fixture 测试，防止只改代码不改行为。

### P1：入口收敛

- 明确 CLI + capabilities 是唯一稳定入口；
- DSH tool 标 `eval-only`（或由 schema 生成）；
- skill 的命令/字段清单尽可能由 capabilities 生成，至少加一致性 gate。

### P2：会话/缓存/结构/治理

- 先评估 `--from-snapshot` 全覆盖或 `use_cache` 默认，不直接上 serve；
- 合并两套 DAG、拆 `_registry.py`、归档 PLAN/iter 历史；
- 把 oracle/mutation 纳入第二个 canonical gate 或明确声明。

---

## 5. 对应 PLAN（已合并）

本文的建议已登记为 **P182**，不直接实现：

```text
P182.1 envelope inventory + check_envelope_contract gate
P182.2 executable JSON schema + validation gate
P182.3 stats/elaboration completeness
P182.4 agent entry convergence + capabilities-generated skill
P182.5 snapshot/cache/session evaluation
P182.6 governance/claims/structural cleanup
```

采纳顺序建议：P182.1 → P182.3 → P182.2 → P182.4 → P182.5/6。
理由：envelope 是 agent 消费的第一道契约；stats 完整性是单点高风险；schema 是长期收益；
入口/性能/治理在契约稳定后再动，避免同时改接口和结构。

---

## 6. 复核命令

```bash
git rev-parse --short HEAD
sv_query capabilities --json | jq '.json_contract.schema_version, (.commands|length)'
sv_query capabilities --json | jq '[.commands[]|select(.envelope=="direct")]|length'
grep -n 'JSON_CONTRACT' src/cli/_registry.py | head
python3 - <<'PY'
import json
d=json.load(open('tools/llm_schema.json'))
print(d['version'], list(d['commands']))
PY
grep -RIn 'build_graph(' src/cli | wc -l
grep -RIn 'use_cache' src/sv_query/trace/unified_tracer.py | head
python3 tools/check_docs.py --strict
python3 tools/check_plan.py
bash tools/run_gates.sh
```

**判读原则**：数字以命令输出为准；本文是评审，不是契约。任何建议实施前必须按
[AGENTS.md](../../AGENTS.md) §2 登记 PLAN、建 task、置 current item。
