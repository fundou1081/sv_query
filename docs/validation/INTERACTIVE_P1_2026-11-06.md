# Interactive P1：3 场景 × 3 模型 × 2 seed

**日期**: 2026-11-06
**状态**: P79 完成
**臂**: T2 only
**范围**: interactive-debug 稳定性，不是真实 bug benchmark

---

## 1. 设置

- 场景：deep_drive_chain / rand_constraints / rand_coverage_mapping；
- 模型：MiniMax-M3 / MiniMax-M3.1-Flash / DeepSeek-Flash；
- seed1：复用 P0（deep）与 P74（constraints/coverage）；
- seed2：新跑 9 个 agent，隔离 workspace，无 ground truth；
- seed2 prompt：
  - 至少 4 轮 query；
  - 明确答案字段；
  - 不读 scenario/ground truth。

seed1 与 seed2 的 prompt 不是逐字相同：seed1 的 constraints/coverage 来自 P74，
字段定义较松；seed2 使用 P79 的明确 shape。比较时按**语义正确性**，不是逐字协议。

---

## 2. seed2 结果

| 场景 | 模型 | rounds | 结果 |
|---|---|---:|---|
| deep | MiniMax-M3 | 8 | ✅ 12/11, mux_node, control, comb=false |
| deep | MiniMax-M3.1-Flash | 11 | ✅ |
| deep | DeepSeek-Flash | 7 | ✅ |
| constraints | MiniMax-M3 | 9 | ✅ both_vars_block=packet.c_packet |
| constraints | MiniMax-M3.1-Flash | 6 | ✅ |
| constraints | DeepSeek-Flash | 8 | ✅ |
| coverage | MiniMax-M3 | 5 | ✅ |
| coverage | MiniMax-M3.1-Flash | 8 | ✅ |
| coverage | DeepSeek-Flash | 6 | ✅ |

### 运行时间

| 模型 | deep | constraints | coverage |
|---|---:|---:|---:|
| MiniMax-M3 | 106.2s | 43.6s | 61.1s |
| MiniMax-M3.1-Flash | 164.2s | 52.2s | 80.5s |
| DeepSeek-Flash | 49.7s | 29.9s | 28.6s |

### 运行故障

seed2 并行 3 个 agent 时，MiniMax 出现 3 次 `429 RATE_LIMIT`：

- M3 deep；
- M3 coverage；
- M3.1 deep。

这三项**不是语义失败**。改为单并发 + 60/120s backoff 重跑后全部通过。

---

## 3. 两 seed 对照

| 场景 | 模型 | seed1 | seed2 | 稳定性 |
|---|---|---|---|---|
| deep | MiniMax-M3 | ✅ clarified | ✅ | 稳定（clarified 后） |
| deep | MiniMax-M3.1-Flash | ✅ | ✅ | 稳定 |
| deep | DeepSeek-Flash | ✅ | ✅ | 稳定 |
| constraints | MiniMax-M3 | 🟡 `both_vars_block=cg` | ✅ `packet.c_packet` | **有方差** |
| constraints | MiniMax-M3.1-Flash | ✅ | ✅ | 稳定 |
| constraints | DeepSeek-Flash | ✅ | ✅ | 稳定 |
| coverage | MiniMax-M3 | ✅ | ✅ | 稳定 |
| coverage | MiniMax-M3.1-Flash | ✅ | ✅ | 稳定 |
| coverage | DeepSeek-Flash | ✅ | ✅ | 稳定 |

汇总：

```text
17/18 完整正确
1/18 部分：MiniMax-M3 constraints seed1，把 covergroup cg 当成“共同 block”
```

seed1 的 M3 错误不是工具退化：prompt 当时没有明确“constraint block”，
seed2 用明确 shape 后通过。P0 的 M3 deep 也有同类字段歧义（combinational）。

---

## 4. 关键发现

1. **P77 在 seed2 稳定生效**：三个模型 deep 都返回 12 节点/11 hops、
   `ternary_sel`、`mux_control=...u_stage.sel`。
2. **coverage 三个模型两 seed 都稳定**；`bin_details` 后不再需要内部 API。
3. **M3 的约束题有方差**：seed1 把 covergroup 当 block；seed2 明确字段后正确。
4. **M3 的 deep 字段也有方差**：P0 第一次 `combinational=true`；clarified 后通过。
5. **MiniMax 有 rate limit 风险**：并发 3 会 429；benchmark harness 需要
   单并发或退避。
6. 不是模型排名：样本小，且 seed1 协议不完全一致。

---

## 5. 结论

```text
deep:       3/3 × 2 seed，稳定
coverage:   3/3 × 2 seed，稳定
constraints: 8/9 完整 + 1 个字段歧义
```

工具层（P77）已经足够支撑这三类交互式查询；剩余问题主要是：

- prompt/answer shape 的明确性；
- MiniMax 的 rate limit/成本；
- 单 seed/小样本，不是真实 bug 基准。

## 6. 下一步

1. 不再扩 interactive 场景；
2. 做外部 benchmark（本地 VeriBugBench Icarus 小样本优先）；
3. 把 P1 harness 的 rate-limit 退避保留；
4. warm query service 仍排在外部证据之后。
