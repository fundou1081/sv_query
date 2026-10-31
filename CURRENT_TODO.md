# CURRENT_TODO — 当前正在做的事

> **计划源**: 代码修改计划以 [PLAN.md](PLAN.md) 为**全局唯一真相源**；本文件只记录"此刻"的上下文。
> **位置固定**: 根目录 `CURRENT_TODO.md`, 路径永不变更。
> **更新时机**: 每次开始任务 / 完成 sub-task / 被打断切换任务时, 立即更新。
> **最后更新**: 2026-10-29 GMT+8 (iter_314: P18 可信性与测试入口收尾)

---

## 🎯 当前计划（以 [PLAN.md](PLAN.md) 为准）

- **已完成**: P0~P12 全部完成（含 P5~P12 位精确性系列，iter_289~300）
- **当前 item**: 无（P26 完成；等待新需求/评审项）
- **P13 评审 backlog**: 见 [trace_capability_review_2026-10-27](docs/architecture/trace_capability_review_2026-10-27.md)
- **P18~P24** ✅；**P25** 条件化简/互斥仅记录（未排期）；**P26.1** 遍历完整性 ✅（iter_321）；**P26.2** 运行期系统函数 ✅（iter_322）
  → P13.6（多驱动/静态 memory）
- 开工前先更新 PLAN.md + 跑 `python3 tools/check_plan.py`

---

## 📦 仓库状态 (2026-10-27)

- **分支 = `main`**（推送 `backup/main`；本轮文档提交后以 `git log -1` 为准）
- **全量基线**: **2489 passed / 0 failed**（`sim/tests/`, `-m "not opensource"`；
  7 skipped / 152 deselected）；35 命令（core 25 / view 10）
- **图缓存**: `CACHE_VERSION = 1.4`；图基线 6 fixture（`sim/tests/golden/graph_baseline/`）
- **位精确性**: 显式位/切片/寄存器/总线桥/表达式（位运算、加减乘、常量移位、Slice）/
  直接拷贝/纯拼接/常量位/`integer` 宽度/signedness/packed struct 聚合+成员+成员位桥
  全部有模型；比较/逻辑/变量移位/动态选择/函数调用为本质粗粒度（见 KNOWN_LIMITATIONS §3.6）
- **已登记限制**: `SVQ_BIT_BRIDGE` 默认 `one`（`full` 可选）；深层成员（`o.inner.a`）
  与非 packed struct 不参与位桥

---

## 📍 最近完成（位精确性系列）

| 迭代 | 内容 | 关键结果 |
|---|---|---|
| iter_289~292 | 位精度审计 + F1/F2/F3/F5 | 切片/负载按位精确，写污染/断链修复 |
| iter_293 | F4 总线位桥（`one` 默认/`full` 可选） | 缺位侧合成，纯总线可贯通 |
| iter_294 | 表达式按运算符逐位映射 | 位运算/加减乘/常量移位/Slice |
| iter_295 | 直接拷贝 + 纯拼接 | `assign y=a` 位精确；`{a,b}` 分段 |
| iter_296 | 常量位分解 | `4'hA` → `1'b1`；拼接字面量段 |
| iter_297 | signedness 建模 | `TraceNode.is_signed`；符号扩展 |
| iter_298 | 整数类型位宽 | `integer/int/byte/...` 真实宽度 |
| iter_299 | packed struct/union（聚合+成员布局） | 宽度/signedness/位段 |
| iter_300 | packed 成员位级查询桥 | `p.a[1]` ↔ `p[5]` |

---

## ✅ 刚完成（P13.1，P0 静默错误）

**现象（实测）**: 默认 `one` 建图后切换 `SVQ_BIT_BRIDGE=full` 再用缓存 → 仍是 5 节点（应 37）。
**根因**: `UnifiedTracer._graph_cache_key` 未包含 bit-bridge 模式。
**修法**: key 加 `-bb{one|full}`；补回归测试（两种模式各建一次，节点数不同且互不串）。
**验收**: 切换模式后必须重建；同模式缓存仍命中；全量 0 failed。
**结果 (iter_302)**: key 加 `-bb{one|full}`；one→full 5→37、full→one 37→5；同模式命中；
新增 `test_bit_bridge_cache.py`（5 个）；全量 **2494 passed**。

