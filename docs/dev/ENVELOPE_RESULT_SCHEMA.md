# Per-command result key schemas — P182.2b

> **状态**: 26/26 core standard result 必需键可执行校验；值/类型见 [ENVELOPE_RESULT_TYPES](ENVELOPE_RESULT_TYPES.md)。
> **来源**: `python3 tools/check_envelope_schema.py --schema-results`
> **上游**: [ENVELOPE_JSON_SCHEMA](ENVELOPE_JSON_SCHEMA.md)（顶层）/ [ENVELOPE_INVENTORY](ENVELOPE_INVENTORY.md)

## 1. 规则

对每个 core standard 命令，从 `JSON_CONTRACT["commands"][cmd]["result_fields"]` 生成：

```json
{
  "type": "object",
  "required": ["..."],
  "additionalProperties": true
}
```

`optional_result_fields` 中的键不要求存在：

- `trace covergroup`: `links` / `samples`（按 mode 互斥）
- `filelist prune`: `output` / `written` / `dry_run` / `backup` / `requires_apply`

## 2. 覆盖

- 26 个 core standard 成功 case（P182.1c manifest）；
- 复用 tb-join 临时 snapshot setup；
- 只验证 `result` 顶层必需键，不验证字段值类型、枚举或嵌套元素。

## 3. 本次修正的 contract 漂移（纠错，非 schema 演进）

这些修改是纠正“声明与真实输出不符”，不是新增对外契约能力；因此
`JSON_CONTRACT.schema_version` 保持 `1`，但文档必须明确记录。

- `trace fanin` / `trace fanout` 的 `result_fields` 原为 `drivers` / `loads`
  （那是 `signals[]` 内层字段），已改为实际 result 顶层字段；
- `trace covergroup.links` / `samples` 标为 optional（按 mode 互斥）；
- `filelist prune` 的 `output` / `written` / `dry_run` / `backup` /
  `requires_apply` 标为 optional（仅 `--output` 时出现）。

## 4. 使用

```bash
python3 tools/check_envelope_schema.py --schema-results
# schema-results: PASS (26/26)
```

本 gate 当前未接入 `run_gates.sh`。`--schema-results` 只验证 result 顶层键；
`ok` 已由本 gate 同时检查，但 full envelope 仍应与 `--schema-core` 同跑。
