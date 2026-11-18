# Result value types — P182.2c high-value + P182.2d remaining

> **状态**: 26/26 core standard 命令 + 2 个变体；`schema-types: PASS (28/28)`。
> P182.2c 完成 9 个高价值命令；P182.2d 补齐剩余 17 个。
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

P182.2d 追加的 17 个命令（逐命令字段数）：

```text
trace evidence 3 / trace profile 3 / trace lookup 4 / trace manifest 4
trace constraints 4 / trace constraint-neighborhood 5 / trace tb-join 6
trace frontier 4 / trace constraint-chain 10 / trace covergroups 4
trace coverpoints 5 / controlflow list-conditioned 2 / verify consistency 6
verify structural 9 / scope 11 / filelist prune 12 / graph subgraph 5
```

其中 `verify structural` 的 5 个额外字段当前是 property、不是 required；
`filelist prune` 的 output 组仍是 optional。

P182.2c：9 个命令 + 2 个变体 = 11 case；P182.2d 补齐剩余 17 个命令，
现在共 **26 个命令 + 2 个变体 = 28 case**。

## 3. 不覆盖

- 数组元素/嵌套 object 的完整 schema（本阶段只校验顶层类型）；
- direct 13 条、exp 6 条、failure schema；
- `tools/llm_schema.json` 的 trace 细粒度 schema（遗留辅助）。

## 4. 使用

```bash
python3 tools/check_envelope_schema.py --schema-types
# schema-types: PASS (28/28)
```

本 gate 当前未接入 `run_gates.sh`。
