# Executable envelope JSON Schema — P182.2 (top-level)

> **状态**: top-level standard success schema 可执行；26/26 matrix PASS。
> **来源**: `python3 tools/check_envelope_schema.py --schema-core`
> **上游**: [ENVELOPE_INVENTORY](ENVELOPE_INVENTORY.md) / [ENVELOPE_FAILURE_CONTRACT](ENVELOPE_FAILURE_CONTRACT.md)

## 1. 范围

本阶段只定义 **standard success 顶层信封**，从 `JSON_CONTRACT["top_level"]` 生成：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["ok", "command", "params", "result", "errors"],
  "properties": {
    "ok": {"const": true},
    "command": {"type": "string"},
    "params": {"type": "object"},
    "result": {"type": "object"},
    "errors": {
      "type": "array",
      "maxItems": 0,
      "items": {"type": ["string", "object"]}
    }
  },
  "additionalProperties": true
}
```

`additionalProperties=true` 放行 contract 明写的 `optional_top_level`
（`seeds` / `evidence` / `subcommand`），同时不限制其他额外键（打错的键不会被本 schema 拒绝）。

## 2. 覆盖

- 26 个 core standard 成功 case（P182.1c manifest）；
- 使用真实 fixture；`trace tb-join` 在临时 snapshot 目录 setup；
- 只验证顶层，不验证 per-command `result` 内部字段。

## 3. 明确不覆盖

- per-command result schema（P182.2b，见 [ENVELOPE_RESULT_SCHEMA](ENVELOPE_RESULT_SCHEMA.md)）；
- direct 13 条（P182.1e 静态契约）；
- exp 6 条；
- failure schema（P182.1f 用 rc/ok/error_code 契约）；
- truncated/partial 语义。

## 4. 使用

```bash
python3 tools/check_envelope_schema.py --schema-core
# schema-core: PASS (26/26)
```

本 gate 当前未接入 `run_gates.sh`；接入前需评估额外执行时长。
