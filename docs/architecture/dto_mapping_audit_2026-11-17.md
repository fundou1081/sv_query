# DTO 映射审计（D9 / P183.3）— 2026-11-17

> **Baseline**: `2fe3d74f`
> **范围**: `TraceNode` / `TraceEdge` → dict 的全部投影；CLI/core 消费的 node/edge
> / evidence DTO；snapshot save/load payload。
> **结论**: **每个上下文保留一份 canonical projection**，不做强制全局合并。
> 本轮不改任何 CLI/JSON 字段语义。
>
> 契约依据：[SEMANTIC_CONTRACTS §1](../dev/SEMANTIC_CONTRACTS.md)、
> [SNAPSHOT_SURFACE](../dev/SNAPSHOT_SURFACE.md)、
> [JSON 契约](json_contract_2026-10-31.md)。
> 锁定测试：`sim/tests/unit/test_d9_dto_mapping_contract.py`。

---

## 1. 方法

1. 全仓搜索 `TraceNode` / `TraceEdge` → dict 的构造点（`to_dict`、`*_dict`、
   `{"id": ...}`、`"width_msb"`、`"assign_type"` 等模式）。
2. 逐投影记录**精确字段集**、消费者、字段形态与派生规则。
3. 区分三种情况：
   - **精确重复**（同字段集 + 同派生规则）→ 可抽最小 helper；
   - **重叠但语义不同**（字段/规则至少一处不同）→ 不能合并；
   - **不同域**（MIG/architecture/聚合结果）→ 不在 canonical node/edge DTO 范围。
4. 用独立 oracle 锁定字段集：
   - `dataclasses.fields(TraceNode/TraceEdge)`；
   - `cli._registry.JSON_CONTRACT`（`capabilities --json` 的同一来源）。

---

## 2. Canonical 投影清单（精确字段集）

### 2.1 Snapshot：`SignalGraph.to_dict` / `from_dict`

位置：`src/sv_query/trace/core/graph/models.py:627`（node 653 / edge 682）

**Node 字段（18，= TraceNode 全部 dataclass 字段）**

```text
id, name, module, kind, width, bit_range, file, line,
is_clock, is_reset, is_enable, is_port, is_signed,
parent, parent_bit_start, parent_bit_end, modport_dir, extra
```

**Edge 字段（16 = TraceEdge 全部字段 - 2 个声明不持久化字段）**

```text
src, dst, kind, assign_type, condition, clock_domain, modport_dir,
confidence, expression, bit_slice, source_location, condition_chain,
function_return, is_function_call, source, extra
```

显式不持久化（见 [SNAPSHOT_SURFACE §1](../dev/SNAPSHOT_SURFACE.md)）：

| 字段 | 处置 | 原因 |
|---|---|---|
| `effective_condition` | 🔁 重算恢复 | `add_trace_edge` 在 `from_dict` 路径重算 |
| `condition_ast` | ❌ 不保证 | 运行期 AST 对象，不可 JSON 序列化 |

**消费者**：`snapshot save/list/show/compare`、`SignalGraph.from_dict`、
`UnifiedTracer.load_snapshot`、graph cache（缓存复用同一 `graph_data`）。
**职责**：唯一**全保真**持久化投影；agent 的 `--from-snapshot` 语义依赖它。

### 2.2 Snapshot payload 包装层

| 层 | 位置 | 增加的键 |
|---|---|---|
| `graph.to_dict()` | `graph/models.py` | `version, created_at, node_count, edge_count, nodes, edges, dynamic_nodes, function_nodes, runtime_system_nodes, expr_trees, const_map, func_info` |
| `snapshot save` | `src/cli/core/state/snapshot.py:123` | `module_graph, elaboration_errors, failed_files, strict_mode` |
| `SnapshotManager.save` | `snapshot_manager.py:143` | `version(默认), tag, git_commit, files, created_at`；原子写 |

**读路径**：`SnapshotManager.load` 返回原始 dict → `SignalGraph.from_dict` +
`ModuleInstanceGraph.from_dict`；损坏 JSON 显式 `ValueError`，不返回假图。
**遗留入口 / writer 级重复**：`SignalGraph.save_snapshot/load_snapshot`
（`models.py:856/878`）复用同一 `to_dict`，但当前 `src/` 无消费者。
两处 writer 都重复赋值 `tag/git_commit/files/created_at`；这是**写盘元数据**
重复，不是 DTO 字段重复，且两者原子性/version 默认语义不同
（`SnapshotManager.save` 原子写 + `version` 默认；`save_snapshot` 直接写）。
本轮不合并（抽 helper 只会收敛 4 行元数据赋值，且会触达无消费者的遗留入口），
留作后续清理项，见 §7。

