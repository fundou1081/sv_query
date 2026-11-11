# Agent JSON 契约（2026-10-31，schema v1）

**目标**: agent 从 `svq capabilities --json` 读取机器可读字段契约，不靠猜命令/字段。
**入口**:

```bash
sv_query capabilities --json | jq '.json_contract'
```

**范围（当前）**: 顶层 envelope + `trace fanin`/`trace fanout` 的 signal/node 字段。
其他 core 命令共享 envelope；命令专属字段按同一策略逐步登记。

## 版本策略

- 当前 `schema_version = "1"`。
- **v1 内允许**：新增可选字段（additive）。
- **必须升版本**：删除/重命名字段、改字段类型、新增必填字段。
- 可空值用 JSON `null`，不用“字段缺失”表达未知。
- `unknown` / `coarse_fallback` / `condition_truncated` / `cycles_detected=null`
  都是**显式降级**，不是失败。

## 顶层 envelope

| 字段 | 类型 | 含义 |
|---|---|---|
| `ok` | boolean | 任一分信号失败则 false |
| `command` | string | 命令名（如 `trace_fanin`） |
| `params` | object | 解析后的请求参数 |
| `result` | object | 命令专属 payload |
| `errors` | array | 分信号错误；ok=true 时为空 |

## trace signal 字段

| 字段 | 类型 | 含义 |
|---|---|---|
| `signal` / `index` | string / int | 请求信号与批内位置 |
| `precision` | `bit`/`bus`/`unknown` | 答案粒度 |
| `coarse_fallback` | boolean | 位查询混入总线/常量 → 降级解读 |
| `dynamic_index` | boolean | 运行期索引影响 → unknown |
| `function_call` | boolean | 函数调用影响（未 inline）→ unknown |
| `runtime_system_call` | boolean | `$random` 等运行期系统调用 → unknown |
| `conditions` | array<string> | 每路径条件表达式（直接边或多路径组合） |
| `condition_truncated` | boolean | 条件路径枚举触顶 |
| `truncated_by_depth` | boolean | depth 边界还有未展开边 |
| `cycles_detected` | boolean\|null | 可达环；null = 预算不足无法判定 |
| `count` / `pre_filter_count` / `truncated` | int/int/bool | 返回数 / 过滤前数 / max_results 截断 |

fanin 额外：`drivers[]`、`driver_count`、`multi_driver`、`conditional_drivers`。
fanout 额外：`loads[]`。

## trace node 字段

| 字段 | 类型 | 含义 |
|---|---|---|
| `id` / `module` / `kind` | string | 图节点身份 |
| `width` / `width_msb` / `width_lsb` | int / int\|null | 位宽与声明范围 |
| `distance` | int | 距查询信号的跳数 |
| `precision` | `bit`/`bus`/`constant`/`unknown` | 节点粒度 |
| `is_signed` / `parent` / `bit_range` | bool\|null / string\|null / array\|null | 符号/父节点/位段 |
| `dynamic_index` / `function_call` / `runtime_system_call` | bool | 三种不可静态判定来源 |
| `condition` | string | 直接边 OR / 多路径 OR；空=无条件 |
| `conditions` | array<string> | 保留的每路径组合 |
| `condition_path` / `condition_paths` | array / array<object> | 首路径原始条件 / 每路径 `{condition,path}` |
| `condition_unconditional` / `condition_truncated` | bool | 无条件路径存在 / 枚举触顶 |

## 示例

```json
{
  "signal": "top.y",
  "precision": "unknown",
  "function_call": true,
  "conditions": ["sel", "!sel"],
  "cycles_detected": false,
  "truncated_by_depth": false
}
```

节点条件：

```json
{
  "id": "top.a",
  "condition": "(!(c2) && c3) || ((c1) && (c2))",
  "conditions": ["!(c2) && c3", "(c1) && (c2)"],
  "condition_paths": [
    {"condition": "!(c2) && c3", "path": ["!(c2) && c3"]},
    {"condition": "(c1) && (c2)", "path": ["c1", "c2"]}
  ]
}
```

