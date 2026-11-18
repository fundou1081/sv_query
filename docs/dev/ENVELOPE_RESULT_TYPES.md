# Result value types — P182.2c (high-value slice)

> **状态**: 9 个高价值命令 + 2 个变体；11/11 PASS。
> **来源**: `python3 tools/check_envelope_schema.py --schema-types`
> **上游**: [ENVELOPE_RESULT_SCHEMA](ENVELOPE_RESULT_SCHEMA.md)

## 1. 三个契约决定

1. **`result_fields` = 必填最小子集**，不是完整字段集；额外键允许。
2. **mode-dependent 字段显式 optional**；`trace covergroup` 增加 `--rand` 变体。
3. **值类型优先从 `JSON_CONTRACT` 的 `stats_result` / `graph_*_result` /
   `verify_claim_result` / `dataflow_result` 派生**；手工表仅补 contract 未覆盖字段。
   `tools/llm_schema.json` 仅保留为遗留 trace 辅助。

## 2. 覆盖

| 命令 | 类型覆盖 |
|---|---|
| `stats` | 6 个 result 顶层字段 |
| `drivers` / `loads` | 6 个字段 |
| `graph nodes` / `graph edges` | 2 个字段 |
| `controlflow analyze` | 4 个字段 |
| `dataflow analyze` | 20 个字段 |
| `verify claim` | 5 个字段，status enum |
| `trace covergroup` | 采样字段 + `--rand` 变体 |
| `dataflow analyze` | 增加 no-path 变体；`primary_latency_cycles` 允许 null |

共 **9 个命令 + 2 个变体 = 11 case**。

## 3. 不覆盖

- 剩余 17 个 core standard 命令（P182.2d）；
- 数组元素/嵌套 object 的 schema；
- direct 13 条、exp 6 条、failure schema；
- `tools/llm_schema.json` 的 trace 细粒度 schema（遗留辅助）。

## 4. 使用

```bash
python3 tools/check_envelope_schema.py --schema-types
# schema-types: PASS (11/11)
```

本 gate 当前未接入 `run_gates.sh`。
