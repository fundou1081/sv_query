# 模型对比：A+D 方案 vs 原版（P94）

**日期**: 2026-11-07
**范围**: 12 题 fixed protocol，seed1，T2 新方案；source/T2 原版来自 P87
**数据**:
- [A+D T2 seed1](long_12_ad_s1_2026-11-07.json)
- [原版 96 cells](long_range_12_fixed_2026-11-07.json)

---

## 1. A+D 方案

- AXI/SERV：`filelist prune --top` → snapshot save；
- Pico：单文件 snapshot；
- T2 agent 用 `--from-snapshot <tag>` 查询；
- 不再每次 build；
- source 臂不变，仍用 P87 原版数据。

快照 prep：

| 设计 | files | nodes | save |
|---|---:|---:|---:|
| AXI | 3 | 351 | 1.1s |
| SERV | 17 | 1,347 | 1.5s |
| Pico | 1 | 1,842 | 2.1s |

---

## 2. 准确率

### T2

| 模型 | 原版 T2 | A+D T2 |
|---|---:|---:|
| MiniMax-M3 | **12/12** | **12/12** |
| DeepSeek-Flash | **12/12** | **12/12** |

A+D **没有提升准确率**；两者都是满分。

### source 基线

原版 seed1：

| 模型 | source |
|---|---:|
| MiniMax-M3 | 8/12 |
| DeepSeek-Flash | 8/12 |

source 仍是 32/48（两 seed）。

---

## 3. 延迟

| 模型 | 原版 T2 mean | A+D T2 mean |
|---|---:|---:|
| MiniMax-M3 | 68.6s | **239.4s** |
| DeepSeek-Flash | 32.5s | **74.4s** |

A+D **更慢**，尽管快照加载只需约 0.5s。

原因不是 snapshot：

- MiniMax 多次通过 repo 的 `run_cli.py`、重复探索；
- DeepSeek 有一次直接读 snapshot JSON；
- agent 仍在做证据核对，模型/API 时间占主导；
- 单 seed，模型延迟方差大。

**不能声称 A+D 降低了总延迟。**

---

## 4. 查询数

| 模型 | 原版 T2 queries | A+D queries |
|---|---:|---:|
| MiniMax-M3 | 70 | 74 |
| DeepSeek-Flash | 29 | 20 |

查询数相近，说明不是简单“少查了”；  
但 A+D 的 query 里有部分不是 CLI，而是：

- 读 `snapshot.json`；
- 通过 repo `run_cli.py`；
- 不完全符合“只用 `--from-snapshot`”的协议。

所以 exact 仍有效，**query 证据不干净**。

---

## 5. 结论

```text
A+D：准确率不变（仍 24/24）
A+D：延迟没有改善，反而更慢（seed1）
A+D：agent 会绕过 snapshot CLI 直接读 JSON/repo
```

因此：

1. 不能把 A/D 当作“模型能力提升”；
2. 不能把 A/D 当作“成本优化”；
3. D 的 snapshot 对机器友好，但当前 agent prompt 没把它变成更短路径；
4. 需要先修 agent 使用协议，或在 runner 里禁止 repo/JSON 读取，才能公平比较延迟。

---

## 6. 边界

- 1 seed；原版有 2 seed；
- A/D 只跑 T2；source 复用原版；
- A/D 的 snapshot 预构建时间未计入 agent wall；
- 部分 query 不是实际 CLI；
- 不作模型排名。

## 7. 下一步

不要把 A/D 设为默认。先做：

1. T2 硬隔离禁止 repo / snapshot 文件直读；
2. prompt 固定“只允许 `--from-snapshot` CLI”；
3. 重跑 seed1，确认延迟是否仍慢；
4. 若仍慢，A/D 只保留为显式工具，不进入默认工作流。