## 待扩

- `paths` / `dataflow` / `impact` / `graph nodes` 的字段契约（当前只做 envelope + trace）
- 错误对象（`errors[]`）字段固定化
- 可选 `svq schema --json` 独立命令（若 agent 不想拉完整 capabilities）

---

## P28 扩展（2026-10-31）

契约范围新增 5 组：`paths`、`dataflow analyze`、`trace impact`、`graph nodes`、`error_entry`。

### paths（直接 envelope，无 command/params）

- 基础字段：`ok/src/dst/src_resolved/dst_resolved/bits/directed`
- `one` 模式追加：`found/hop_count/path`
- `all` 模式追加：`count/truncated/all_paths`
- `bits` 结构 = `bit_normalization`：`{src,dst,coarse_fallback}`，每个端点 = `bit_endpoint`
  （`requested_bit/requested_range/resolved/precision/coarse_fallback/kind`）

### dataflow analyze

- result：`from_signal/to_signal/from_resolved/to_resolved/bits/is_reachable/paths_count/
  intermediate_signals/primary_latency_cycles/primary_is_async/all_conditions/clock_domain/
  timing_risk/paths`
- [P158.11.2b] 有界搜索字段：`search_status`（`complete|truncated|unknown`）、
  `truncated`、`truncation_reason`（`max_expansions_reached|deadline_reached|
  max_paths_reached|max_depth_reached`，空串=完整）、`expansions`、`elapsed_s`
  - `is_reachable` 是**三态**：`true` / `false`（搜索完成后确认无路径）/ `null`（未查完）；
    `null` 时 result 内附 `machine.unknown_kind="search_budget_exhausted"`。
  - 对应参数：`--max-expansions`（默认 200000）、`--timeout`（秒，可选）
- path：`path_id/segments/distance/has_conditional/latency_cycles/is_async_crossing/
  latency_note/stage_breakdown`
- segment：`from_signal/to_signal/driver/condition/timing/assign_type/distance`，
  `evidence` 仅在 `--evidence` 时出现（可选字段）

### trace impact

- result：`signals/total_signals/total_paths/total_high_risk_count/failed_signals/risk_model`
- signal：`signal/index/resolved_signal/requested_bit/precision/coarse_fallback/
  total_paths/high_risk_count/modules/paths`
- path：`path/path_type/risk/risk_score/fanout/coverage/condition/clock_domain/suggestion`

### graph nodes

- result：`nodes/total`
- 普通节点：`id/name/kind/module`
- `--detail` 追加：`width/expression/operands/signals/function_name/
  condition/true_branch/false_branch`

### error_entry（trace 分信号错误）

`signal/index/error/error_code`。

> `errors[]` 在不同命令可能是**字符串**（如 `trace overview`）或 `error_entry` 对象
> （如 trace fanin/fanout 分信号错误）；契约 `top_level.errors` 类型标为
> `array<string|error_entry>`，消费方按 `typeof` 分支处理。

---

## P29 扩展：locate / evidence / controlflow（2026-10-31）

### graph edges

- result：`edges[]` + `total`
- edge：`src/dst/kind`

### search（direct envelope，无 `command/params`）

- 顶层：`keyword/target/regex/case_insensitive/total_matches/file_count/files[]`
- file：`file/match_count/lines[]/truncated`
- line：`line/text`

### stats

- result：`total_nodes/total_edges/nodes/edges/modules/elaboration_errors`
- `nodes`/`edges` 是 `{kind: count}` 对象

### trace evidence

- 标准 envelope + **可选 top-level `evidence`**（单信号便捷镜像）
- result：`signals[]/total_signals/failed_signals`
- signal：`signal/index/evidence`
- evidence payload：`signal/source_location/source_text/enclosing_*/enclosing_chain/
  is_verified/credibility_score`

### controlflow analyze

- result：`signal/conditioned_drivers[]/warnings[]`
- driver：`to_node/conditions[]`
- condition：`expr/edge`
- edge：`src/dst/kind/condition`