## ✅ 刚完成（P13.2，粗粒度回退标记）

位查询回落总线时输出与位精确同形 → agent 可能误读。
**结果 (iter_303)**: 节点 `precision: bit|bus|constant`；signal 级 `precision`（bit/bus/unknown）
+ `coarse_fallback`（过滤前判定）；顺带修 CLI 位查询"节点不在图"直接报错的 bug
（`attach_distances` root 缺失）；新增 6 个 CLI 测试，全量 **2500 passed**。

## ✅ 刚完成（P13.3，capabilities + 输出字段）

- `capabilities` 增加 `bit_precision` 段：精确/粗粒度形态、`SVQ_BIT_BRIDGE` 模式、已知边界
- trace 输出节点补 `is_signed` / `parent` / `bit_range`（位节点继承父 signedness）
**结果 (iter_304)**: `capabilities --json` 带 12 项 precise / 6 项 coarse / 模式 / markers；
节点输出三字段；位节点继承 signedness；3 个 CLI golden + scheduler 基线有意重生成；
全量 **2508 passed**。

## ✅ 刚完成（P13.4，深层 packed 成员）

`o.inner.a` 之前不建节点 → 查询空答。
**结果 (iter_305)**: 适配器 `get_packed_member_tree`（递归、深度 8）；layout pass 递归建节点
（上限 5000）；fanout 同时并入聚合总线与位子节点负载。
`fanin(o.inner.a[1])` → `{x[1]}`，`fanout` → `{y[9]}`；新增 4 测试，全量 **2512 passed**。

## ✅ 刚完成（P13.5，三元/case 分支按位）

`s = c ? a : b; y = s[3]` 之前返回 `{s[3], a, b}`（分支总线级）。
**结果 (iter_306)**: `TernaryBranch` 同索引（要求等宽）；源位节点存在时
`fanin(y)={s[3],a[3],b[3]}`、`fanout(a[3])={ta,s[3],y}`；case 同理；宽度不等回落总线。
新增 7 测试，全量 **2519 passed**。

## ✅ 刚完成（P13.6，多驱动标记 + 静态 memory 位精度）

- 多驱动：`assign y=a; assign y=b` → 无标记；现输出 `driver_count/multi_driver/conditional_drivers`
- 静态 memory：`mem[1]` 宽度 (1,0) → 8 位；F4 合成 `mem[1][k]`；`fanin(z)={y[3],mem[1][3],d[3]}`
- 顺带修 `extra=None`（wire_init）与两处 `except: pass`（纪律 2.5）
**结果 (iter_307)**: 新增 9 测试；全量 **2528 passed**；缓存 1.5。

## ✅ 刚完成（P14.1，动态索引显式 unknown）

`mem[i]` 动态读之前和总线答案同形；现在 `precision=unknown` + `dynamic_index=true`
（fanin/fanout/节点级），静态 memory 不受影响。新增 5 个 CLI 测试，全量 **2533 passed**。

## ✅ 刚完成（P15，位级 endpoint 便捷入口）

`paths`/`dataflow analyze`/`trace impact` 支持 `--bits`（逗号分隔，按端点顺序/批量对齐）；
位节点存在 → precision=bit；缺失 → 回落总线 + `coarse_fallback=true`。
新增 7 个 CLI 测试，全量 **2540 passed**。

## ✅ 刚完成（P16，动态索引递归传播）

动态索引标记改到**图级**（`_mark_dynamic_provenance` + `SignalGraph._dynamic_nodes`）：
深链、depth=1、fanout、动态写污染静态读都正确 unknown；参数同名切片不再误报；
标记随缓存序列化（CACHE_VERSION 1.6）。新增 7 测试，全量 **2547 passed**。

## ✅ 刚完成（P18，方豆 1→2→3）

1. **P18.1 层次化条件作用域** ✅（iter_312）：`if (u.q)` / `u.u2.q` / `top.u.q` 都能
   解析到实例节点，修端口接不同线名时的动态漏标；括号内不做叶名兜底，参数不误报。
2. **P18.2 函数调用诚实标记** ✅（iter_313）：函数结果节点 `top.f` 不再伪装成 bus；
   `function_call=true` + `precision=unknown`，下游/位子树传播；不做 inline。
