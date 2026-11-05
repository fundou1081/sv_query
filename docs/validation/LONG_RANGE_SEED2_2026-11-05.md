# 长程结构查询：seed-2 全 12 题复跑

**日期**: 2026-11-05
**PLAN**: P69.6
**范围**: 12 题，seed 2；两模型 × 两臂。
**工作区**: `/tmp/lr_pilot`，source 臂禁用全局 sv_query，清理缓存。
**注意**: source 臂仍非硬隔离（见 §4）。

## 1. 结果

| 模型 / 臂 | Exact | 说明 |
|---|---:|---|
| MiniMax-M3 / source | **6/12** | AXI 4/4；SERV 0/4；Pico 2/4 |
| MiniMax-M3 / svq | **12/12** | 全部 exact |
| DeepSeek-Flash / source | **10/12** | AXI 4/4；SERV 3/4；Pico 3/4 |
| DeepSeek-Flash / svq | **12/12** | 全部 exact |

### 与 seed 1 对比

| 模型 / 臂 | seed 1 | seed 2 |
|---|---:|---:|
| MiniMax source | 7/12 | 6/12 |
| MiniMax svq | 12/12 | 12/12 |
| DeepSeek source | 6/12 | 10/12 |
| DeepSeek svq | 12/12 | 12/12 |

观察：

- T2 两个 seed 都 **12/12**；
- source 臂波动明显：DeepSeek 6→10，MiniMax 7→6；
- source 臂的错误集中在 direct vs terminal fanout、path 节点粒度、source-only 下的 canonical ID；
- 小样本仍不能证明模型排名，但可以说明 **T2 的稳定性明显更好**。

## 2. 任务输入问题

第一次跑 Pico 相关 T2 时又出现混合 `full.f`，导致：

- `picorv32_axi.mem_valid` 的 direct load 被算成 0 或 adapter 内部 6 个；
- `mem_rdata[16]` 出现 bit fallback。

用任务规定的单文件输入重跑：

```bash
--file /tmp/lr_pilot/pico/picorv32.v
```

两个模型都正确。该结果已替换，不是 CLI 缺陷。

## 3. 软隔离

seed2 做到了：

- cwd `/tmp/lr_pilot`；
- source 臂运行时移走全局 `sv_query`；
- 清理 `*.json` 缓存；
- source 输出不再引用 `sv_query` 源码（抽查）。

但没有做到硬隔离：

- agent 仍可访问绝对路径；
- source agent 仍读取了 `/tmp` 里的历史 artifact（如 `e_all.json`、
  `drv.json`、`.q_clk.json`）作为 canonical ID 参考；
- 没有 OS sandbox/container。

所以 source 臂的数字仍是**受污染的控制组**，只能看方差，不能当作纯源码基线。

## 4. 成本

seed2 没有做 token/tool-call 汇总；只记录了 wall time。
不能把 seed2 当成成本结论。

## 5. 结论

- **T2 两 seed 稳定 12/12**，这是目前最强的信号；
- **source 臂方差大**（DeepSeek 6→10，MiniMax 7→6），说明“没有工具时结果依赖提示/命名/任务偶然性”；
- 仍不能外推准确率百分比、成本或模型排名；
- 需要 P69.7：12 题 × 3 seed + 容器/沙箱硬隔离 + token/cold-warm 成本。
