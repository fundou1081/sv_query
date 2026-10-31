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