### controlflow list-conditioned

- 标准 envelope + **可选 top-level `subcommand`**
- result：`signals[]/count`

> 这组再次确认 envelope 并非所有 core 命令统一：
> `search` 是 direct output；`trace evidence`/`controlflow list-conditioned`
> 有额外的 top-level 字段。契约用 `envelope`/`optional_top_level` 显式标注。

---

## P30 扩展：结构/元数据（2026-10-31）

这组命令继续使用 **direct output**（无 `ok/command/params/result` 统一外壳，部分有 `ok`），
契约用 `envelope: "direct"` 标注；成功/错误形态分别登记。

### instances

- 成功：`ok/count/module/instances[]`；item `full_path/name/module_type/parent`
- 错误：`ok/error/path/hint`（见 `direct_error`）

### hierarchy

- `ok/root_count/instance_count/tree_node_count/root/depth/tree[]`
- node：`full_path/module_type/children[]/synthetic`

### ports

- `ok/module/count/by_direction/ports[]`
- port：`port/id/direction/width/in_edges/out_edges`
- `module` 实际是**实例路径**（`top.u`），不是模块类型名

### params

- `ok/instance/module_type/count/parameters[]`
- param：`name/value/is_overridden/is_local_param`
- 错误：`ok/error/path/hint`

### connections

- `ok/resolved_as/instance/module_type/parent/port_count/ports[]`
- port：`port/direction/width/internal_signal`
- 只接受**实例路径**；错误含 `resolved_as`

### class

三种模式共用 `class_result` 的字段并集：

| 模式 | 字段 |
|---|---|
| 无类名 | `ok/count/classes[]` |
| 类详情 | `ok/class/member_count/members[]/instance_count/instances[]` |
| `--member` | `ok/class/member/count/instances[]/note` |

member：`id/name/kind/module/width`；instance：`id/name/kind/module/width`。

### direct_error

通用错误形态：`ok/error/hint` + 命令特有 `path`/`target`/`resolved_as`；
消费方应先用 `ok` 判断，不能假定所有 direct 命令都有统一 errors 数组。

---

## P33 扩展：canonical signal identity（2026-10-31）

### trace signal 新增字段

| 字段 | 类型 | 语义 |
|---|---|---|
| `resolved_signal` | `string|null` | 解析后的图节点 id |
| `resolution` | `exact|relative|bit_base_fallback|not_found|ambiguous|internal` | 解析方式 |
| `candidates` | `array<string>` | ambiguous 时的候选 |
| `suggestions` | `array<string>` | not_found 时的近似名 |
| `error` | `string` | per-signal 错误（成功为空串） |

适用：`trace fanin` / `trace fanout` / `trace impact` / `trace evidence`。

### 语义

- **exact**：完整 id 命中。
- **relative**：唯一后缀命中（`u.a` → `top.u.a`）。
- **bit_base_fallback**：`y[3]` 位节点不存在但父总线存在；`resolved_signal`
  仍是完整位 id，查询保留原回退语义。
- **ambiguous**：多个候选 → `ok=false`，`errors[].error_code=E_SIGNAL_AMBIGUOUS`，
  `candidates[]` 给出候选。
- **not_found**：无候选 → `ok=false`，`errors[].error_code=E_SIGNAL_NOT_FOUND`，
  不再返回 `ok=true + drivers=[]`。

> 这是 grounding P0 的第一步：空结果不再等价于“信号不存在”。

---

## P34 扩展：verify（客观检查，2026-10-31）

### verify consistency

- `result.verified`：所有 check pass 且没有 unknown（不等于“命令成功”）
- `result.total_violations` / `unknown_checks` / `checks[]`
- check：`check/status(checked/skipped)/violations[]/truncated/error?`

检查项：

| check | 语义 |
|---|---|
| `reciprocity` | 信号节点的 fanin/fanout 互逆（抽样，默认 200 节点；跳过实例/常量/父位聚合） |
| `bit_mapping` | `parent` 存在、`parent_bit_start/end` 范围、节点宽度、id 前缀 |
| `connection` | MIG 的 port → internal 映射；internal/port 节点存在 |

