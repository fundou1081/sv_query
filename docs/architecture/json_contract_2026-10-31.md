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
