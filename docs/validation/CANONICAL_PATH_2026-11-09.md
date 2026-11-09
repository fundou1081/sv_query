# Canonical path + continuous rerun（P122）

**日期**: 2026-11-09
**触发**: MiniMax 在 OpenTitan T2 选择 13-hop，而不是 18-hop canonical path，且 high confidence。
**状态**: 完成；连续复跑 10/10

---

## 1. 修复

### path 语义

之前：

```text
intent=path       paths --all，默认最短
intent=deep_path  paths --all，选最长
granular          可被模型主动设置
```

现在：

```text
intent=path       paths --canonical --directed
intent=deep_path  兼容 alias，同样 canonical
输出 path_kind=canonical
输出 candidate_count / canonical_policy
```

核心 CLI 已支持 `--canonical`：

```text
max_nodes_then_lexicographic
```

### runner

`run_opentitan_tasks.py`：

- per-cell timeout 从 300s 提到 600s（DeepSeek T1 需要 355s）；
- 捕获 `TimeoutExpired`，记录 `timeout=true`，不再让整个 run 崩溃；
- 单 cell 异常不会丢全部结果；
- 仍是一次连续 run。

## 2. OpenTitan 连续复跑

命令：

```bash
python3 tools/benchmark/run_opentitan_tasks.py \
  --models MiniMax-M3 DeepSeek-Flash --timeout 600 \
  --output /tmp/opentitan_canonical_continuous.json
```

结果：

| task | MiniMax | DeepSeek |
|---|---|---|
| T1 INTR_TEST gate | ✅ 104.1s / 85 calls | ✅ 355.6s / 64 calls |
| T2 RX path | ✅ 19.7s / 15 calls | ✅ 11.0s / 4 calls |
| T3 RX evidence | ✅ 15.9s / 9 calls | ✅ 9.4s / 2 calls |
| T4 verify claims | ✅ 55.4s / 27 calls | ✅ 25.5s / 10 calls |
| T5 unknown/direction | ✅ 19.0s / 2 calls | ✅ 5.6s / 2 calls |

合计：

```text
10/10 exact
0 false-confident
0 false-found
0 timeout
220 tool calls
```

T2 从原来的 46.5s / 145.2s 降到 19.7s / 11.0s，因为不再枚举 20 条路径。

## 3. 过程中出现的 runner 问题

第一次 canonical 复跑 crashed：

```text
subprocess.TimeoutExpired: DeepSeek T1 > 300s
```

并且：

- 整个 run abort；
- 已完成 cell 丢失；
- output JSON 未写。

已修：

```text
per-cell timeout 600
per-cell exception isolation
partial rows preserved
```

这是 runner 问题，不是 canonical path 问题。

## 4. 结论

```text
canonical path 修复成立；
连续 OpenTitan 5 task ×2 模型 = 10/10；
false-confident / false-found = 0；
真实项目上 query/evidence/verify 闭环通过。
```

## 5. 边界

- 只测 OpenTitan UART；
- 仍非外部 fault set；
- DeepSeek T1 355s，接近成本上限；
- T5 schema 已经显式固定；
- 不是 fault localization / patch。