### 2.3 CLI trace：`_node_to_dict`

位置：`src/cli/core/semantic/trace_common.py:745`

字段（24）：

```text
id, kind, module, width_msb, width_lsb, width, distance, precision,
is_signed, parent, bit_range, dynamic_index, function_call,
runtime_system_call, condition, conditions, condition_path,
condition_paths, condition_unconditional, condition_truncated,
condition_simplified, conditions_simplified, condition_analysis,
condition_analysis_incomplete
```

**消费者**：`trace fanin` / `trace fanout`（`trace.py:431`）。
**契约**：`JSON_CONTRACT["trace_node"]`；CLI 测试
`sim/tests/cli/test_json_contract.py::test_fanin_output_matches_contract`。
**职责**：面向 agent 的**查询结果**投影：条件路径、距离、粒度、动态/函数标记。

### 2.4 CLI minimal：`node_dict`

位置：`src/cli/core/semantic/_common.py:30`

字段（5）：

```text
id, name, kind, module, width
```

**消费者**：`class` 的 members/instances、`scope` 的 class members/instances
（`classes.py`、`scope.py`）。
**契约**：`JSON_CONTRACT["class_member"]`（+`is_rand/rand_mode/type`）与
`JSON_CONTRACT["class_instance"]`（严格 5 字段）。
**职责**：最小身份投影，不承载条件/距离/证据。

### 2.5 Core subgraph：`_node_dict` / `_edge_dict`

位置：`src/sv_query/trace/core/query/subgraph.py:106/126`

Node 基础字段（10）：

```text
id, kind, module, width_msb, width_lsb, width, precision,
parent, bit_range, is_signed
```

Edge 基础字段（7）：

```text
src, dst, kind, expression, condition, bit_slice, assign_type
```

`--evidence` 时各追加 `file, line`（node 12；edge 9）。
**消费者**：`graph subgraph`（core，无渲染依赖）。
**契约**：`JSON_CONTRACT["subgraph_node"]` / `["subgraph_edge"]`；
CLI 测试 `test_graph_subgraph_contract`。
**职责**：有界结构子图；响应体积优先，不输出条件分析/距离。

### 2.6 CLI edge evidence：`edge_evidence_dict`

位置：`src/cli/core/semantic/trace_common.py:488`

字段（6）：

```text
kind, assign_type, condition, expression, file, line
```

- `condition` 优先 `edge.condition`，为空回退 `edge.effective_condition`；
- `file/line` 在无 `source_location` 时为 `null`。
**消费者**：`paths --evidence`、`trace fanin/fanout` 的 per-node `evidence`。
**契约**：`JSON_CONTRACT["edge_evidence"]`；测试
`test_paths_evidence_contract`、`test_fanin_evidence_contract`。

### 2.7 CLI graph listing：`graph nodes` / `graph edges`

位置：`src/cli/core/locate/graph.py`

| 投影 | 字段 |
|---|---|
| `graph_node` | `id, name, kind, module` |
| `graph_node_detail` 追加 | `width, expression, operands, signals, function_name, condition, true_branch, false_branch` |
| `graph_edge` | `src, dst, kind` |

**消费者**：`locate graph nodes/edges`（人工/agent 列表）。
**契约**：`JSON_CONTRACT["graph_node"]/["graph_node_detail"]/["graph_edge"]`。

### 2.8 相邻投影（不同域，非 canonical node/edge DTO）

| 投影 | 位置 | 字段/形态 | 为何不并入 |
|---|---|---|---|
| `ports` item | `ports.py:46` | `port, id, direction, width, in_edges, out_edges` | 端口聚合 + 计数 |
| `scope` signal | `scope.py:69` | `name, canonical_id, kind, width, is_port, direction` | scope 清单命名不同 |
| `trace lookup` | `trace_lookup.py:115` | `requested, found, canonical, resolution, matched_via, bit_suffix, aliases, suggestions, width, kind, module` | 解析结果，非图节点快照 |
| `trace profile` | `trace_profile.py:427` | 信号画像聚合（type/bit/source/role/clock…） | 聚合语义 |
| `dataflow segment` | `dataflow.py:217` | `from_signal, to_signal, driver, condition, timing, assign_type, distance[, evidence]` | 路径段语义 |
| `architecture` | `view/architecture.py:24` | MIG 实例/连接（`id,module,parent,depth,ports` / `src,dst,net,...`） | MIG 域，不是 `TraceNode` |
| `tb_join` candidate | `tb_join.py:33` | `signal, name, kind, module, file, line, reason` | 候选匹配结果 |
| `class member` | `classes.py:93` | `node_dict` + `is_rand, rand_mode, type` | 薄扩展层（复用 `node_dict`） |
| `verify finding edge` | `core/query/structural.py:89` | `src, dst, kind, condition, expression` | verify 证据域第 5 个 edge 投影 |

