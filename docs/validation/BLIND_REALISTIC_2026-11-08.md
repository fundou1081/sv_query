# Blind realistic structural validation（P110）

**日期**: 2026-11-08
**范围**: AXI / SERV / Pico，5 个新任务，tool-only
**状态**: partial pass；false-confident=0，fresh set exact 9/10

---

## 1. 设计

任务不是由 agent 生成的；先冻结问题与 ground truth，再运行 agent。

5 个任务：

1. AXI `s_axi_rready` neighbors
2. AXI `m_axi_wdata` neighbors
3. SERV `bufreg.o_dbus_adr` neighbors
4. Pico `mem_axi_bvalid -> xfer_done` path
5. Pico `mem_ready_d` not_found

任务文件：

[tools/benchmark/blind_tasks_b_2026-11-08.json](../../tools/benchmark/blind_tasks_b_2026-11-08.json)

ground truth 来自源码 + canonical ID 对照；不是 agent 产出。

## 2. 首轮 P110a（暴露问题）

DeepSeek 首轮：

```text
3/5 exact
2/5 false-confident
```

两个失败：

1. `s_axi_rvalid` 答案字段是 `driver_ids/load_ids`，语义正确但 schema 不同；
   - 修复：benchmark 统一 alias 归一化，不把命名差异当语义错误。
2. Pico path 返回了 14 节点绕路路径，而不是 3 节点最短路径；
   - 真实工具 bug：path 默认选最长变体；
   - 修复：默认最短，`granular=true` 才选最长。

修复后同一批 DeepSeek 5/5，但该批已不再是 blind，仅作为回归。

## 3. fresh set B

修复后重新冻结 5 个新任务，一次性跑 2 模型：

| 模型 | exact | false-confident | mean wall |
|---|---:|---:|---:|
| MiniMax-M3 | **5/5** | **0** | 8.6s |
| DeepSeek-Flash | **4/5** | **0** | 8.9s |

合计：

```text
9/10 exact
0/10 false-confident
```

DeepSeek 唯一失败：

```text
{"task_id":'blind_b_axi_m_axi_wdata', ...}
```

单引号导致 JSON 解析失败；语义内容其实正确。  
这是格式/协议失败，不是 false-confident。

## 4. 结论

```text
false-confident 指标通过（fresh set 0/10）；
exact 9/10，仍有 1 个 JSON 格式失败；
不能宣称通用 debug 或 100% 正确。
```

首次 blind 的关键价值：

> 发现“path 默认最长”会在普通路径任务上绕路；这不是 synthetic case 能暴露的。

## 5. 边界

- 5 个任务，3 个设计，规模很小；
- ground truth 仍由项目作者冻结；
- 不是外部 fault set；
- 不是 fault localization / patch；
- 只测 tool-only 结构查询；
- evidence 支持没有逐条强制评分；
- 1 次运行。

## 6. 下一步

P111：snapshot/evidence 一键化；
P112：显式 unknown/abstention 与 confidence 合同。
