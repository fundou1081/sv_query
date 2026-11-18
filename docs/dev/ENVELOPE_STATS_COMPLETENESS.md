# stats / elaboration completeness — P182.3

> **状态**: 成功 stats 的 `elaboration_errors=[]` 与 malformed JSON 结构化失败已锁定。
> **来源**: `python3 tools/check_stats_completeness.py`
> **上游**: [ENVELOPE_INVENTORY](ENVELOPE_INVENTORY.md) / [ENVELOPE_RESULT_TYPES](ENVELOPE_RESULT_TYPES.md)

## 1. 契约

### 成功

`stats --json` 成功（rc=0, ok=true）时：

```text
result.elaboration_errors == []
```

agent 不需要在成功信封里再猜“是否有 elaboration **错误**”。

### 失败

malformed RTL（例如 unknown module）在 `--json` 下必须是：

```json
{
  "ok": false,
  "command": "stats",
  "error": "...",
  "error_code": "E_ELABORATION_FAILED",
  "errors": ["..."]
}
```

并且：

- rc=1；
- **没有** `result`（不得把 partial graph 当成功返回）；
- stdout 是 JSON，不是裸 stderr 文本；
- filelist 无有效源文件时使用共享映射 `E_FILELIST_INCOMPLETE`，不要硬编码成
  `E_ELABORATION_FAILED`。

## 2. 附带修正

- `JSON_CONTRACT["stats_result"]["elaboration_errors"]` 改为 `array<object>`；
- `tools/llm_schema.json` 的 `stats.elaboration_errors.items` 从 string 改为 object；
- D12 A/B 对 `stats_result` 的本次契约修正如实归一化，并显式断言新类型。

## 3. 不覆盖

- 不恢复 partial graph / `--no-strict`；
- 不改其他命令的错误出口；
- 不新增 `complete` / `partial` 字段（本阶段只锁成功即无 elaboration 错误）。

## 4. 使用

```bash
python3 tools/check_stats_completeness.py
# stats-completeness: PASS (success empty + structured failure)
```

本 gate 当前未接入 `run_gates.sh`。
