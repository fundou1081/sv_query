# P125 independent intake results

**日期**: 2026-11-09
**范围**: 3 个 OpenTitan DV-derived tasks ×2 模型
**结果**: 6/6 exact；0 false-confident；0 false-found

---

## 1. 任务

来自 worker 的 independent intake：

1. UART noise-filter discovery（不给 canonical signal）；
2. I2C controller-halt verify/abstain（4 verified + tx_pending unknown）；
3. UART system-loopback canonical path（bypasses synchronizer）。

## 2. 结果

| task | MiniMax | DeepSeek |
|---|---|---|
| UART discovery | ✅ 96.6s / 56 calls | ✅ 50.9s / 28 calls |
| I2C verify/abstain | ✅ 14.9s / 12 calls | ✅ 20.9s / 14 calls |
| UART sysloop path | ✅ 16.9s / 14 calls | ✅ 24.0s / 10 calls |

合计：

```text
6/6 exact
0 false-confident
0 false-found
0 timeout
224s / 133 tool calls
```

## 3. 关键观察

### Discovery 能工作，但成本高

T1 没有给 canonical id，模型必须从 UART register file 里找到
`reg2hw.ctrl.nf.q`，再追到 `rx_in_mx`。

- MiniMax 56 calls / 96.6s；
- DeepSeek 28 calls / 50.9s；
- 两者都正确。

这证明 discovery **不是完全不可做**，但一个任务不足以证明需要专门的 search 功能。

### Verify/abstain 正确保留 unknown

T2 的 `tx_pending` 不存在于 `CONTROLLER_EVENTS`，两个模型都返回：

```text
unknown
```

而不是 `contradicted`，也没有伪造节点。

### Path canonical 正确

T3 两个模型都返回 2-hop：

```text
tx_out -> rx_in.ternary_sys_loopback -> rx_in
```

并正确判断 bypasses synchronizer。

## 4. 决策含义

```text
discovery：可做，但只有 1 个样本；不据此加 search 功能
verify/abstain：已验证，不需要新功能
canonical path：已验证，不需要新功能
```

当前独立 intake 没有显示新的核心功能缺口。

## 5. 边界

- 3 个任务；
- 来自 UART/I2C testplan 的 5 个 testpoint；
- ground truth 由 worker 从 spec/source 先确认，再 CLI 交叉验证；
- 仍有 task-author 与 tool 作者同一团队的问题；
- 不是用户研究；
- 不是 fault localization / patch。
