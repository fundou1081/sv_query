# Neighborhood：source vs T2 硬隔离对照

**日期**: 2026-11-07
**状态**: P85 完成
**数据**: [neighborhood_source_t2_2026-11-07.json](neighborhood_source_t2_2026-11-07.json)

---

## 1. 协议

- 场景：complex_constraints / mux_neighborhood；
- 模型：MiniMax-M3 / MiniMax-M3.1-Flash / DeepSeek-Flash；
- 臂：source / T2；
- 2 seed；
- 2 × 3 × 2 × 2 = **24 agents**；
- source/T2 hard sandbox；
- source 无 `sv_query`、无 repo；
- T2 不能读 task JSON/truth；
- 跑前 fact check；
- 所有 cell rc=0、parsed、fact_check_ok。

> 原计划 2 模型；实际加了 M3.1，作为额外样本。

---

## 2. 两种评分

任务要求 canonical IDs，但 source 只能用源码层级名。  
所以分开报告：

- **strict canonical**：ID 完全一致；
- **semantic**：允许 instance alias / mux signal alias，只检查关系内容。

### strict canonical

| 模型 / 臂 | strict |
|---|---:|
| MiniMax-M3 / source | 0/4 |
| MiniMax-M3 / T2 | 1/4 |
| MiniMax-M3.1-Flash / source | 0/4 |
| MiniMax-M3.1-Flash / T2 | 0/4 |
| DeepSeek-Flash / source | 0/4 |
| DeepSeek-Flash / T2 | 3/4 |

合计：

```text
source: 0/12
T2:     4/12
```

### semantic

| 模型 / 臂 | semantic |
|---|---:|
| MiniMax-M3 / source | 3/4 |
| MiniMax-M3 / T2 | 4/4 |
| MiniMax-M3.1-Flash / source | 4/4 |
| MiniMax-M3.1-Flash / T2 | 4/4 |
| DeepSeek-Flash / source | 4/4 |
| DeepSeek-Flash / T2 | 3/4 |

合计：

```text
source: 11/12
T2:     11/12
```

**语义上，T2 没有优势。**

---

## 3. 关键失败

### source semantic 唯一失败

MiniMax-M3 seed2 complex_constraints：

- 找到 `c_len/c_order/c_mode`；
- 但 rand_vars 漏了 `payload`。

### T2 semantic 唯一失败

DeepSeek seed1 complex_constraints：

- 找到 3 个 len 相关约束；
- rand_vars 漏了 `payload`；
- `c_addr` 被列入额外约束，但只约束 addr，语义上无害。

两边都漏同一个变量，说明是 agent 的完整性检查问题，不是工具独有。

### strict 差异的来源

source 用：

```text
top.u.lo / top.sel[0] / top.a
```

T2 用：

```text
top.u.lo.ternary_sel[0] / top.u.sel[0] / top.u.a
```

两者语义等价，但 strict canonical 只认后者。  
所以 strict 0/12 不能解释为 source “不会分析”。

---

## 4. 其他观察

- mux semantic：source/T2 都 12/12；复杂 mux 关系本身可提取。
- constraints semantic：11/12；唯一失败是漏 payload。
- T2 12/12 都报告了 `queries`；这次没有空 query log。
- mean wall：

| 模型 / 臂 | mean |
|---|---:|
| MiniMax-M3 / source | 14.0s |
| MiniMax-M3 / T2 | 32.2s |
| M3.1 / source | 53.4s |
| M3.1 / T2 | 70.1s |
| DeepSeek / source | 32.1s |
| DeepSeek / T2 | 41.4s |

T2 更慢；没有 token 统计。

---

## 5. 结论

1. **复杂 constraint / mux 的关系语义，source 和 T2 都能拿到。**
2. T2 的优势主要是 **canonical/synthetic ID**，不是理解能力。
3. 但 T2 的 strict canonical 只有 4/12，说明额外字段/alias 仍会让严格匹配失败。
4. 之前“T2 应该更好”的假设在邻域任务上没有成立。
5. 不能据此做 neighborhood CLI；没有证据表明它能提升语义准确率。

## 6. 下一步建议

不要做 `trace neighborhood` 来提升准确率。  
先做：

1. **评价口径统一**：strict + semantic 双评分进入正式报告；
2. **prompt 明确 canonical 类型**：
   - 是否要求 OP_TERNARY ID；
   - 是否接受 instance alias；
3. 如果目标是产品化 neighborhood：
   - 只做“compact view”，不宣称准确率；
   - 先测 token/time 是否降低；
4. 然后回到外部 benchmark。

## 7. 边界

- 2 个 fixture，不是真实项目；
- 3 模型（原计划 2）；
- 2 seed；
- semantic checker 是规则近似，不是人工逐项审计；
- 不宣称模型排名。