> `ok=true` 只表示命令执行；**结论看 `result.verified` 与各 check 的 status**。

### verify claim

- 输入：`--claim JSON` 或 `--claim-file`
- 输出：`claim/status/reason/evidence[]/counterevidence[]`
- `status`：`verified | contradicted | unknown`
- 支持类型：

| type | claim 字段 | 语义 |
|---|---|---|
| `driver` | `signal`,`driver`,`transitive?` | driver 在 fanin 中 |
| `path` | `from`,`to`,`nodes?`,`bidirectional?` | 路径边存在 / 可达；bidirectional 同时查反向 |
| `connection` | `instance`,`port`,`internal` | MIG 端口映射匹配 |
| `bit` | `target`,`source` | 两位节点之间直接边存在；位节点缺失 → unknown |

> 不把“无法证明”伪造成 contradicted；位节点缺失返回 unknown。

---

## P36 扩展：trace profile（波形关联元数据，2026-10-31）

`trace profile` 输出每个信号的静态画像，供外部波形工具对齐：

| 字段 | 语义 |
|---|---|
| `resolved_signal` / `resolution` | canonical id + 解析方式 |
| `aliases` | canonical/leaf/relative 候选名（不保证唯一） |
| `width` / `is_signed` / `kind` / `module` | 信号类型信息 |
| `bit` | `bit_range/parent/parent_bit_start/end` |
| `source` | 声明 `file/line/declaration`；`driver` 为赋值行（evidence resolver 修正） |
| `role` | clock/reset/enable/port/modport |
| `clock_domains` | 唯一 clock domain/信号名 |
| `clocks[]` | `signal/condition/clock_domain` |
| `resets[]` | `signal/condition` |
| `sequential` | `is_sequential/assign_types/stage/stage_known` |
| `driver_count` / `load_count` | 直接驱动/负载数 |
| `error` | per-signal 错误（成功为空串） |

> `stage` 暂未计算：`stage=null, stage_known=false`，不伪造流水级数。
> evidence 缺失时 `source.driver` 可能为 null；aliases 是波形候选名，消歧仍需 canonical id。

---

## P37 扩展：per-driver / per-hop evidence（2026-10-31）

### trace fanin / fanout `--evidence`

默认输出不变；加 flag 后每个 driver/load 多一个 `evidence`：

| 字段 | 语义 |
|---|---|
| `kind` | 边类型 |
| `assign_type` | continuous/always_ff/nonblocking... |
| `condition` | 边条件（空 = 无条件） |
| `expression` | 驱动表达式 |
| `file` / `line` | 边 source_location；缺失为 null |

- 契约：`edge_evidence`；命令的 `optional_node_fields=["evidence"]`。
- `evidence` 只加在**返回的节点**上（过滤/截断后）。

### paths `--evidence`

默认输出不变；加 flag 后：

- 单路径：`edge_evidence[]`，长度 = `len(path)-1`；
- `--all`：`edge_evidence[][]`，与 `all_paths` 对齐；
- 每跳：`edge_evidence` 同结构；无边的 hop 为 `null`（例如纯 parent/bit-select 聚合）。

> evidence 的 `line` 可能来自 edge.source_location（条件行），不是赋值行；
> 需要赋值行时用 `trace evidence`（已做 assignment-line 修正）。

---

## P38 扩展：class relations（2026-10-31）

`class <name> --relations`（direct output）：

| 字段 | 语义 |
|---|---|
| `extends` / `ancestors` | 直接父类 / 祖先链 |
| `subclasses` / `descendants` | 直接子类 / 全部后代 |
| `members` | 类型级成员（class_member） |
| `instances` | 类实例（class_instance） |
| `member_instances[]` | 每个成员的图内实例节点 + count |
| `constraints[]` | 图内 `CONSTRAINS/HAS_*` 边 |
| `methods[]` | 方法定义 + 方法体调用 |
| `methods[].calls[]` | `receiver/method/target_class` |

