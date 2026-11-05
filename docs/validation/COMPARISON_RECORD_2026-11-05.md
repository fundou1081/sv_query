# 对比结果冻结记录（2026-11-05）

**性质**: 内部验证冻结；不是对外基准声明。
**实验 run commit**: `c6bebc78`（12-task，48 agents）
**结果修正**: 之后对 Pico bit 题用单文件输入重跑（2 agents），结论以本文件/结果 JSON 为准。

## 1. 冻结产物

| 产物 | SHA256 |
|---|---|
| `docs/validation/long_range_12_2026-11-05.json` | `58898bcbfebe4b0daa1f4928e56f331fe837483b1ea36fcf8f11d4fb4aba7360` |
| `tools/benchmark/long_range_tasks.json` | `8ba60bf70a9aaca361778ced4d55751442aafeab434b0588244e7f00232e3a61` |
| `tools/benchmark/score_long_range.py` | `50fbfd6d2e01f21da6d0e58427b272429bd5c303da7113c71a22377b21693eba` |
| `tools/benchmark/verify_long_range.py` | `a9b995891356b0ed22ebdc28f9f226cc11b02a0f24b541bcda69ced03ea615f6` |
| `docs/validation/long_range_12_usage_2026-11-05.json` | `d240acb35105d8d94d0d2e79a794f7702e1f3181f702ec03f2bb80760fc2f9de` |

模型：

```text
MiniMax-M3      provider=minimax-cn
DeepSeek-Flash  provider=deepseek-official
```

任务：12（AXI 4 / SERV 4 / PicoRV32 4），2 模型 × 2 臂 = 48 cells。
Ground truth：源码人工追踪 + sv_query 双来源，冻结在 tasks JSON。

## 2. 冻结结果

| 模型 / 臂 | Exact | 高置信错误 | Mean wall |
|---|---:|---:|---:|
| MiniMax-M3 / source | 7/12 | 2/12 | 51.4 s |
| MiniMax-M3 / svq | 12/12 | 0/12 | 130.6 s |
| DeepSeek-Flash / source | 6/12 | 1/12 | 57.2 s |
| DeepSeek-Flash / svq | 12/12 | 0/12 | 74.9 s |

解释：见 [LONG_RANGE_12_2026-11-05.md](LONG_RANGE_12_2026-11-05.md)。

**Token/tool-call**（DSH 子 session 日志；total input = uncached + cacheRead）：

| 模型 / 臂 | mean tokens | tool calls | tokens/correct |
|---|---:|---:|---:|
| MiniMax source | 237.6k | 15.2 | 407.4k |
| MiniMax svq | 329.7k | 18.4 | 329.7k |
| DeepSeek source | 123.2k | 8.3 | 246.4k |
| DeepSeek svq | 244.2k | 12.0 | 244.2k |

原始汇总：[long_range_12_usage_2026-11-05.json](long_range_12_usage_2026-11-05.json)。
不要把 wall time 或 token 总量单独当成本；没有价格换算。

## 3. 单独复验脚本

```bash
cd /Users/fundou/my_dv_proj/sv_query
python3 tools/benchmark/verify_long_range.py --json
```

检查三层：

1. 结果覆盖：12 题 × 2 模型 × 2 臂 = 48 cells，无缺/多；
2. 结果评分：调用 `score_long_range.py`，不允许结果 JSON 自报分数；
3. Ground truth：用稳定 source（AXI filelist / SERV 生成 filelist /
   Pico 单文件）重新构图，执行 direct fanin/fanout/path，与冻结答案逐项比对。

最近一次：

```text
coverage: OK (48 cells)
truth: 12/12 OK
result: ✅ PASS
MiniMax source 7/12; MiniMax svq 12/12
DeepSeek source 6/12; DeepSeek svq 12/12
```

脚本**不重跑 LLM**。重跑模型对照仍需 workflow/subagent 与模型凭证；
复验脚本只验证“结果记录 + 当前工具事实”。

## 4. 已知缺陷 / 修正

- 首次 T2 Pico bit 结果被混合 `full.f` 污染，已用
  `--file pico/picorv32.v` 重跑并修正；任务 JSON 现在带
  `source` + `query` 约束，复验脚本拒绝依赖临时混合 filelist。
- source 臂仍不干净：MiniMax 输出引用了 sv_query 源码的 ID 规则；
  因此 source 准确率是“受污染下界”，不能当作纯源码对照。
- 已有 token/tool-call 汇总（未做价格换算/cold-warm 拆分）；单 seed；任务手工挑选。
- 结论：工具主要改善 exact 正确性与模型间一致性；本轮没有成本优势。

## 5. 外部可用性

在完成真正隔离、多 seed、cold/warm 成本拆分前，不将本记录写成 README 的
性能/准确率承诺，也不对外声称 HWE-Bench/VeriBugBench 效果。
