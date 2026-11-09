# OpenTitan UART continuous run（P121）

**日期**: 2026-11-09
**性质**: 同一套任务、同一套工具，连续跑 5 任务 ×2 模型
**结果**: 9/10 exact；1 false-confident；0 false-found

---

## 1. 命令与成本

```bash
cd /Users/fundou/my_dv_proj/sv_query
python3 tools/benchmark/run_opentitan_tasks.py \
  --models MiniMax-M3 DeepSeek-Flash \
  --output /tmp/opentitan_continuous.json
```

```text
wall: 513.31s (8m33s)
cells: 10
tool calls: 194
rc != 0: 0
json_repaired: 0
```

无 provider / rate-limit / auth 问题。

## 2. 结果

| task | MiniMax | DeepSeek |
|---|---|---|
| T1 INTR_TEST gate | ✅ 87.7s / 49 calls | ✅ 151.8s / 49 calls |
| T2 RX path | ❌ 46.5s / 22 calls | ✅ 145.2s / 39 calls |
| T3 RX evidence | ✅ 11.1s / 4 calls | ✅ 10.3s / 3 calls |
| T4 verify claims | ✅ 14.8s / 6 calls | ✅ 36.6s / 18 calls |
| T5 unknown/direction | ✅ 5.1s / 2 calls | ✅ 4.2s / 2 calls |

合计：

```text
9/10 exact
1 false-confident
0 false-found
```

## 3. 唯一失败：T2 canonical path

MiniMax 返回：

```text
13 hops / 14 nodes
rx_sync -> rx_in_mx -> rx_in -> rx_val_q
```

期望：

```text
18 hops / 19 nodes
包括 rx_sync_q1, rx_sync_q2, rx_in_maj,
两个 ternary 节点
```

模型自己的 notes 里承认看到了 18-hop 变体，但仍选择了 13-hop，并标成：

```text
path_kind: canonical
confidence: high
```

这是 **path canonical 语义歧义**，不是 provider 错误。

当前工具：

```text
intent=path       最短
intent=deep_path  最长
```

但 OpenTitan 的“canonical”既不是最短，也不一定是最长；`--canonical` 是另一种选择策略。

## 4. 代码/任务变更

```text
sv_query: 0 dirty files
OpenTitan: 0 tracked modifications
task JSON: unchanged
runner: unchanged
```

没有为了这次运行改任何文件。

## 5. 结论

```text
连续 run 可执行；
9/10；
唯一失败是 canonical path 选择歧义；
没有 false-found；
没有 provider 问题。
```

## 6. 下一步

必须修 path 语义，而不是继续换模型：

```text
path      明确是 shortest 还是 canonical
deep_path 明确是 longest 还是 canonical
```

否则同一题会有多个“正确”路径，评分和 agent 行为都不稳定。