- `target_class`：裸调用解析到当前类/祖先；receiver 调用类型未解析时为 `null`。
- 继承链来自 `ClassHierarchy`；方法调用来自方法体文本（不展开内部细节）。
- 空关系是事实：`members=[]` / `instances=[]` / `methods=[]`，不臆造。

---

## P39 扩展：waveform path lookup（2026-11-01）

波形工具提供完整 RTL hier path；`trace lookup` **严格**映射：

| 字段 | 语义 |
|---|---|
| `requested` | 原 path |
| `found` | 是否严格命中 |
| `canonical` | 图 canonical id |
| `resolution` | `exact` / `bit_parent` / `not_found` |
| `bit_suffix` | `[3]` / `[7:4]`（bit_parent） |
| `aliases` | port/internal 等别名 |
| `suggestions` | not_found 候选 |
| `width` / `kind` / `module` | 信号元数据 |

- `$root.` 前缀会剥离；首尾空白 trim；
- **不做模糊后缀解析**（与 agent 的 relative 模式区分）；
- 位节点缺失 → canonical=父总线 + bit_suffix，不返回 not_found；
- `found=false` 是正常结果，`ok` 仍为 true；批量看 `result.failed`。

### 尚未覆盖（P39.2/后续）

- interface / modport 路径别名；
- generate 标签与 waveform 工具命名差异；
- escaped identifier 的空白/转义变体（基础 exact 可用）；
- type/enum/array/struct 解码元数据；
- clock posedge/negedge、reset active_low/async、sequential stage。

---

## P39.2 profile 增强（clock/reset/bit，2026-11-01）

### 新增字段

| 字段 | 语义 |
|---|---|
| `type.kind` / `type.known` | NodeKind；`known=false` 表示未解析语义类型 |
| `bit.select` / `bit.kind` / `bit.offset` / `bit.parent_width` | 位/切片/动态索引 + LSB offset |
| `clocks[].edge` | `posedge` / `negedge`（从 enclosing always 解析） |
| `resets[].edge` / `async` / `active_low` | 异步复位边沿/极性 |
| `sequential.always` | enclosing always `{file,line}`（可能为 null） |

### 语义边界

- clock/reset 边沿来自 evidence 的 always 文本；没有 always 证据 → `edge=null`；
- `active_low` 先从条件（`!rst`/`==0`）推断，再从 `_n` 命名推断；仍无法判断 → null；
- `type.known=false`：P39.2 只给 NodeKind，不伪装 enum/struct/array 类型；
- `bit` 对 `bit_base_fallback` 使用请求的 `[3]` 作为 select/offset，parent 是 canonical 总线。

---

## P39.3 path alias index（2026-11-01）

`trace lookup` 现在先查 exact，再查 alias index：

- `resolution=exact|alias|bit_parent|ambiguous|not_found`
- `matched_via=exact|alias|bit_parent|null`
- escaped identifier：登记去反斜杠的可读变体；
  若变体与真实节点冲突 → `ambiguous`（不猜）。
- port/internal aliases 仍来自 MIG。

> interface/modport 与 generate `genblk` 命名别名仍不在本索引内（见 KNOWN）。

---

## P40.1 profile type metadata（2026-11-01）

`profile_signal.type` 从 NodeKind 升级为语义类型（module/instance 内 Port/Variable）：

| 字段 | 语义 |
|---|---|
| `known` | 是否解析到 semantic symbol |
| `name` / `canonical` | 声明类型 / canonical type |
| `is_enum/is_struct/is_union/is_unpacked_array/is_array` | 类型分类 |
| `array_element` | 数组元素类型 |
| `bit_width` / `is_signed` | 语义位宽/符号 |
| `enum_values[]` | `name/value`（enum） |
| `packed_members[]` | `name/width/offset/signed`（struct/union） |

- 只解析 module/instance 的 Port/Variable；class/constraint 仍 `known=false`；
- struct 成员 offset 是 LSB 在聚合中的位置；
- enum value 保留源码字面量；不做运行期编码转换。

