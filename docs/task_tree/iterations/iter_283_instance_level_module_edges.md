# Iteration 283: `visualize module` / `arch` 换实例级边推导（PLAN P1.1）

**Metadata**:
- **Iteration #**: 283
- **Task Tree Level**: L2（[L1_view_layer_single_namespace](../tasks/L1_view_layer_single_namespace.md) / PLAN `P1.1`）
- **Created**: 2026-10-25 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "嗯，继续做"）
- **Outcome**: ✅ 完成（边来自真实跨实例网络；旧 MIG 启发式函数删除；2330 passed）

## 🎯 目标

`visualize module` / `arch` 的 L2 边一直走 `extract_module_edges_from_mig`：
把 MIG 的 `inst_port → module_type.port` 按"同模块类型 + 同端口名"分组，
组内两两连边。这是双命名空间时代的启发式——**多实例会误连**（两个 fifo 的 `data_i`
即使接在不同网络上也连起来），且不随真实接线变化。

本迭代改为**实例级图**推导，作为 P1.2（删 MIG 映射）的前置。

## 🔧 新算法（`extract_module_edges_from_graph`）

| 来源 | 判据 |
|---|---|
| ① 直接跨实例边 | 图边两端归属**不同实例**（CONNECTION / DRIVER） |
| ② 经父级网络 | 同一条网络节点（owner 不在 in-scope 实例内，且不是 CONST 字面量）连接两个实例端点 |

- **owner 判定**：节点 id 按 `.` 逐段回退，最长命中 `instances`（generate 路径也能命中）
- **去重**：`(src_inst, dst_inst, port_src, port_dst)`
- **广播网络上限**：每个网络最多 4 对（clk/rst 连 N 个实例 → N² 噪声）
- **常量过滤**：`0` / `1'b0` 这类 CONST 不是网络（首版曾产生 `sa1 → lp1 | net 0` 假边）
- **输出字段不变**：`src/dst/src_instance/dst_instance/internal/port/port_src/port_dst/width`

## 🐛 实现中抓到的两个问题

| # | 问题 | 现象 |
|---|---|---|
| 1 | 只用"直接跨实例边" | `minimal_3module` 只剩 0 条（实例间经 top wire 相连，两端 owner 不同但中间是父级网络）→ 补 ② 两跳网络路径 |
| 2 | 常量节点被当网络 | 出现 `sa1 → lp1 | net 0` 假边 → 过滤 `NodeKind.CONST` |

## 📊 效果（同一 fixture）

| fixture | 旧 MIG 启发式 | 新实例级图 |
|---|---|---|
| minimal_3module（3 实例） | 0（strict_uart 场景） | **7**（sa1↔la1/lp1 真实端口对） |
| scheduler_minimal（7 实例） | — | **52**（共享 clk/rst + 数据网络） |
| arch_test_top（5 实例） | 3 | **11**（含 direct_in/q 真实端口） |
| arch_deep_top（11 实例 / 6 层） | 7 | **65**（每层父子端口连接） |

> 边数变多是**预期**：旧值按"同类型同名端口"去重（把不同网络合并），
> 新值每条真实网络一对。`arch` 的 `--summary` 已改为"边数 > 0 + 出现真实端口名"。

## 🔧 删除与替换

| 位置 | 变更 |
|---|---|
| `module_extractor.py` | 删 `extract_module_edges_from_mig`，新增 `extract_module_edges_from_graph` |
| `cli/view/visualize_module.py` | 传 `tracer.get_graph()`，不再读 `_module_graph` |
| `cli/view/arch.py` | 同上；`--no-mig` 仍表示"不生成 L2 边"（向后兼容） |
| `tools/benchmark/run_benchmark.py` | L4 改用 graph-based（否则 import 失败） |
| `sim/tests/unit/test_pr4_visualize_l2.py` | 重写：真实图 + minimal_3module；含 CONST-网络守卫、确定性、`--no-mig` |
| `sim/tests/cli/test_arch.py` | 期望从"精确旧值"改为"边数 > 0 + 真实端口名" |

## ✅ 验证

| 验证 | 结果 |
|---|---|
| 全量门禁 | ✅ **2330 passed / 0 failed** |
| L2 专项测试 | ✅ 14 passed（含 8 个图推导用例） |
| arch 测试 | ✅ 20 passed |
| 真实项目冒烟 | `arch -f verilog-axi.f -t axi_crossbar` → 2 实例 / 2 边 / 24.5s |

## 🔗 相关

- 计划: [PLAN.md P1.1](../../../PLAN.md)
- 连通层收口: [iter_276](iter_276_clean_single_namespace.md) / [iter_277](iter_277_remove_self_mapping.md)
- 下一步: P1.2 删 MIG 映射
