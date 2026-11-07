# 最终验证摘要

**日期**: 2026-11-07
**状态**: 收尾（P89）
**原则**: 分开报告 task family；不把 direct-query 结果当 debug 能力。

---

## 1. 一句话结论

```text
T2 是一个可靠的 canonical structural query 执行层；
但还没有被证明是通用 RTL debugger。
```

支持这个结论的证据是：

- 12 个 direct structural tasks：T2 48/48，source 32/48；
- 邻域任务：source/T2 语义 11/12 vs 11/12；
- multi-turn T2：17/18；
- 双评分：canonical + semantic 分开。

---

## 2. 已验证

### A. 12 题固定协议（最强证据）

**范围**：12 题 ×2 模型 ×2 臂 ×2 seed = **96 cells**  
**隔离**：source/T2 hard sandbox；source 无 CLI/repo；T2 无 truth/task JSON。  
**协议**：fact check、`--depth 1`、query log。

| 模型 / 臂 | exact | high-conf 错 |
|---|---:|---:|
| MiniMax-M3 / source | 17/24 | 7/24 |
| MiniMax-M3 / T2 | **24/24** | 0/24 |
| DeepSeek-Flash / source | 15/24 | 2/24 |
| DeepSeek-Flash / T2 | **24/24** | 0/24 |

合计：

```text
source: 32/48
T2:     48/48
```

全部 96 cells：

```text
rc=0 / parsed / fact_check_ok
T2 query+depth audit 48/48
```

报告：[LONG_RANGE_12_FIXED_2026-11-07.md](LONG_RANGE_12_FIXED_2026-11-07.md)

### B. 邻域语义

**范围**：complex constraints / nested mux；3 模型 ×2 臂 ×2 seed = **24 cells**。

```text
canonical: source 0/12, T2 4/12
semantic:  source 11/12, T2 11/12
```

- mux semantic 12/12；
- constraints semantic 11/12，双方各漏一个 `payload`；
- T2 的优势是 canonical ID，不是关系理解；
- T2 更慢，且没有 token/cost 证据。

报告：[NEIGHBORHOOD_SOURCE_T2_2026-11-07.md](NEIGHBORHOOD_SOURCE_T2_2026-11-07.md)

### C. Multi-turn T2

**范围**：3 场景 ×3 模型 ×2 seed = **18 cells**。

```text
17/18 完整正确
1/18 部分正确
```

唯一 partial：

```text
MiniMax-M3 constraints seed1
把 covergroup cg 当成共同 block
```

报告：[INTERACTIVE_P1_2026-11-06.md](INTERACTIVE_P1_2026-11-06.md)

### D. 邻域场景 smoke

**范围**：2 场景 ×3 模型 ×1 seed = **6 cells，T2 only**。

```text
6/6 exact
```

报告：[INTERACTIVE_NEIGHBORHOOD_2026-11-07.md](INTERACTIVE_NEIGHBORHOOD_2026-11-07.md)

### E. 双评分

- canonical：精确 ID/path/count；
- semantic：只对 neighborhood；
- direct 结构查询 `semantic=None`；
- 旧 P85 strict 6/12 已修正为 canonical 4/12。

报告：[DUAL_SCORING_2026-11-07.md](DUAL_SCORING_2026-11-07.md)

### G. 成本归因

3 个 T2 cell 的 cold/warm 重放：

- SERV：query 7.4s / wall 61.7s（12%），模型 residual 54.4s；
- Pico：query 3.1s / wall 23.9s（13%），residual 20.8s；
- AXI：cold 27.3s；`connections` warm 26.8s；self-reported query sum > wall。

结论：**模型生成主导**；暂停 serve/batch，先修 cache/telemetry。

报告：[QUERY_COST_ATTRIBUTION_2026-11-07.md](QUERY_COST_ATTRIBUTION_2026-11-07.md)

### F. 回归

```text
2556 passed / 0 failed
7 skipped / 119 deselected
```

---

## 3. 未验证

以下全部**没有证据**：

1. **外部 benchmark**  
   VeriBug 未执行（P88 放弃）；没有真实项目故障集。
2. **通用 RTL debug**  
   只测了 direct query、邻域提取和少量 multi-turn。
3. **真实 bug 修复**  
   没有 fault localization / patch / 仿真 oracle。
4. **成本优势**  
   没有 token/价格；cold/warm 未拆分。
5. **模型排名**  
   模型样本和任务都有限。
6. **3rd seed**  
   12 题只有 2 seed。
7. **source/T2 的 multi-turn 对照**  
   P1 是 T2 only。

---

## 4. 可以写 / 不可以写

### 可以写

```text
在 12 个 direct structural tasks 上，固定协议后 T2 48/48，
source 32/48；T2 无 high-confidence 错误。
```

```text
邻域关系语义 source/T2 都是 11/12；T2 主要改善 canonical ID。
```

```text
T2 multi-turn 稳定性 17/18。
```

### 不可以写

```text
T2 比 source 更会 debug
T2 在真实项目上更准
T2 成本更低
T2 可以替代 VCS/波形调试
模型排名
```

---

## 5. 产品判断

当前最准确的定位：

```text
agent-facing RTL query + verification layer
```

不是：

```text
autonomous RTL debugger
```

T2 的价值已经被证明在：

- canonical ID；
- 直接 fanin/fanout；
- 图邻域；
- 可审计 query/evidence。

还没被证明在：

- root cause；
- patch；
- 真实故障；
- 成本。

---

## 6. 下一步（如果重启）

不再扩内部 direct 题。  
如果要做外部验证，只做最小路径：

```text
1 个项目：first_counter_overflow
Icarus reference/mutant/compare
5 个 mutant
source/T2 ×1 seed = 20 agents
```

且只声称 **Icarus-compatible subset**。

否则保持冻结。

成本归因（P90）显示 query 只占 12–13%，所以 warm service 不是当前第一优先。

---

## 7. 资产索引

- [实验资产盘点](EXPERIMENT_INVENTORY_2026-11-06.md)
- [12 题固定协议](LONG_RANGE_12_FIXED_2026-11-07.md)
- [邻域 source/T2](NEIGHBORHOOD_SOURCE_T2_2026-11-07.md)
- [双评分](DUAL_SCORING_2026-11-07.md)
- [Interactive P1](INTERACTIVE_P1_2026-11-06.md)
- [PLAN](../../PLAN.md)
