# evidence=true 成本（P108）

**日期**: 2026-11-08
**范围**: 3 个代表 cell ×2 模型；evidence=false / true 对照
**数据**: /tmp/tool_evidence_true.json（未入库）

---

## 1. 结果

evidence=true 仍全部正确：

```text
6/6 exact
```

wall：

| cell | MiniMax | DeepSeek |
|---|---:|---:|
| AXI araddr | 7.8s | 4.2s |
| SERV clk path | 7.2s | 4.1s |
| Pico adapter fanout | 8.5s | 10.1s |

## 2. token 成本

从 DSH session usage 统计：

| cell | 默认 | evidence | 变化 |
|---|---:|---:|---:|
| Mini AXI | 9012 | 9089 | +0.9% |
| Mini SERV | 9097 | 9061 | -0.4% |
| Mini Pico | 9060 | 9580 | +5.7% |
| Deep AXI | 8994 | 9010 | +0.2% |
| Deep SERV | 8892 | 9076 | +2.1% |
| Deep Pico | 8991 | 9372 | +4.2% |

合计：

```text
默认 54046
evidence 55188
+2.1%
```

## 3. 解释

- evidence 只返回 1–4 个节点的 source_context；
- 不是全文件，所以成本有限；
- 最大增幅在 fanout 多节点 + MiniMax 的组合；
- 本对照不是严格同 prompt：有些 default call 带了 details，模型自行加的；
- token 统计来自 session usage，不是 API 账单。

## 4. 结论

```text
evidence 成本约 +2%；
对失败复核足够便宜；
可以保留 opt-in。
```

## 5. 边界

- 3 cells，不是 12 题全量；
- 1 次运行；
- 不同模型 token 口径可能有差异；
- 不是模型排名。
