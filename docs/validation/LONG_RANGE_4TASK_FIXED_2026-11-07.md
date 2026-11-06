# Long-range 4-task pilot：修复查询协议后

**日期**: 2026-11-07
**状态**: P83 完成
**数据**: [long_range_4task_fixed_2026-11-07.json](long_range_4task_fixed_2026-11-07.json)

---

## 1. 修复内容

针对 P82 的失败：

1. T2 prompt 明确：direct distance=1 的 fanin/fanout 必须使用 `--depth 1`；
2. 最终 JSON 必须包含 `queries`；
3. runner 检查 T2 query log 是否含 `--depth 1`；
4. 跑前用当前图做 **确定性 fact check**；
5. source prompt 明确 direct = 单跳，不是 terminal。

fact check 先发现了 `paths` 的 **direct envelope** 兼容 bug 和 SERV 路径误报；
修复后 4 题 ground truth 全部与当前图一致。

---

## 2. 结果

4 题 × 2 模型 × 2 臂 × 2 seed = 32 cells。  
全部 rc=0、parsed=true、fact_check_ok=true；无 429。

| 模型 / 臂 | exact | false-confident high | mean wall |
|---|---:|---:|---:|
| MiniMax-M3 / source | 5/8 | 3/8 | 34.2s |
| MiniMax-M3 / T2 | **8/8** | 0/8 | 50.2s |
| DeepSeek-Flash / source | 6/8 | 0/8 | 88.6s |
| DeepSeek-Flash / T2 | **8/8** | 0/8 | 41.1s |

合计：

```text
source: 11/16
T2:     16/16
```

## 3. 按任务

| task | source | T2 |
|---|---:|---:|
| axi_araddr_neighbors | 3/4 | **4/4** |
| serv_clk_path | 4/4 | 4/4 |
| pico_adapter_mem_valid_fanout | **0/4** | **4/4** |
| pico_adapter_rdata_fanin | 4/4 | 4/4 |

T2 的提升集中在 direct fanout 语义；`serv_clk_path` 和 bit fanin 两边都稳定。

## 4. 协议检查

`queries` 自报：

- MiniMax-M3 T2：8/8 含 `--depth 1`；
- DeepSeek-Flash T2：3/8 含 `--depth 1`；
- 其余 5 个 DeepSeek T2 虽然答案 exact，但没有在最终 JSON 报告 query。

所以：

```text
T2 exact: 16/16
T2 可审计 query log: 11/16
```

不能把“答案对”与“按协议执行”混为一谈。  
DeepSeek 需要更严格的 query-log schema，否则只能算“结果对、过程未证明”。

## 5. 结论

修复协议后：

- **T2 在这 4 个 direct-query 任务上明显优于 source**：16/16 vs 11/16；
- 失败主要来自 source 的 direct vs terminal 误读；
- T2 没有 high-confidence 错误；
- hard isolation、fact check、`--depth 1` 都生效；
- 但仍是 4 题、direct query、2 seed；不能外推到 debug reasoning 或 12×3。

## 6. 下一步

1. 强化 T2 `queries` 强制字段（缺 query 视为协议失败）；
2. 跑 12 题 ×2 seed（T2/source）之前，先确认 5 个 query-log 缺失可修；
3. 双评分仍未做；
4. 不把本结果写成“T2 通用更强”。

## 7. 边界

- 4 题、2 模型、2 seed；
- direct/短路径，不是多轮深跳；
- source/T2 budget 仍是 prompt 约束；
- 没有 token/价格统计；
- 不作模型排名。
