# Long-range 4-task pilot（P82）

**日期**: 2026-11-07
**性质**: hard-isolated source/T2 pilot；不是 12×3，不宣称模型排名。
**数据**: [long_range_4task_2026-11-07.json](long_range_4task_2026-11-07.json)

---

## 1. 协议

- 4 题：
  - `axi_araddr_neighbors`
  - `serv_clk_path`
  - `pico_adapter_mem_valid_fanout`
  - `pico_adapter_rdata_fanin`
- 2 模型：MiniMax-M3 / DeepSeek-Flash；
- 2 臂：source / T2；
- 2 seed；
- 32 cells；
- source/T2 同 prompt、budget=8；
- source 用 `source.sb`，T2 用 `t2_long.sb`；
- workspace 只含 RTL + 本地 filelist。

**结果**：32 cells 全部 rc=0、parsed=true；无 429、无超时。

---

## 2. 汇总

| 模型 / 臂 | exact | false-confident high | mean wall |
|---|---:|---:|---:|
| MiniMax-M3 / source | 5/8 | 3/8 | 28.3s |
| MiniMax-M3 / T2 | 4/8 | 4/8 | 26.8s |
| DeepSeek-Flash / source | 6/8 | 0/8 | 69.2s |
| DeepSeek-Flash / T2 | 6/8 | 0/8 | 74.8s |

总体：

```text
source: 11/16
T2:     10/16
```

**在这 4 题上，T2 没有优势。**

---

## 3. 按任务

| task | exact |
|---|---:|
| axi_araddr_neighbors | 7/8 |
| serv_clk_path | **8/8** |
| pico_adapter_mem_valid_fanout | **0/8** |
| pico_adapter_rdata_fanin | 6/8 |

---

## 4. 关键失败

### 4.1 pico_adapter_mem_valid_fanout：0/8

直接 CLI 事实：

```bash
sv_query loads picorv32_axi.axi_adapter.mem_valid \
  --file picorv32.v --depth 1
```

返回 **6 个 direct loads**，与 ground truth 一致。

但 agent 返回：

- 9 个，包含 `ack_awvalid/ack_arvalid/ack_wvalid`；
- 7 个，包含 `ack_clear`；
- 或合成 `mem_valid_load_L2773_...` 节点；
- 或 7 个重复的 `mem_valid`。

这不是工具事实错误，而是：

> agent 没有真正执行 `--depth 1` 的 direct fanout；
> 或把 terminal/内部 load 当成 direct load。

### 4.2 pico_adapter_rdata_fanin

MiniMax-M3 T2 seed1 返回：

```text
picorv32_axi.mem_axi_rdata[16]
```

而正确是：

```text
picorv32_axi.axi_adapter.mem_axi_rdata[16]
```

直接 CLI 查询正确。  
这是 agent 选错目标/父路径，不是图缺陷。

### 4.3 axi_araddr_neighbors

MiniMax-M3 T2 seed2 返回 drivers 正确，但 **loads 为空**，仍标 high。  
source/T2 都有高置信错误。

---

## 5. 重要结论

1. **hard isolation 生效**：所有 agent 都能跑完，没有权限崩溃；source 无 `sv_query`，T2 无法读 task JSON。
2. **之前 soft 12 题 T2 12/12 没有在硬隔离 4 题上复现**。
3. 主要失败不是“图算错”，而是 **agent 查询纪律**：
   - 不用 `--depth 1`；
   - 把 terminal load 当 direct；
   - 选错父路径；
   - 高置信但没验证 count。
4. source 也没有优势；它同样会误读 terminal/direct。
5. 任务设计仍然是**直接查询**，不是多轮深跳。

---

## 6. 对 benchmark 的含义

这轮支持一个更谨慎的结论：

> 工具本身能给出 6/6 的 direct fanout；  
> 但 agent 在自然语言任务下不一定正确使用 `--depth 1`。

所以下一轮应先修**agent 使用协议**，而不是扩大任务数：

- T2 prompt 明确要求：direct 查询必须 `--depth 1`；
- 要求 agent 在最终答案里报告 query command；
- runner 检查 query log 是否包含 `--depth 1`；
- source 任务强调“direct”与“terminal”的区别；
- 每题先做一次确定性 CLI fact check，确认 ground truth 与当前图一致。

---

## 7. 下一步

1. 用修正后的 prompt 重跑这 4 题（先 1 seed）；
2. 若 T2 仍不胜出，不再扩 12×3；
3. 如果 T2 胜出，再跑 4 题 ×2 seed / 12 题；
4. 双评分仍未做，不能把 file:line 等语义正确答案简单算错。

## 8. 边界

- 4 题、2 seed；
- 不是 12×3；
- 不宣称模型排名/成本优势；
- source/T2 budget 只是 prompt 约束；
- 本次没有统计 tokens。
