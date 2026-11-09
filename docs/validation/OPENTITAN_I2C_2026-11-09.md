# OpenTitan I2C second-block pilot（P123）

**日期**: 2026-11-09
**性质**: 第二个真实 OpenTitan block，验证 UART 经验是否可复用
**结果**: 3 任务 ×2 模型 = 6/6 exact，0 false-confident

---

## 1. Onboarding

Worker `opentitan-pilot`（MiniMax-M3）按模型选择规则承担调研/建图，
主 agent 负责验收和修正任务语义。

| 项 | i2c | UART 参考 |
|---|---:|---:|
| files | 67 | 60 |
| nodes | **9370** | 4803 |
| edges | **17599** | 8507 |
| elaboration errors | **0（首次）** | 0（4 轮后） |
| cold build | 16.50s | 7.57s |
| snapshot | 12.1MB | 5.9MB |
| dynamic nodes | 247 | 1 |

首次即 elaborate，说明 UART 的依赖闭包规则可复用：
- `prim_generic` 的 tech-specific cells；
- `top_pkg/top_racl_pkg`；
- `+incdir`；
- 不列 include-only `.svh`。

## 2. Agent 任务

| task | MiniMax | DeepSeek |
|---|---|---|
| T1 INTR_TEST gate | ✅ 344s / 126 calls | ✅ 586s / 92 calls |
| T2 SCL path | ✅ 15.7s / 8 calls | ✅ 44.6s / 20 calls |
| T3 verify claims | ✅ 25.5s / 10 calls | ✅ 23.0s / 14 calls |

合计：

```text
6/6 exact
0 false-confident
0 false-found
```

T3 初始 runner 失败是 **benchmark schema 分类错误**：把 verify status 任务归成
`t3`（evidence file/line），改为 `t4` 后 2/2。不是工具错误。

## 3. 对 worker 报告的两处纠正

Worker 报告里有两处把**任务语义错误**说成工具 bug，主 agent 已核实并纠正：

### 纠正 1：claim E 不是 tool false negative

`i2c.sv:154`：

```systemverilog
assign cio_scl_en_o = ~scl_int;
```

所以 `cio_scl_en_o` 的**直接 driver 是 `scl_int`**。  
`scl_out_fsm` 是 4-hop 上游，不是直接 driver。

因此：

```text
claim: scl_out_fsm directly drives cio_scl_en_o
→ contradicted 是正确的
```

path 证明的是 transitive reachability，不是 direct driver。  
Worker 把它解释成“drivers 不遍历 bitwise-NOT”是错的；直接 fanin 正是 `scl_int`。

### 纠正 2：compound boolean 结论使用了错误实例名

Worker 用：

```text
i2c.i2c_core.u_bus_monitor.start_det
```

但实际实例是：

```text
i2c.i2c_core.u_i2c_bus_monitor.start_det
```

用正确 ID：

```text
drivers(start_det) = thd_dat_i, monitor_enable, ctrl_det_count, start_det_pending
```

所以没有“drivers 漏掉 compound boolean 项”的证据。  
不需要为此改 core。

## 4. 真实问题

### P1 — I2C T1 成本高

```text
MiniMax 344s / 126 calls
DeepSeek 586s / 92 calls
```

INTR_TEST 有 15 个 load，agent 需要大量搜索；比 UART T1 更贵。

### P2 — 动态节点多

```text
dynamic_nodes 247
```

FIFO/arbiter/SRAM 区域更弱；本次任务刻意避开。

### P3 — verify consistency 仍 advisory

I2C clean design 上 806 violations，主要是 reggen packed-struct width；
不能当 pass/fail gate。

### P4 — 依赖闭包仍手工

虽然首次 elaborate，filelist 仍是手写的 67 文件；`.core` 依赖仍是 superset。

## 5. 结论

```text
第二个真实 block 建图成功；
3 个任务 6/6；
UART onboarding 规则可复用；
但 I2C T1 成本已经接近实际上限。
```

同时证明：

```text
worker 适合调研/建图；
任务语义和工具结论必须由主 agent 复核。
```

## 6. 边界

- 只测 i2c；
- 3 个任务；
- 不是连续 3 任务一次 run（T1/T2 初始，T3 重跑）；
- 不是外部 fault set；
- 不是 fault localization / patch。
