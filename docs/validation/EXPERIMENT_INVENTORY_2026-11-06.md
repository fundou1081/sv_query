# 实验资产盘点：多轮 / 深跳 / 对照

**日期**: 2026-11-06
**用途**: 找到之前做过的实验代码与数据，供后续统一运行评价。

---

## 1. 真正的多轮交互实验（当前主线）

**P74 / P78 / P79**

| 资产 | 路径 | 状态 |
|---|---|---|
| 场景 | `tools/benchmark/interactive_debug/scenarios.json` | 3 个：deep drive / rand constraints / coverage |
| fixture | `examples/interactive_debug/` | deep_chain.sv / rand_coverage.sv |
| runner | `tools/benchmark/interactive_debug/run_seed.py` | 可跑 3 模型 × 3 场景 × seed |
| 模型配置 | `tools/benchmark/interactive_debug/patches/` | M3 / M3.1 / DeepSeek |
| 结果 | `docs/validation/INTERACTIVE_P0/P1/DEBUG` | 2 seed 数据 |
| 评分 | runner 内置 field checks | 非统一 semantic/canonical 双评分 |

这是目前**唯一可复现的 multi-turn runner**。

---

## 2. 长程结构查询 12 题（P69）

| 资产 | 路径 | 说明 |
|---|---|---|
| 任务 | `tools/benchmark/long_range_tasks.json` | 12 题：AXI/SERV/Pico |
| 评分 | `tools/benchmark/score_long_range.py` | exact-only |
| 复验 | `tools/benchmark/verify_long_range.py` | 结果覆盖 + ground truth |
| 结果 | `docs/validation/long_range_12_2026-11-05.json` | 48 cells |
| 报告 | `LONG_RANGE_12` / `LONG_RANGE_SEED2` / `COMPARISON_RECORD` | source vs T2 |

**注意**：这 12 题不是多轮深跳。  
`long_range_tasks.json` 的 `query` 字段是：

```text
fanin --depth 1
fanout --depth 1
shortest path
```

T2 基本一条命令就能答；source 需要人肉找 canonical ID。  
它测的是“直接查询执行”，不是“连续追问”。

**runner 已补 (P81)**：`tools/benchmark/run_long_range.py` 支持 hard sandbox、
本地 filelist、source/T2 同 prompt；单题 smoke 已通过；4-task pilot 结果见 LONG_RANGE_4TASK_2026-11-07。

---

## 3. 4-task pilot（P69.2）

| 资产 | 路径 |
|---|---|
| 结果 | `docs/validation/long_range_pilot_2026-11-05.json` |
| 报告 | `docs/validation/LONG_RANGE_PILOT_2026-11-05.md` |
| 评分 | 复用 `score_long_range.py` |

同样没有独立 runner；prompt 是当时 inline 构造的。

---

## 4. 硬隔离 PoC（P69.7）

| 资产 | 路径 |
|---|---|
| source profile | `tools/benchmark/hard_isolated/source.sb` |
| T2 profile | `tools/benchmark/hard_isolated/t2.sb` |
| 说明 | `tools/benchmark/hard_isolated/README.md` |
| 审计 | `docs/validation/HARD_ISOLATION_2026-11-05.md` |

只有**单题 4 cells**，不是 12×3 矩阵。

---

## 5. 反幻觉 CDC walkthrough（P67）

`examples/anti_hallucination_cdc/`

这是人工多步查询示范：

```text
profile -> fanin -> fanout -> 反驳“两级同步器”
```

不是 agent benchmark，没有多模型 runner；可作为“多轮证据链”的参考样例。

---

## 6. 其他相关但不是 agent 实验

- `tools/benchmark/query_perf.py`：构图/查询性能；
- `tools/benchmark/run_benchmark.py`：构建质量/回归；
- `sim/tests/.../test_*deep_chain*`：结构单测，不是 agent 行为实验。

---

## 7. 资产缺口

1. **没有统一 runner** 能同时跑 interactive 3 题和 long-range 12 题；
2. long-range 12 题没有 multi-turn 协议；
3. source/T2 结果受污染（`/tmp` artifact、repo/CLI 不对称）；
4. T2 允许 repo，存在读 task JSON 的权限风险；
5. 评分不统一：interactive 是 field checks，long-range 是 exact-only；
6. long-range 的 source/T2 prompt 没有入库；
7. 没有 hard isolation 下的多题矩阵。

---

## 8. 建议的统一运行方式

保持两个 task family **分开报告**，不要合成一个 accuracy：

```text
Family A: interactive 3
  - 多轮
  - deep mux / class constraints / coverage mapping
  - 用 run_seed.py

Family B: long-range 12
  - 直接结构查询
  - 不是多轮
  - 需要补 runner + hard isolation + dual scoring
```

统一要求：

- source / T2 同预算（tool calls / wall / token）；
- 两边 hard sandbox；
- T2 不允许读 task JSON/ground truth；
- 双评分：`semantic_exact` + `canonical_exact`；
- 2–3 seed；
- 记录空输出/429/超时，单独分类；
- 不把 direct-query 结果当 debug reasoning。

---

## 9. 结论

```text
真正的 multi-turn code: interactive_debug/run_seed.py
深跳任务集: long_range_tasks.json（但不是多轮）
历史 48-agent: 只有任务/结果/评分，没有 runner
```

下一步如果“一起运行”：

1. 先复用 `run_seed.py` 跑 Family A；
2. 为 Family B 补 `run_long_range.py`，套同一结果 schema；
3. 先做 4 个代表任务 × 2 臂 × 2 seed 的 hard-isolated pilot；
4. 再决定 12×3。
