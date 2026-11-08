# OpenTitan UART real-project pilot（P118）

**日期**: 2026-11-09
**项目**: local OpenTitan `hw/ip/uart`
**HEAD**: `a82c4892e88253924b3f7af05ce7494232ab263a`
**性质**: 真实项目 onboarding + 5 个 agent 任务；不是通用 benchmark

---

## 1. Worker onboarding

Worker：

```text
opentitan-pilot
MiniMax-M3
standalone worker
```

结果：

- 选择 `hw/ip/uart` top `uart`；
- 手写 filelist：60 source files + 4 incdir；
- snapshot：**4803 nodes / 8507 edges / 0 elaboration errors / 5.1MB**；
- build：**7.57s cold / 7.80s warm**；
- snapshot query：约 **0.30s**；
- 未修改 OpenTitan tracked files。

产物：

- [worker report](opentitan_uart/WORKER_REPORT.md)
- [filelist](opentitan_uart/opentitan.f)
- [frozen tasks](opentitan_uart/opentitan_tasks.json)

## 2. Agent 任务

5 个真实 OpenTitan UART 问题 ×2 模型：

| task | MiniMax | DeepSeek |
|---|---|---|
| T1 INTR_TEST gate | ✅ 17.5s / 12 calls | ✅ 169s / 45 calls |
| T2 RX path | ✅ 44.6s / 35 calls | ✅ 38.9s / 17 calls |
| T3 RX evidence | ❌ 33s / 28 calls | ❌ 220s / 55 calls |
| T4 verify claims | ✅ 17.6s / 11 calls | ✅ 49.6s / 23 calls |
| T5 unknown/direction | ❌ 14s / 10 calls | ❌ 22s / 10 calls |

原始结果：

```text
6/10 exact
4/10 false-confident
```

但必须分开看。

## 2.1 修复后复测

初始 T3 两次失败后，修复了 edge-level evidence：

- snapshot 保存 `TraceEdge.source_location/expression/bit_slice`；
- `intent=evidence` 返回 `edge_evidence`；
- 重建 `opentitan_uart` snapshot。

T3 复测：

```text
MiniMax: uart_core.sv:307 + correct source_line ✅
DeepSeek: uart_core.sv:307 + correct source_line ✅
```

原任务期望 306（reset 分支）过窄；functional driver 是 307。  
因此 T1/T2/T4/T3 的相关任务现在是 **8/8**；T5 因题目 schema 歧义暂不计入。

详见 [EDGE_EVIDENCE_2026-11-09.md](EDGE_EVIDENCE_2026-11-09.md)。

## 3. 遇到的问题

### P1 — Snapshot evidence 给的是声明行，不是赋值行（核心问题）

T3 期望：

```text
hw/ip/uart/rtl/uart_core.sv:306
rx_val_q <= 16'h0;  (reset branch)
driver assignment at :308
```

两个模型都返回：

```text
uart_core.sv:43
```

这是 snapshot 里 `rx_val_q` 节点的声明/端口位置。  
`intent=evidence` 只按 node file/line 读取，不能给出 **driver edge 的 source_location**。

所以 T3 的 false-confident 不是模型胡乱猜，而是：

```text
工具给出的 evidence 粒度错了
→ agent 高置信复制了错误行
```

这是当前“可验证事实层”最核心的缺口：

```text
node declaration evidence
≠
edge assignment evidence
```

需要二选一：

1. snapshot 序列化 `TraceEdge.source_location/expression`；
2. tool 的 evidence 对 `--from-snapshot` 不可用时明确返回 `unsupported`，不要返回声明行冒充赋值行。

### P2 — OpenTitan 依赖闭包不能直接来自 `.core`

Worker 记录：

- `lowrisc:prim:all` 会拉入 `lc_ctrl_pkg`、tech-specific `prim_buf/prim_flop`；
- `prim_generic` 需要手选；
- `+incdir+` 必需；
- `top_pkg/top_racl_pkg` 在 `hw/top_earlgrey`，不在 block 内；
- `filelist prune` 仍保留 include-only `.svh`，需手工删。

结果：**4 轮手工依赖整理**才得到可 elaborate 的 60 文件 filelist。

### P3 — 真实任务成本高

DeepSeek T1：**169s / 45 calls**。  
T3：**220s / 55 calls**。

工具单次 query 约 0.30s，但 agent 需要大量搜索/邻居扩展；真实 OpenTitan 任务不是 5–10s cell。

### P4 — T5 题目本身有歧义

T5 让模型返回“missing signal / no path”的状态；模型分别返回了 ID、boolean、`contradicted/unknown` 混合形式。  
这是 **benchmark schema 设计问题**，不能当成纯模型错误。  
T5 需要固定 answer schema，或直接给 verify claim JSON。

### P5 — `paths` 的 canonical 歧义

Worker 记录同一对 RX 信号：

- 默认 `paths --directed`：9 hops；
- `--canonical`：18 hops；
- `--all`：48 条路径（10–19 hops）。

T2 两个模型都给出了 18-hop 路径，但工具/任务必须明确 canonical 规则，否则同一问题会有多个“正确”答案。

## 4. 结论

```text
OpenTitan UART 可以被 sv_query 建图；
真实 block 的 query/verify 基本可用；
但 evidence 粒度是当前核心阻塞。
```

不要把 6/10 简单归因于模型：

- T1/T2/T4：6/6 成功；
- T3：已修复（edge evidence；CLI `trace evidence --from-snapshot` 也返回 edge location）；原 run 的 T3 是修复前结果；
- T5：题目 schema 歧义，未计入准确率。

核心下一步：

```text
edge-level evidence 已修复；
处理 T5 schema 歧义；
再做一次新的 OpenTitan 任务集，确认不是单例修复。
```

## 5. 边界

- 只测 UART 一个 block；
- 依赖闭包手工整理；
- 没有仿真/波形；
- 不是 fault localization；
- 5 个任务，2 模型；
- OpenTitan HEAD 固定，未测版本漂移。