---

## P40.2 sequential stage / sample（2026-11-01）

`profile_signal.sequential` 新增：

| 字段 | 语义 |
|---|---|
| `stage` | pipeline stage（仅 detect_pipeline 识别出的 REG） |
| `stage_known` / `stage_source` | 是否已知 / `pipeline_detect` |
| `stage_unknown_reason` | `combinational` / `not_pipeline_reg` / `no_pipeline_detected` |
| `sample` | 采样边沿，如 `posedge top.clk` |
| `sample_unknown_reason` | `combinational` / `multi_clock` / `clock_edge_unknown` |
| `always` | enclosing always `{file,line}` |

- stage 只对 REG 且 pipeline 检测命中时给；组合/状态机不猜。
- 多 clock / 无 edge 时 `sample=null` + reason，不伪造采样时刻。
- 所有 unknown 都显式，保持 `stage_known=false`。

---

## P41.1 struct member type（2026-11-01）

`profile_signal.type` 对 struct 成员（如 `top.p.a`）：

| 字段 | 值 |
|---|---|
| `known` | true |
| `name` | `pair_t.a`（父类型.成员） |
| `canonical` | 父 struct canonical type |
| `bit_width` / `is_signed` | 成员宽度/符号 |
| `member_of` | 父 struct 类型 |
| `member_offset` | 成员 LSB offset |
| `packed_members` | 成员自身不是 aggregate，通常 [] |

> 只对 module/instance 内的 packed struct 成员推导；嵌套/class 成员仍 unknown。

---

## P41.2 waveform manifest（2026-11-01）

`trace manifest` 批量输出 waveform 工具可直接消费的条目：

```json
{
  "waveform_path": "top.u.data[3]",
  "index": 0,
  "found": true,
  "lookup": { ...lookup_path... },
  "profile": { ...profile_signal... }
}
```

- 一次 graph build，批量 paths；
- 未找到：`found=false, lookup.resolution=not_found, profile=null`；
- 找到：`lookup` + 完整 `profile`（type/bit/clock/reset/stage/source）；
- 契约：`manifest_entry` / `manifest_result`。

---

## P42.1 interface/modport connection aliases（2026-11-01）

`lookup_path.aliases` 现在包含 **CONNECTION 边相邻节点**：

- interface 实例成员 ↔ modport 成员：
  `top.u_if.data` ↔ `top.u_prod.m.data`
- 模块端口 ↔ 外部网络；
- 只用于完整 path 的别名发现；exact 仍优先；
- alias 冲突仍返回 ambiguous。

> CONNECTION 是物理网络连接，不等于语义驱动；lookup 只做路径映射，不改变 fanin/fanout 结论。

---

## P43.1 generate 路径/类型（2026-11-01）

- **路径**：graph 使用 pyslang/LRM 的 generate hier path：
  - 未命名 loop：`top.genblk1[0].x`
  - 未命名 if：`top.genblk2.y`
  - 命名 generate：`top.gen_accum[0].prod`
  `trace lookup` 严格 exact 命中，无需额外别名。
- **type**：`_build_type_lookup` 现在递归 generate scope（entry/if），
  `top.genblk1[0].x` 可解析 `type.name=logic`。
- 生成 scope 本身的节点（如 `top.genblk1[0]`）没有 signal type，保持 unknown。

> 若波形工具对 generate 使用非 LRM 命名（如零填充 `genblk01`），需要该工具
> 提供样例；当前不猜别名，避免错配。

---

## P44 Scope 层收敛（2026-11-01）

### capabilities `mode`

每个命令新增：

```
mode: scope | trace | verify | locate | state | exp
```

映射：

- scope: scope/instances/hierarchy/ports/params/connections/class
- trace: drivers/loads/trace */paths/dataflow/controlflow
- verify: verify *
- locate: graph/search/stats/capabilities
- state: snapshot *
- exp: audit/diagnose/view

### `scope <instance>` 聚合