---

## 3. 重叠矩阵

| 字段名 | Snapshot | CLI trace | CLI minimal | Core subgraph | CLI evidence | Graph listing |
|---|---|---|---|---|---|---|
| `id` | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| `name` | ✅ | — | ✅ | — | — | ✅ |
| `module` | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| `kind` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| width | `[msb,lsb]\|null` | `width_msb/lsb/width(int)` | `[msb,lsb]\|null` | `width_msb/lsb/width(int)` | — | detail `width` |
| `precision` | — | ✅ | — | ✅ | — | — |
| `distance` | — | ✅ | — | — | — | — |
| `is_signed` | ✅ | ✅ | — | ✅ | — | — |
| `parent*` | ✅ | `parent` | — | `parent` | — | — |
| `bit_range` | ✅ | ✅ | — | ✅ | — | — |
| `condition*` | `condition`, `condition_chain` | `condition(s)/paths/analysis` | — | `condition` | `condition` | — |
| `source_location` | ✅ 全量 | — | — | `file/line`（可选） | `file/line` 扁平 | — |
| `extra` | ✅ JSON-safe | — | — | — | — | — |

**结论**：字段名有大量重叠，但**没有任何两个投影的字段集与派生规则同时相同**。

---

## 4. 为什么不能强制合并（实测差异）

### 4.1 width 的编码与公式不同

| 投影 | 编码 | 公式 |
|---|---|---|
| Snapshot / CLI minimal | `[msb, lsb]` 或 `null` | 原样 |
| CLI trace | `width_msb` + `width_lsb` + `width`(int) | `max(0, msb - lsb + 1)` |
| Core subgraph | `width_msb` + `width_lsb` + `width`(int) | `max(0, abs(msb - lsb) + 1)` |

对反向/异常 range，trace 与 subgraph 的 `width` 已经不同（见 §4.2 实测）。

### 4.2 precision 的判定策略不同

- CLI trace `node_precision`：先看 `extra` 的 `function_call/runtime_system_call/dynamic`，
  再看 `1'b[01]` 与 `N'...` 字面量 regex，最后看位后缀/宽度。
- Core subgraph `_precision`：只看 `kind == CONST`、`width == 1`、`width > 1`。

实测（本机真实 fixture，baseline `2fe3d74f`）：

```text
minimal_3module CONST id="0", width=(0,0)
  CLI trace : width=1, precision=bit
  subgraph  : width=1, precision=constant

scheduler_minimal bit node id="Scheduler_minimal.s0_reg[0]", width=(1,0)
  CLI trace : precision=bit
  subgraph  : precision=bus
```

不存在 `msb < lsb` 的真实节点，因此 trace 的 `width=0` 分支目前没有真实输入形态；
不要把它当已观察事实。

这是**可观察的 DTO 语义差异**；合并会改变其中一个 CLI 输出，违反 D9
“不得改变现有字段语义”。已登记到
[KNOWN_LIMITATIONS §3.16](../KNOWN_LIMITATIONS.md)。

### 4.3 condition 的语义不同

- Snapshot：`condition` + `condition_chain`，`effective_condition` 重算；
- CLI trace：`condition` + `conditions` + `condition_path(s)` + simplified/analysis；
- CLI evidence：`condition` 为空时回退 `effective_condition`；
- Core subgraph：只有 `condition`，不做路径分析。

四者回答的问题不同（原始边 / 多路径 OR / 单跳证据 / 结构子图），
合并会把“未分析”伪装成“无条件”或反之。

### 4.4 source_location 的形态不同

- Snapshot：完整 `{file, line_start, line_end, column}`；
- CLI evidence：扁平 `file` / `line`（无位置时 `null`）；
- Core subgraph：`file` / `line`（无位置时 `""` / `0`）；
- CLI trace node：不输出位置（避免每个结果节点重复）。

### 4.5 响应体积 / 消费场景不同

Snapshot 是持久化（全保真）；trace 是查询结果（每节点 24 字段）；
subgraph 是有界结构响应（10/12 字段）；listing 是导航（4 字段）。
统一成全局 DTO 会让 listing/subgraph 携带无用字段，或让 snapshot 丢字段。

---

## 5. 决策

**采用“每个上下文一份 canonical projection”，不强制全局合并。**

