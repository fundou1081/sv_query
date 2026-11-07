# 实验资产盘点：多轮 / 深跳 / 邻域 / 对照

**日期**: 2026-11-06（2026-11-07 更新）
**用途**: 找到实验代码、数据、评分与边界，供最终验证摘要引用。

---

## 1. 真正的多轮交互实验

**P74 / P78 / P79 / P84**

| 资产 | 路径 | 状态 |
|---|---|---|
| 场景 | `tools/benchmark/interactive_debug/scenarios.json` | 5 个：deep drive / rand constraints / coverage / complex constraints / nested mux |
| fixture | `examples/interactive_debug/` | deep_chain.sv / rand_coverage.sv / complex_constraints.sv / mux_neighborhood.sv |
| runner | `tools/benchmark/interactive_debug/run_seed.py` | 3 模型 × 任意场景 × seed |
| 模型配置 | `tools/benchmark/interactive_debug/patches/` | M3 / M3.1 / DeepSeek |
| 结果 | `INTERACTIVE_P0/P1/DEBUG` | 3 场景 ×3 模型 ×2 seed：**17/18** |
| 邻域结果 | `INTERACTIVE_NEIGHBORHOOD_2026-11-07.md` | 2 场景 ×3 模型 ×1 seed：**6/6**（T2 only） |
| 评分 | runner 内置 field checks | 尚未统一到 semantic/canonical scorer |

这是目前**唯一可复现的 multi-turn runner**。  
注意：P1 的 seed1/seed2 prompt 不完全逐字相同，按语义正确性统计。

---

## 2. 长程结构查询 12 题（P69 / P87）

| 资产 | 路径 | 说明 |
|---|---|---|
| 任务 | `tools/benchmark/long_range_tasks.json` | 12 题：AXI/SERV/Pico |
| runner | `tools/benchmark/run_long_range.py` | hard isolation、source/T2、fact check、query log |
| 评分 | `tools/benchmark/score_long_range.py` | canonical；direct semantic=n/a |
| 复验 | `tools/benchmark/verify_long_range.py` | 结果覆盖 + ground truth |
| 固定协议结果 | `docs/validation/long_range_12_fixed_2026-11-07.json` | **96 cells**（12×2 模型×2 臂×2 seed） |
| 报告 | `LONG_RANGE_12_FIXED_2026-11-07.md` | T2 48/48；source 32/48 |

**注意**：这 12 题不是多轮深跳。  
`long_range_tasks.json` 的 `query` 字段是：

```text
fanin --depth 1
fanout --depth 1
shortest path
```

T2 基本一条命令就能答；source 需要人肉找 canonical ID。  
它测的是“直接查询执行”，不是“连续追问”。

固定协议后：

- 全部 96 cells rc=0 / parsed / fact_check_ok；
- T2 query/depth audit 48/48；
- source high-confidence 错 9/48；
- T2 high-confidence 错 0/48。

历史 4-task pilot：

- `LONG_RANGE_4TASK_2026-11-07.md`（协议修复前）；
- `LONG_RANGE_4TASK_FIXED_2026-11-07.md`（协议修复后，T2 16/16 vs source 11/16）。

---

## 3. 硬隔离（P69.7）

| 资产 | 路径 |
|---|---|
| source profile | `tools/benchmark/hard_isolated/source.sb` |
| T2 profile | `tools/benchmark/hard_isolated/t2_long.sb` |
| 说明 | `tools/benchmark/hard_isolated/README.md` |
| 审计 | `docs/validation/HARD_ISOLATION_2026-11-05.md` |
| 实际矩阵 | P87：12 题 ×2 模型 ×2 臂 ×2 seed = **96 cells** |

source 被拒绝 repo / `sv_query` / pilot artifact；  
T2 被拒绝 task JSON / ground truth / benchmark docs。  
硬隔离已从单题 PoC 走到 96-cell 矩阵。

---

## 4. 邻域场景（P84 / P85）

| 资产 | 路径 | 说明 |
|---|---|---|
| 场景 | `tools/benchmark/interactive_debug/scenarios.json` | complex_constraints / mux_neighborhood |
| runner | `tools/benchmark/run_neighborhood.py` | hard isolation + source/T2 + fact check |
| 评分 | `tools/benchmark/scoring.py` | canonical + semantic |
| 结果 | `neighborhood_source_t2_2026-11-07.json` | 2 场景 ×3 模型 ×2 臂 ×2 seed = **24 cells** |
| 报告 | `NEIGHBORHOOD_SOURCE_T2_2026-11-07.md` | canonical 0 vs4/12；semantic 11 vs11/12 |

结论：邻域语义 source/T2 都能做；T2 只有 canonical ID 优势。

---

## 5. 统一双评分（P86）

| 资产 | 路径 |
|---|---|
| scorer | `tools/benchmark/scoring.py` |
| 测试 | `sim/tests/unit/test_dual_scoring.py` |
| 文档 | `docs/validation/DUAL_SCORING_2026-11-07.md` |

- canonical：精确 ID/path/count；
- semantic：只对 neighborhood 任务；
- direct 结构查询 `semantic=None`，不伪造；
- P85 旧 strict 6/12 已修正为 canonical 4/12。

---

## 6. 反幻觉 CDC walkthrough（P67）

`examples/anti_hallucination_cdc/`

这是人工多步查询示范：

```text
profile -> fanin -> fanout -> 反驳“两级同步器”
```

不是 agent benchmark，没有多模型 runner；可作为“多轮证据链”的参考样例。

---

## 7. 外部 benchmark：明确 deferred/放弃（P88）

**VeriBug / VeriBugBench 没有执行。**

原因：

- 官方参考后端是 Synopsys VCS + Verdi PLI，本环境没有；
- Icarus 只是有限兼容子集，不能代表 2608 instances；
- 做 adapter 需要 mutation ID 隐藏、patch 评分、仿真验证，成本高；
- 对当前产品判断的增量不足以抵消成本。

因此：

```text
不写外部 benchmark 结果
不写“真实项目 debug 有效”
不把内部 12 题当成 VeriBug
```

如果以后重启，最小路径是：
`first_counter_overflow` → Icarus reference/mutant/compare → 5 instances →
source/T2 ×1 seed；仍只代表 Icarus 子集。

---

## 8. 其他相关但不是 agent 实验

- `tools/benchmark/query_perf.py`：构图/查询性能；
- `tools/benchmark/run_benchmark.py`：构建质量/回归；
- `sim/tests/.../test_*deep_chain*`：结构单测，不是 agent 行为实验。

---

## 9. 当前资产缺口

1. **外部效度**：没有 VeriBug/真实项目故障集；
2. **3rd seed**：12 题只有 2 seed；
3. **成本**：token/cold-warm 未拆分；
4. **direct semantic**：direct 结构题没有独立 semantic 表示；
5. **interactive 评分**：仍是 runner field checks，未接入统一 scorer；
6. **任务族不能合成一个 accuracy**：interactive / long-range / neighborhood 必须分开报告。

---

## 10. 结论

```text
可复现 multi-turn runner: interactive_debug/run_seed.py
可复现 12 题固定协议: run_long_range.py
可复现邻域对照: run_neighborhood.py
统一双评分: scoring.py
外部 benchmark: 未执行（P88 放弃）
```

当前应**冻结实验扩张**，以
[FINAL_VALIDATION_SUMMARY_2026-11-07.md](FINAL_VALIDATION_SUMMARY_2026-11-07.md)
为准；不再用 direct-query 结果证明 debug 能力。