标准 envelope；直接输出：

| 字段 | 语义 |
|---|---|
| `scope` / `canonical_id` | scope path |
| `module_type` / `parent` | 类型/父 |
| `children[]` | 直接子实例 + canonical_id |
| `ports[]` | name/direction/width/canonical_id/internal_signal |
| `parameters[]` | name/value/is_overridden/is_local_param |

- 支持实例路径；顶层模块 path（如 `top`）也可作为 scope；
- scope 只做入口/上下文，不做因果追踪。

---

## P44.5 scope 可发现性（2026-11-01）

`scope` 增加：

| 字段 | 语义 |
|---|---|
| `kind` | `instance` / `generate` / `class` |
| `signals[]` | scope 直接子信号/端口：name/canonical_id/kind/width/is_port/direction |
| `members[]` | class scope 的类型级成员 |
| `instances[]` | class scope 的实例 |

- interface 实例：`kind=instance`，`signals` 列出 interface 成员（data/valid 等）；
- generate scope（如 `top.genblk1[0]`）：`kind=generate`，`signals` 列出直接子信号；
- class 类型（如 `packet`）：`kind=class`，返回 members/instances，不展开方法体；
- 普通实例：`signals` 同时列出端口和直接内部信号。

---

## P45 模拟 waveform 端到端（2026-11-01）

新增 fixture `waveform_end_to_end.sv` + `test_waveform_end_to_end.py`，覆盖：

| path | 覆盖点 |
|---|---|
| `$root.top.clk` | `$root` 归一化 |
| `top.genblk1[0].x` | 未命名 generate |
| `top.gen_if.y` | 命名 generate |
| `top.u_if.data` | interface 成员 |
| `top.u_prod.m.data` | modport 成员 + connection alias |
| `top.p.a` | packed struct 成员 |
| `top.gen_sig[3]` | bit_parent |
| `top.not_here` | not_found |

同时修复：

- `resolve_signal` 全局支持 `$root.`；
- packed struct 成员节点（node.name 只有成员名、parent 指向父总线）可解析 member type。

---

## P47 class member / UVM 可发现性（2026-11-01）

`class <name> --member <member>` 现在返回两组：

| 字段 | 语义 |
|---|---|
| `instances[]` | **图内已存在**的实例成员节点（原行为） |
| `count` | 图内节点数 |
| `candidates[]` | 语义推导的完整实例路径（不造图节点） |
| `candidate_count` | 候选数 |

candidate：

| 字段 | 语义 |
|---|---|
| `canonical_id` | 实际实例成员路径（如 `top.e.p.addr`） |
| `member` | 成员名 |
| `class_instance` | 所属实例路径 |
| `in_graph` | 图内是否已有节点 |
| `kind` / `width` | 类型级成员信息 |

- 从真实根 class 实例出发，沿 `CLASS_INSTANCE` 成员递归；
- type-level 成员实例（module 是 class 名）不作为根；
- 不往图里造节点，保留“未使用成员不臆造”的图语义；
- `in_graph=false` 表示语义上存在、但 RTL/graph 未使用。

---

## P48 条件化简 / 互斥（2026-11-01）

### L1 局部布尔化简

fanin/fanout 的每个节点/路径新增：

| 字段 | 语义 |
|---|---|
| `condition_simplified` | L1 化简后的 OR；原始 `condition` 不变 |
| `conditions_simplified` | 每个原始条件的化简形式 |
| `condition_paths[].simplified` | 单路径化简 |
| `condition_paths[].analysis` | 该路径分析结果 |
| `condition_analysis` | changed/method/confidence/four_state_safe/tautology/unsat/analysis_incomplete/error |
| `condition_analysis_incomplete` | 有解析失败，化简不权威 |

支持只含 `! / && / || / 括号` 的布尔 IR；原子整体保留。
**不假设四态补元律**：`a && !a` 不化简为 false。

### L2 语法级互斥

fanin signal 新增：

