# 查询成本归因（P90）

**日期**: 2026-11-07
**性质**: 3 个 T2 cell 的冷/热重放 + DSH 真实 session telemetry
**数据**:
- [session_telemetry_2026-11-07.json](session_telemetry_2026-11-07.json)
- [query_cost_attribution_2026-11-07.json](query_cost_attribution_2026-11-07.json)
**脚本**:
- [session_telemetry.py](../../tools/benchmark/session_telemetry.py)
- [query_cost_attribution.py](../../tools/benchmark/query_cost_attribution.py)

---

## 1. 方法

### A. 真实 telemetry

从 DSH `session.v4.jsonl.zstd` 读取：

- `tool/call` / `job/settled` → 实际命令与耗时；
- `assistant/message.usage` → token；
- `turn/start` / `turn/end` → wall。

### B. 冷/热重放

从 P87 结果取 3 个 T2 cell，复制 workspace、清空 `.cache`：

1. 第一条命令 → cold；
2. 同一 cache 跑两遍 warm，取每条命令中位数。

**限制**：

- 重放使用最终 JSON 的 `queries`，已被证明是 lossy self-report；
- 重放只用于“命令族成本”参考，不作为 agent 实际耗时；
- cold/warm 是重放，不是实时观测。

---

## 2. 真实结果

| task | wall | tool | model residual | sv_query calls | total tokens |
|---|---:|---:|---:|---:|---:|
| AXI araddr | 16.1s | 3.8s | **12.3s** | 6 | 61,935 |
| SERV clk path | 60.2s | 11.2s | **49.0s** | 5 | 84,224 |
| Pico mem_valid | 22.9s | 6.4s | **16.5s** | 8 | 111,971 |

比例：

```text
AXI:  tool 24% / model 76%
SERV: tool 19% / model 81%
Pico: tool 28% / model 72%
```

**模型生成是主要 wall 成本。**

---

## 3. 冷/热参考

| task | cold first | warm first | warm sum | command family notes |
|---|---:|---:|---:|---|
| AXI | **27.3s** | 0.6s | 29.5s | `connections` 完整重放 26.8s |
| SERV | 3.4s | 3.4s | 7.4s | `paths` 每次约 3.4s |
| Pico | 2.1s | 0.3s | 3.1s | 单次 `lookup` 约 2.0s |

注意：

- P87 的 fact check 在 agent 之前构建过图，AXI agent 实际吃到了 warm cache；
- 真实首次查询会多付 cold build；
- AXI `connections` 重放 26.8s，但 agent 真实命令是 `sv_query connections ... | head -60`，0.729s 就被截断；最终 JSON 把它简写成完整命令；
- 所以 **cold/warm 表不能直接加到 agent wall**。

---

## 4. 关键修正：`queries` 不是 telemetry

### 自报 vs 实际

| task | 自报 | 实际 sv_query |
|---|---:|---:|
| SERV clk path | 2 | 5 |
| Pico mem_valid | 5 | 8 |
| AXI araddr | 6 | 6 |

96 cells 审计：

```text
T2: 48/48 有实际 sv_query；389 次实际调用
T2 direct fanin/fanout: 44/44 实际使用 --depth 1
source: 47/48 无 sv_query；1 次尝试被拒/失败
```

因此：

- `queries` 可以用于说明“尝试过什么”；
- 不能用于精确成本、执行证明或协议审计；
- 协议审计应读 DSH session telemetry。

详见 [SESSION_TELEMETRY_2026-11-07.md](SESSION_TELEMETRY_2026-11-07.md)。

---

## 5. 决策

按 P90 门槛：

```text
cold + non-cacheable query > agent wall 30% → session/batch
```

真实 telemetry 显示：

- tool 占 19–28%；
- model residual 占 72–81%；
- cold build 在 benchmark 中被 fact check 预热，真实首次查询另算。

所以：

> **现在不做 serve / batch。**

先做：

1. **把 session telemetry 纳入 runner**
   - 记录实际命令、耗时、token；
   - 不再把最终 `queries` 当执行日志。

2. **修 `paths` / `connections` 的重复构图**
   - `paths` 每次约 3.4s；
   - `connections` 完整构图约 26.8s；
   - 这是 cache/build 问题，不是 daemon 问题。

3. **真实首查询单独计**
   - cold build 不预热；
   - 记录 first-query 与后续 query。

之后如果 tool 占比仍 >30%，再考虑 batch（优先）或 serve。

---

## 6. 对 warm service 的判断

不是“warm service 没价值”，而是：

- 当前 3 个样本里，模型生成占 72–81%；
- serve/batch 只能优化 tool 部分；
- 先修 cache 和 telemetry，收益更确定；
- 没有完整 48-cell telemetry 前，不做架构性投入。

## 7. 边界

- 3 个 cell 的实时 telemetry；96-cell 只做 sv_query 计数审计；
- 每个 workspace 有历史 session，取最新且 wall 接近结果；
- token 包含 cache read，不是账单；
- cold/warm 为重放；
- 不据此做模型排名。
