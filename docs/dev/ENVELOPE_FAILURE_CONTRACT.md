# Envelope Failure Contract — P182.1f (gate)

> **状态**: 契约 gate 可用（26/26 PASS）；**尚未接入 `run_gates.sh`**，违规 exit 1。
> **来源**: `python3 tools/check_envelope_contract.py --matrix-failure`
> **Baseline**: 053b77fd
> **日期**: 2026-11-18
> **上游**: [ENVELOPE_FAILURE_INVENTORY](ENVELOPE_FAILURE_INVENTORY.md)（P182.1d 只读观测）

## 1. 契约范围

本契约只裁决 26 个 core standard 命令在**固定失败输入**上的三个可观察事实：

1. 进程退出码 `rc`；
2. 顶层 `ok`；
3. 混合例外下 `errors[].error_code`。

它**不**裁决 `result`/`params` 内容、错误消息文本、严格命令的
`error_code`/`errors` 形状，也不覆盖 direct / exp / truncated 命令。
断言之外的行为保持现状，不因本 gate 通过而被声明为“正确”。

## 2. 严格规则

对 **不在** [§3 例外列表](#3-唯一混合例外恰好四条) 中的每一条失败输入：

```text
operational failure => rc = 1 且 顶层 ok = false
```

任一条件不满足即 `FAIL`，进程 exit 1。失败输入复用 P182.1d 的
26 条 manifest（每个 core standard 命令恰好一条），不另建第二份清单；
manifest 的数量、registry 覆盖、fixture 存在性由静态检查先行校验。

## 3. 唯一混合例外（恰好四条）

| 命令 | rc | ok | errors | 每条 `error_code` |
|---|---|---|---|---|
| `drivers` | 0 | false | 非空 list | `E_SIGNAL_NOT_FOUND` |
| `loads` | 0 | false | 非空 list | `E_SIGNAL_NOT_FOUND` |
| `trace evidence` | 0 | false | 非空 list | `E_SIGNAL_NOT_FOUND` |
| `trace profile` | 0 | false | 非空 list | `E_SIGNAL_NOT_FOUND` |

**为什么是这四条**：它们是按 signal 逐个返回结果的查询命令。目标 signal
不存在时，结果按 signal 记录在 `errors[]` 里（`E_SIGNAL_NOT_FOUND`），
调用本身仍完成，因此现有实现用 `rc=0 + ok=false` 表达“部分/全部目标未找到”。
P182.1b 与 [KNOWN_LIMITATIONS §3.19](../KNOWN_LIMITATIONS.md) 已记录该形态与
`rc≠0 ⟺ ok:false` 候选规则的冲突；P182.1f 的裁决是**把它固化为显式
allowlist**，而不是静默接受所有 `rc=0/ok=false`。

allowlist 是封闭集合：新增第五条必须同时改契约文档、manifest 测试和
`HYBRID_ALLOWLIST`，不能靠“同类命令”自行扩张。

## 4. 不是例外的“未找到即数据”

以下形态**不属于**混合例外，仍按严格规则处理：

- **`trace lookup` / `trace manifest` 的未知 path**：返回 `ok=true`、
  `found=false`，是“查询成功、结果为未找到”的业务数据，不是 operational
  failure。它们的失败输入改用缺失源文件，因此必须 `rc=1 + ok=false`。
- **`paths` 的无匹配结果**：同样属于数据结果，不是失败；`paths` 本身已是
  direct 命令，不在本 26 条 core standard manifest 内，也不在 allowlist。
  若将来纳入失败矩阵，其 operational failure 必须 `rc=1 + ok=false`。
- 其余命令（`scope`、`verify*`、`dataflow`、`controlflow`、`stats`、
  `graph*`、`filelist prune` 等）没有任何例外。

“未找到”只有在 §3 四条命令中、且以 `errors[].error_code =
E_SIGNAL_NOT_FOUND` 表达时，才允许 `rc=0`。

## 5. gate 行为

- 真实执行 26 条失败输入；任一命令执行异常、超时、无 JSON 根、`rc`/`ok`
  不符或混合例外缺错误码，都记为 `FAIL`；
- `NO_FAILURE_INPUT` 记为失败（打印原因，exit 1），**不静默跳过**；
- manifest 自身问题（数量、覆盖、fixture 缺失）同样 `FAIL`；
- 文本输出逐条 `PASS/FAIL`，末行 `matrix-failure: PASS|FAIL (n/26)`；
- 不改 CLI / `src/` / registry；当前未接入 `tools/run_gates.sh`。

## 6. 复现

```bash
# gate：当前树 26/26 PASS，exit 0
python3 tools/check_envelope_contract.py --matrix-failure

# 定向测试（含 operational rc0 / hybrid rc1 / 缺 E_SIGNAL_NOT_FOUND 注入）
python3 -m pytest sim/tests/unit/test_p182_1f_failure_contract.py -q -p no:randomly
```

## 7. 不能从本契约得出的结论

- 不能推断 22 条严格命令已有统一的顶层 `error_code` 或 `errors` 形状
  （属 P182.2 schema）。
- 不能把四条 hybrid 的 `rc=0` 当成全局规则或“推荐行为”；它只是冻结的例外。
- 不能推断 direct / exp 命令的失败行为。
- 不能替代成功路径矩阵（`--matrix-core`）或 canary（`--canary`）。
