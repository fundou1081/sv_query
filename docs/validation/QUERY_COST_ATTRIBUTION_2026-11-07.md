# 查询成本归因（P90.1）

**日期**: 2026-11-07
**性质**: 3 个 T2 cell 的冷/热重放，不是新 agent 实验
**数据**: [query_cost_attribution_2026-11-07.json](query_cost_attribution_2026-11-07.json)
**脚本**: [tools/benchmark/query_cost_attribution.py](../../tools/benchmark/query_cost_attribution.py)

---

## 1. 方法

从 P87 的 12-task fixed 结果中取 3 个 T2 cell：

| task | 设计 | 模型 |
|---|---|---|
| axi_araddr_neighbors | AXI | MiniMax-M3 |
| serv_clk_path | SERV | DeepSeek-Flash |
| pico_adapter_mem_valid_fanout | PicoRV32 | MiniMax-M3 |

步骤：

1. 复制 agent workspace，清空 `.cache`；
2. 跑第一条命令 → cold；
3. 同一 cache 跑两遍 warm，每条命令取中位数；
4. `agent_minus_observed = agent wall - warm 命令总和`；
5. 单独测 `sv_query --help` startup。

**重要限制**：

- 命令来自 agent 最终 JSON 的 `queries`，是 self-reported，不是真实 tool telemetry；
- `agent_minus_observed` 包含模型生成、API、harness 开销；
- 负值说明 query log 与 wall 不一致，不能当精确归因；
- 这是单机 3 个样本，不是统计结论。

---

## 2. 结果

| task | agent wall | cmds | cold first | warm first | warm sum | agent-observed | outlier |
|---|---:|---:|---:|---:|---:|---:|---:|
| AXI araddr | 18.0s | 6 | **27.3s** | 0.6s | 29.5s | **-11.5s** | `connections` 26.8s |
| SERV clk path | 61.7s | 2 | 3.4s | 3.4s | 7.4s | **54.4s** | — |
| Pico mem_valid | 23.9s | 5 | 2.1s | 0.3s | 3.1s | **20.8s** | — |

CLI startup：

```text
sv_query --help: 0.27s
```

---

## 3. 解释

### SERV：模型/生成占主导

- 两条 `paths`：3.4s + 4.0s ≈ 7.4s；
- agent wall 61.7s；
- observed query 只占 **12%**；
- 剩余 **54.4s（88%）** 是模型生成/harness。

**结论**：这个 cell 做 warm service 不会解决主要成本。

### Pico：模型/生成占主导

- 4 条 direct 查询约 1.1s；
- 1 条 `trace lookup` 2.0s；
- 合计 3.1s；
- agent wall 23.9s；
- query 占 **13%**；
- 剩余 **20.8s（87%）**。

**结论**：同上。

### AXI：self-reported query log 不可信

- cold first = 27.3s；
- warm first = 0.6s；
- 第 6 条 `connections` 在 warm 下仍 **26.8s**；
- 6 条命令总和 29.5s，**大于 agent wall 18.0s**；
- 这不可能同时成立。

两种可能：

1. agent 没有真正执行最后一条，只在 JSON 里写了；
2. agent 的 cache 状态/命令与本机重放不同。

无论哪种，**不能把 `queries` 当执行 telemetry**。

如果排除最后的 `connections`：

```text
5 条查询 ≈ 2.7s
agent wall 18.0s
residual ≈ 15.3s（85%）
```

AXI 的真正问题是：

- 首次 cold build 27s；
- `connections` 命令 warm 仍 26.8s；
- 这两个是**缓存/命令族问题**，不是“缺少 daemon”。

---

## 4. 关键发现

1. **模型/生成是主要 wall 成本**  
   SERV/Pico 的 query 只占 12–13%。

2. **cold build 只影响第一查询**  
   AXI 27s，Pico 2.1s，SERV 3.4s。  
   P87 的 fact check 预先跑过命令，agent 实际吃到了 warm cache；  
   所以 benchmark 的 agent wall **低估了真实首次查询成本**。

3. **`paths` / `connections` 没有稳定 warm 收益**  
   - SERV `paths` warm 仍 3.4s/次；
   - AXI `connections` warm 仍 26.8s；
   - 这不是“CLI 启动”问题（startup 0.27s）。

4. **`queries` 不是 telemetry**  
   AXI 的 query sum 大于 wall，说明最终 JSON 可能包含未真实执行/未完成的命令。  
   之前的“query log audit”只能证明**有记录**，不能证明**执行过**。

---

## 5. 决策

按 P90 的门槛：

```text
build + reload > agent wall 30% → 做 session/batch
```

当前结果：

- SERV：12% query → **不达标**
- Pico：13% query → **不达标**
- AXI：cold/connections 很高，但 query log 不可信，不能直接算比例

所以：

> **现在不做 `serve` / `batch`。**

先做两件更基础的事：

1. **真实 tool telemetry**  
   记录命令开始/结束/rc/耗时，不依赖 agent 自报。

2. **修 `paths` / `connections` 的缓存/构图路径**  
   - AXI `connections` warm 26.8s；
   - SERV `paths` warm 3.4s/次；
   - 这比做 daemon 更直接。

做完后重新测：

```text
如果 cold + non-cacheable query 仍 >30% wall
    → 做 batch（优先）或 serve
否则
    → 停止优化，进入发布
```

---

## 6. 对“warm service”的判断

不是“warm service 没价值”，而是：

- 它解决的是 **cold build / 重复构图**；
- 当前 3 个样本里，SERV/Pico 的主要成本是模型生成；
- AXI 的重复构图问题可以用 **cache fix** 解决，未必要 daemon；
- 在没有真实 telemetry 前做 serve，会把工程投到错误瓶颈。

## 7. 边界

- 3 个 cell，单机；
- self-reported queries；
- 未测 token；
- 未测并发；
- cold/warm 是重放，不是 agent 实时观测；
- 不据此做模型排名。
