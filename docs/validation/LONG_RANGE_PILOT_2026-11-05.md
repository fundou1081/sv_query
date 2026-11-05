# 长程结构查询 pilot：source-only vs sv_query

**日期**: 2026-11-05
**PLAN**: P69
**性质**: 4-task pilot，**不足以作为产品有效性结论**；用于验证协议、暴露隔离问题。
**模型**: MiniMax-M3 (`minimax-cn`) / DeepSeek-Flash (`deepseek-official`)
**原始结果**: [long_range_pilot_2026-11-05.json](long_range_pilot_2026-11-05.json)
**评分脚本**: [score_long_range.py](../../tools/benchmark/score_long_range.py)

## 1. 协议

- 4 个任务：2 个真实跨模块连接、1 个跨模块路径、1 个单文件结构查询；
- 2 个模型 × 2 臂：
  - `source`：只读源码/grep；
  - `svq`：同一模型 + 安装的 `sv_query` CLI；
- 每题要求 exact canonical IDs；`--depth 1` / structural shortest path 已写进题面；
- 评分脚本确定性比较，不调用模型。

Ground truth：

| task | answer |
|---|---|
| `axi_fanin` | driver `axi_adapter.axi_adapter_rd_inst.m_axi_araddr_reg`；load `axi_adapter.m_axi_araddr` |
| `serv_fanout` | 3 个 `i_clk`/`clk` 端口 |
| `pico_fanout` | `picorv32_axi.axi_adapter.mem_valid` |
| `serv_path` | `clk → cpu.clk → cpu.alu.clk`，2 hops |

## 2. 汇总

| 模型 / 臂 | exact | high-confidence wrong | 平均 wall time |
|---|---:|---:|---:|
| MiniMax-M3 / source | **1/4** | **2/4** | 68.7 s |
| MiniMax-M3 / svq | **4/4** | **0/4** | 28.3 s |
| DeepSeek-Flash / source | **2/4** | 0/4 | 62.6 s |
| DeepSeek-Flash / svq | **3/4** | 0/4 | 21.9 s |

> `DeepSeek-Flash / svq` 的 3/4 包含一个空输出（schema/agent 失败），不是“答错但自信”。

## 3. 逐题

| task | MiniMax source | MiniMax svq | DeepSeek source | DeepSeek svq |
|---|---|---|---|---|
| axi_fanin | ✗ 空输出 | ✓ | ✗ loads 空 | ✓ |
| serv_fanout | ✓ | ✓ | ✓ | ✓ |
| pico_fanout | ✗ 重复 load，count=2 | ✓ | ✗ ID 带 `@file:line` 后缀 | ✗ 空输出 |
| serv_path | ✗ 用 `cpu` 实例节点代替 `cpu.clk` | ✓ | ✓ | ✓ |

## 4. 初步观察（只作方向）

1. 在这 4 题上，`svq` 臂对 **canonical ID / 路径节点粒度** 更稳定：
   MiniMax 1→4，DeepSeek 2→3。
2. 源码臂出现了 **高置信错误**：MiniMax 在 pico count 和 path 粒度上都是 `high`，但都错。
3. wall time 上 `svq` 臂更短（21.9–28.3 s vs 62.6–68.7 s），但这不是干净成本结论：
   未统计 token；`svq` 可能复用图缓存；样本只有 4。
4. 工具不会自动消除错误：DeepSeek-Flash 的 `svq` 臂仍有一个空输出；
   之前 AXI path 的扩展 run 还出现过把 instance hub 当路径节点的误读。

## 5. 有效性威胁（必须读）

- **n=4，单 seed，任务为手工挑选**，不能外推。
- **source 臂没有完全隔离**：MiniMax-M3 的 `serv_fanout` 输出引用了
  `sv_query` 源码里的 canonical ID 规则；说明 source-only 控制组仍摸到了仓库/工具知识。
  该臂的数字只能算“受污染的方向性结果”。
- 空输出被计为错误；没有重试，也没有区分 schema 失败/模型拒答/超时。
- 成本只有 wall time，没有 input/output tokens；`svq` 的 cold build、cache 命中未拆分。
- Ground truth 由源码人工追踪 + sv_query 枚举双来源建立，但不是完全双盲。
- 任务粒度已用 `--depth 1`/structural path 固定；source 模型仍可能按“terminal fanout”理解，
  这是语义定义差异，不应全部归因于模型能力。

## 6. 结论

这组 pilot **支持继续做对照**，但不支持任何“准确率提升 X%”的产品声明。

下一步应先修协议而不是扩大样本：

1. source 臂放到真正隔离的工作区（无 `sv_query` 源码、无已缓存结果、最好无安装二进制）；
2. 冻结 12–15 题，同一题多 seed；
3. 记录 tokens/tool calls，拆分 cold build / warm query；
4. 增加空输出重试规则并单列；
5. 再决定是否值得跑 30–50 题。

## 7. 不涉及

- HWE-Bench / VeriBugBench 修复实验；
- 商业调试工具对照；
- 多线程/门级性能；
- 任何 agent 根因命中率的结论。
