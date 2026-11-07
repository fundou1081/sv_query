# 12-task fixed protocol（P87）

**日期**: 2026-11-07
**性质**: source/T2 12 题，2 模型 × 2 臂 × 2 seed = 96 cells；
hard-isolated；固定 direct-query 协议；不是外部 benchmark。
**数据**: [long_range_12_fixed_2026-11-07.json](long_range_12_fixed_2026-11-07.json)

---

## 1. 协议

- 12 题：AXI 4 / SERV 4 / PicoRV32 4；
- 模型：MiniMax-M3 / DeepSeek-Flash；
- 臂：source / T2；
- seed：2；
- source/T2 hard sandbox；
- source 无 `sv_query`、无 repo；
- T2 不能读 task JSON/truth；
- 跑前 fact check；
- T2 direct fanin/fanout 必须 `--depth 1`；
- 最终 JSON 必须报告 `queries`。

全部 96 cells：

```text
rc=0
parsed=true
fact_check_ok=true
T2 depth1_ok = 24/24
```

无 429、无超时。

---

## 2. 总结果

| 模型 / 臂 | exact | false-confident high | mean wall |
|---|---:|---:|---:|
| MiniMax-M3 / source | 17/24 | 7/24 | 33.0s |
| MiniMax-M3 / T2 | **24/24** | 0/24 | 63.5s |
| DeepSeek-Flash / source | 15/24 | 2/24 | 80.2s |
| DeepSeek-Flash / T2 | **24/24** | 0/24 | 33.5s |

合计：

```text
source: 32/48
T2:     48/48
```

T2 和 source 的差距是 **16/48**。

---

## 3. 按任务

| task | source | T2 |
|---|---:|---:|
| axi_araddr_neighbors | 3/4 | 4/4 |
| axi_arvalid_fanin | 4/4 | 4/4 |
| axi_awvalid_fanin | 4/4 | 4/4 |
| axi_awvalid_fanout | 2/4 | 4/4 |
| serv_clk_fanout | 4/4 | 4/4 |
| serv_alu_clk_fanin | 4/4 | 4/4 |
| serv_cpu_clk_fanout | 1/4 | 4/4 |
| serv_clk_path | 4/4 | 4/4 |
| pico_mem_valid_fanout | 2/4 | 4/4 |
| pico_adapter_mem_valid_fanin | 0/4 | 4/4 |
| pico_adapter_mem_valid_fanout | 0/4 | 4/4 |
| pico_adapter_rdata_fanin | 4/4 | 4/4 |

source 的弱点集中在：

- SERV CPU clock fanout（terminal/direct）；
- Pico adapter 的 fanin/fanout；
- AXI fanout 的 canonical/terminal。

T2 没有失败项。

---

## 4. 和旧 12 题结果对比

旧 P69 结果：

```text
MiniMax source: 7/12, 6/12
DeepSeek source: 6/12, 10/12
T2: 12/12, 12/12
```

固定协议后：

```text
MiniMax source: 17/24 (≈8.5/12)
DeepSeek source: 15/24 (≈7.5/12)
T2: 48/48
```

source 仍差；T2 两个 seed 都 100%。  
但旧结果有 source 污染/协议不一致，不能和本轮直接合并成 3 seed。

---

## 5. 关键结论

1. **T2 在 12 个 direct structural tasks 上稳定 48/48。**
2. **source 在相同 hard isolation 下 32/48，且 9 个 high-confidence 错误。**
3. `--depth 1` + query log + fact check 后，T2 的 direct 语义没有失败。
4. 这证明的是“canonical structural query 执行”，不是 debug reasoning。
5. 任务仍是 direct/short，不能外推到多轮深跳、真实 bug 修复或 HWE。

## 6. 成本

- T2 token 未统计；wall time 混合：
  - DeepSeek T2 更快（33.5 vs 80.2s）；
  - MiniMax T2 更慢（63.5 vs 33.0s）。
- 没有价格换算，不能声称成本优势。
- T2 的 cold build 与 warm query 未拆分。

## 7. 边界

- 2 模型 ×2 seed，不是 3 seed；
- exact canonical only；semantic 对 direct task 为 n/a；
- 12 题手工选择；
- 不是 HWE/VeriBug；
- 不作模型排名。

## 8. 下一步

1. 补 token/cold-warm 统计；
2. 第三方外部故障集（VeriBug Icarus 小样本）；
3. 如果继续内部评测，只做 3rd seed，不再加题；
4. 不再用 direct 结果证明 debug 能力。