3. **P18.3 `--bits` 范围/显式映射** ✅（iter_314）：支持 `7:4` 与 `src=1,dst=5`；
   范围缺失显式回落总线 + `coarse_fallback`。
4. **P18.4 收尾** ✅：全量 **2572 passed**；检查全绿。

**不做**：函数 inline（第 4 项）、有符号算术逐位（第 5 项）。

## ✅ 刚完成（P19，函数条件诚实标记）

`if (f(a))` / `if (f(a) > 0)` / `f(a) ? b : c` / `case (f(a))` /
`posedge f(a)` / package 函数：即使图上没有 `top.f` 结果节点，也标
`function_call=true` + `precision=unknown`。新增 7 测试，全量 **2579 passed**。

## ✅ 刚完成（P20，宏/动态拼接函数）

宏 alias/包装/令牌拼接/ifdef/package/层次函数均已覆盖并加回归测试；
补上 DPI import（`$unit`）与 interface 函数两个真缺口；系统函数有意不标。
新增 6 测试，全量 **2585 passed**。

## ✅ 刚完成（P21→P22）

1. **P21 真实工程 smoke** ✅（iter_317）：strict_uart / verilog-axi / picorv32
   构建+查询+缓存标记验证；新增 smoke 工具与仓库内回归测试。
2. **P22 条件输出** ✅（iter_318）：fanin/fanout 输出每个结果节点的
   `condition`/`conditions`，signal 级 `conditions`；无条件字段为空；
   嵌套条件/ternary 测试覆盖。

全量 **2591 passed**。

## ✅ 刚完成（P23，路径条件组合）

depth>1 深层 driver 沿最短路径组合条件 `(c1) && (c2)`，输出 `condition_path`；
嵌套 if/ternary 用完整 `condition_chain`。顺带修缺失位节点导致的
`NetworkXError`（smoke 发现）。全量 **2594 passed**。

> 边界：只走最短路径，不枚举多路径 OR；无图路径的位节点条件可能为空。

## ✅ 刚完成（P24，多路径条件 OR）

同一 driver 多条路径：`condition=(p1) || (p2)`；`conditions` 保留每路径组合，
`condition_paths` 保留每路径原始序列；无条件路径优先为 `condition=""`；
枚举上限 8 路径/深度 20/5000 展开，触顶标 `condition_truncated`。
全量 **2598 passed**。

## ✅ 刚完成（P26，遍历完整性 + 运行期系统函数）

1. **P26.1** ✅ 遍历完整性：`truncated_by_depth`、`cycles_detected`（capped null）。
2. **P26.2** ✅ 运行期系统调用：`$random/$urandom...` → `runtime_system_call=true` + unknown；
   修了 `$random` 节点 id 变成对象 repr 的不可复现 bug。
3. **P26.3** ✅ 6 新测试；3 golden 重生成；真实 smoke 全 PASS；全量 **2609 passed**。
P25（条件化简/互斥）仍只记录、未排期。

## 后续候选

P0~P18 backlog 已清空。可选方向：
- 函数 inline（需单独立项；当前只做诚实标记）
- 有符号算术/比较语义（按方豆决定暂不做逐位）
- 条件层次化显示文本（当前 dynamic 解析已修，显示仍可能退化）
- `--bits` 的 `+:`/变量范围（当前仅静态 hi:lo）

---

## 🧰 固定设施与门禁

```bash
python3 -m pytest sim/tests/ -m "not opensource" -q -p no:randomly   # 全量
python3 tools/check_docs.py            # 死链/归档/未登记
python3 tools/check_plan.py            # 计划树
python3 tools/check_cli_layers.py      # 分层
python3 tools/gen_cli_surface.py --check
python3 tools/check_except_pass.py
```

| 设施 | 位置 |
|---|---|
| 计划树 | [PLAN.md](PLAN.md)（唯一） |
| 迭代记录 | `docs/task_tree/iterations/`（只增不改） |
| 测试地图 | [TESTING.md](TESTING.md) / [docs/TEST_MAP.md](docs/TEST_MAP.md) |
| 已知限制 | [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md) |
| 能力评审 | [docs/architecture/trace_capability_review_2026-10-27.md](docs/architecture/trace_capability_review_2026-10-27.md) |
