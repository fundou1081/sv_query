# Direct Envelope Contract — P182.1e (static)

> **状态**: 只读契约（13/13）；`--direct-contract` 静态检查，不执行 CLI，不接入 `run_gates.sh`。
> **来源**: `python3 tools/check_envelope_contract.py --direct-contract`
> **上游**: [ENVELOPE_INVENTORY](ENVELOPE_INVENTORY.md) / [ENVELOPE_FAILURE_CONTRACT](ENVELOPE_FAILURE_CONTRACT.md)

## 1. 决策

`direct` 不是“没有契约”，而是：

> **显式允许命令自定义根形状；每个 direct 命令必须在 `JSON_CONTRACT` 中有条目，并在此表登记允许的根。**

不允许“新 direct 命令默认随便输出”；新增 direct 必须同时加 contract 条目和本表。

## 2. 13 个 direct 命令

| 命令 | 允许根 | 备注 |
|---|---|---|
| `instances` | object | `ok/count/module/instances` |
| `connections` | object | `ok/...` |
| `hierarchy` | object | `ok/...` |
| `params` | object | `ok/...` |
| `ports` | object | `ok/...` |
| `class` | object | 列出/详情/成员形状 |
| `paths` | object | direct base + mode 字段 |
| `search` | object | 无 `ok`，字段直接暴露 |
| `capabilities` | object | `schema_version/layers/commands` |
| `snapshot save` | object | `ok/...` |
| `snapshot list` | **list or object** | 无 tag → list；带 tag → object；无 `ok` |
| `snapshot compare` | object | 无 `ok`；差异结果字段直接暴露 |
| `snapshot delete` | object | `ok/...` |

## 3. 显式例外

- **`snapshot list` 双根**：
  - `snapshot list --json` → list；
  - `snapshot list <tag> --json` → object；
  - 不能用一个固定根断言覆盖两种模式。
- **无 `ok` 的 direct**：`search`、`capabilities`、`snapshot list`、`snapshot compare`；它们不是 standard 失败信封候选。
- **`paths`**：2026-11-18 P182.1c 已从 registry standard 改为 direct；CLI 输出不变。

## 4. 不承诺

- 不为 direct 命令强制 `rc/ok` 一致；失败形状仍是逐命令的，P182.2 schema 再决定；
- 不把 direct 根 shape 与 standard 的 `{ok,command,params,result,errors}` 混同；
- 不用本契约替代真实执行测试；它只锁静态登记面。

## 5. 使用

```bash
python3 tools/check_envelope_contract.py --direct-contract
# direct-contract: PASS (13/13)
```

缺失 contract、缺失登记、未知 direct、数量漂移 → exit 1。