| 上下文 | Canonical 实现（唯一） | 契约/锁 | 职责 |
|---|---|---|---|
| Snapshot | `SignalGraph.to_dict/from_dict` | `SNAPSHOT_SURFACE.md` + D9 test | 全保真持久化 |
| CLI trace 结果 | `trace_common._node_to_dict` | `JSON_CONTRACT.trace_node` | 条件/距离/粒度查询 |
| CLI 最小身份 | `_common.node_dict` | `JSON_CONTRACT.class_instance` | class/scope 成员 |
| CLI edge evidence | `trace_common.edge_evidence_dict` | `JSON_CONTRACT.edge_evidence` | 单跳证据 |
| Core subgraph | `subgraph._node_dict/_edge_dict` | `JSON_CONTRACT.subgraph_node/edge` | 有界结构子图 |
| CLI graph listing | `locate/graph.py` | `JSON_CONTRACT.graph_node/edge` | 导航列表 |

**变更规则**

1. 同一上下文的字段增删 → 同步其 `JSON_CONTRACT` / `SNAPSHOT_SURFACE`
   + 锁定测试；禁止只改实现。
2. 跨上下文“统一 DTO”不是重构，而是**公开 schema 变更**：需要
   版本策略 + CLI/JSON 契约更新 + 方豆拍板；不得以“去重”为名直接合并。
3. 新命令优先复用上表已有投影；如果只是薄扩展（如 `class member`），
   调用 `node_dict` 后追加字段，不复制基础字段。
4. Snapshot 永远是唯一全保真投影；查询 DTO 不得声称覆盖 snapshot 字段面。

---

## 6. 本轮最小收敛

**没有发现精确重复的完整映射**，因此：

- 未抽 helper、未改任何投影实现（避免“为了去重而改语义”）；
- 新增 `sim/tests/unit/test_d9_dto_mapping_contract.py`，用独立 oracle 锁定：
  - snapshot node = `dataclasses.fields(TraceNode)` 全字段；
  - snapshot edge = `dataclasses.fields(TraceEdge)` - `{effective_condition, condition_ast}`；
  - CLI/core 投影字段集 = `JSON_CONTRACT` 对应 section；
  - 各上下文投影互不相等（防止未来被强制合并）。
- 无新增公开 schema、无 CLI 行为变化。

**重复惯用法说明**：`list(x.width) if x.width else None`、
`getattr(kind, "name", ...)` 等在多个投影出现，但它们是**字段级惯用法**，
不是完整映射实现；抽成 helper 会触及无关命令且不改变字段面，故本轮不做。

**writer 级重复说明**：`SignalGraph.save_snapshot` 与 `SnapshotManager.save`
重复 `tag/git_commit/files/created_at` 赋值（§2.2）。这不是 DTO 投影重复；
前者无 `src/` 消费者且写盘保证不同，本轮不合并，登记为后续清理项。

---

## 7. 已知风险 / 后续

1. **precision/width 双策略**（§4.1/§4.2）未统一：CLI trace 与 core subgraph
   对同一节点可能给出不同 `precision` / `width`。本轮只登记，不修
   （修会改变输出）。见 [KNOWN_LIMITATIONS §3.16](../KNOWN_LIMITATIONS.md)。
2. `SignalGraph.save_snapshot/load_snapshot` 是遗留便捷入口，复用 `to_dict`，
   当前 `src/` 无消费者；如未来清理，应确认无外部脚本依赖（本轮不删除）。
3. `TraceNode.extra` / `TraceEdge.extra` 在 snapshot 只保留 JSON-safe 值；
   查询投影不输出 `extra`（除 `node_dict` 不含），这不是丢失，是投影选择。
4. 任何跨上下文合并都必须先更新 [SNAPSHOT_SURFACE](../dev/SNAPSHOT_SURFACE.md)
   与 `JSON_CONTRACT`，并提升 schema 版本。

---

## 8. 验证记录（2026-11-17）

```text
python3 -m pytest sim/tests/unit/test_d9_dto_mapping_contract.py -q -p no:randomly
# 3 passed

python3 -m pytest sim/tests/unit/test_p158_9_2_snapshot_surface.py -q -p no:randomly
# 10 passed

python3 -m pytest sim/tests/cli/test_json_contract.py -q -p no:randomly
# 39 passed
```

gate 结果见 `agents/dev-deepseek/handoff/D9_handoff.md`。

---

## 9. 参考

- [SEMANTIC_CONTRACTS §1](../dev/SEMANTIC_CONTRACTS.md)
- [SNAPSHOT_SURFACE](../dev/SNAPSHOT_SURFACE.md)
- [Agent JSON 契约](json_contract_2026-10-31.md)
- `sim/tests/unit/test_d9_dto_mapping_contract.py`
- `sim/tests/unit/test_p158_9_2_snapshot_surface.py`
- `sim/tests/cli/test_json_contract.py`