| 字段 | 语义 |
|---|---|
| `driver_conflict` | `none / possible / proven_exclusive_2state / unknown` |
| `driver_conflict_analysis` | status/method/confidence/four_state_safe |

- 只证明 `a` vs `!a` 的语法互补；
- `four_state_safe=false`：四态下 else ≠ !cond；
- 无分支 group/casez/unique 支持。

---

## P49 全图 reciprocity（2026-11-01）

`verify consistency --full --checks reciprocity`：

- `mode=full`：遍历所有信号节点，不抽样；`truncated=false`；
- 排除范围显式：
  - `non_signal`：实例/class/表达式节点；
  - `bit_like`：位/切片节点（使用父总线 fallback，严格 edge reciprocity 不适用）；
  - `constant`：字面量驱动/负载；
- `coverage.bit_level_reciprocity = not_applicable`；
- 全图完整检查的是**非位信号节点**；位级一致性由 `bit_mapping` 单独检查。

> 全图模式在 verilog-axi 上约 50s；适合验证/CI，不作为默认查询。

---

## P50 bit-level consistency（2026-11-02）

`verify consistency --checks bit` 扩展为结构一致性：

| 检查 | 语义 |
|---|---|
| `parent_missing` | parent 节点不存在 |
| `parent_edge_missing` | range-select 主节点缺少到 parent 的 BIT_SELECT/MEMBER_SELECT |
| `parent_range_out_of_bounds` | parent 位范围越界 |
| `bit_range_mismatch` | bit_range 与 parent_bit_start/end 不一致 |
| `width_mismatch` | 子节点宽度与 parent 位宽不一致 |
| `id_parent_mismatch` | 位选 id 不以 parent[ 开头 |

- 单 bit 展开节点/struct 成员/array element 不会被误判为“缺 edge”；
- `bit_select_checked` / `index_like` 显式区分；
- 全量 parent nodes，不抽样。

---

## P51 位选 ID 归一化（2026-11-02）

- `bus[base +: width]` → graph id `bus[base+width-1:base]`；
- `bus[base -: width]` → `bus[base:base-width+1]`；
- `base_chain` 末位使用归一化 full_id；
- multi-top filelist 每个 top 用自己的 namespace；
- 只对直接拷贝 edge 做 slice 位展开；
- graph cache v14 强制失效旧位选图。

位级一致性剩余 `parent_range_out_of_bounds` 主要是 parent width 元数据问题。

## P144 schema 决议（2026-11-09）

这些不是新 schema 版本，而是对既有 v1 歧义的显式登记；新增字段均为可选
（`id`、`truncated`、`complete`、`reason`、`envelope`、`write_scope`）。

### envelope

- 标准：`ok/command/params/result/errors`
- direct：命令自定义顶层；目前为 `capabilities`、`search`、`snapshot list`、
  `snapshot compare`
- 机器可读位置：`capabilities.commands[].envelope`
- `json_contract.envelope_policy` 是唯一规则源。

### optional/null

- 已知空值：字段存在且为 `null`
- 不适用：字段可省略，但必须由命令 schema 标明
- 缺失不等于 `false`/`0`

### errors[]

允许 `string | error_entry`；`error_entry` 至少含 `error`。
trace 命令的 `error_entry` 还含 `signal/index/error_code/resolution/candidates`。
`json_contract.errors_policy` 为唯一规则源。

### write scope

`core.readonly=true` 表示不改 RTL/项目源文件，不是“绝不写盘”。
`capabilities.commands[].write_scope`：

```text
none    不写盘
cache   只写 svq cache/snapshot
output  只写显式指定的输出文件
```

### constraint block

`trace constraints` 输出 canonical `id`，`block` 保留为 v1 alias；
`constraint_block` 两者均已登记。

### constraint neighborhood

`summary.truncated`：`--max-nodes` 触发预算截断时为 true。

### coverage

`trace covergroups` / `trace coverpoints` / `trace covergroup` 输出
`complete:true` + `reason`；解析失败仍为 `ok:false`。
`complete` 只表示命令完成，不证明覆盖语义完整。
