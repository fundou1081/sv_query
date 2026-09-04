# Iteration 126: 准确性审计 A1/A2 修复 — 自动单 top target (CLI 入口) + 总线位查询提升

**Metadata**:
- **Iteration #**: 126
- **Task Tree Level**: L2 (signal graph 准确性审计 → 修复)
- **Parent Task**: [signal_graph_accuracy_audit.md](../../architecture/signal_graph_accuracy_audit.md)
- **Created**: 2026-09-03 GMT+8
- **Updated**: 2026-09-04 (A1 收窄为 CLI 入口 opt-in — 见决策 3)
- **Author**: AI 助手
- **Outcome**: ✅ 成功

## 🎯 本次目标

按审计清单修 A1 (无 target 盲区) 与 A2 (总线直连位查询空答)。

## 🔬 实际结果

### A1: 无 target_module → generate 嵌套实例内部缺失 (严重)

- **第一版**: `unified_tracer.build_graph` 无条件自动单 top target → 全量回归
  **8 失败** (cross_module_tracking ×3 / boundary parameterized_module /
  module_synth defparam / advanced_syntax time_function / stats_filelist /
  …)。
- **根因 (回归)**: 库 API `build_graph()` 无 target 的**类型级多模块契约**被这些
  测试锁定 — mixed-namespace: `top.u_tb.clk` (实例端口) 与 `tb.clk_out`
  (类型级内部驱动) 并存, 是既有 API 语义, 不是 bug。
- **定稿**: 自动 target 只做**用户入口**: `build_graph` 新增
  `auto_target_single_top: bool = False` 参数 (默认关 = 库契约不变);
  CLI 所有 visualize 子命令共用入口 `build_viz_tracer`
  (`src/cli/_viz_common.py`) 在无 `--module` 时传
  `auto_target_single_top=True`。单 top 自动聚焦; 多 top 库保持全图。
- **证据**: cordic fixture CLI 无 module 建图 365→**542 节点**, 实例内部真实
  assign 恢复 (`cordic.genblk1[0].U.x_shifter.D` 等出现; 验证: run_cli.py
  visualize dataflow → 667 SVG rects, genblk1[0].U.* 节点存在)。
- **澄清**: iter_113-120 已让**直接** generate 实例 (leaf 在 top 内 generate-for)
  无 target 也有实例路径; A1 flag 补的是**嵌套实例内部真实 assign**
  (cordic 型: top→genblk1[i].U→x_shifter 三层)。第一版测试
  `test_generate_internal_present_without_target` 断言的是输出端口
  self-loop DRIVER 标记 (s==d), 默认关闭也绿 — 弱断言掩盖修复;
  已重写为断言**非自环** a→y 真实驱动 (见决策 4)。

### A2: 子模块输出总线直连顶层位 → 位查询空答 (中)

诊断: 纯总线直连 (sub .y(y), assign y=a) 无 per-bit 逻辑 → **无位节点**;
位查询直接空。修复 (`query/signal.py::_trace_drivers_recursive`):
- 位节点不存在 (带 [i] 后缀) → 提升到父总线 (总线粒度)
- 位节点存在但无 incoming 驱动 → 沿 BIT_SELECT 出边提升到父总线
- 结果: top.y[3] fanin `[] → ['top.u_sub.y']` (非空且方向正确); 有 per-bit
  逻辑场景 (xor 风格) 位查询语义不变 (a,b 直达)
- 粒度说明: 总线粒度结果, 位对位折算列后续项 (审计文档)

### 验证

- 新 unit 5 (test_accuracy_a1_a2: A1 默认库契约保留 / flag 开启真实驱动 /
  flag 命名空间前缀; A2 总线位非空 / per-bit 场景不变)
- 全量回归: **2913 passed / 0 failed / 0 skipped** (8 处恢复 + 无新破坏)

## 💡 关键发现 / 决策

1. A1 自动 target 仅限**单 top**: 多 top 库 (库文件) 保持旧全图语义 — 用户显式
   --module 才过滤; 避免"自动首 top 丢弃其他 top"的隐性回归。
2. A2 位粒度缺失的两种形态 (无位节点 / 有节点无驱动) 需分别处理; 查询层补
   提升是正确位置 (图本身无 per-bit 信息可补 — 纯总线无位逻辑)。
3. **默认开启自动 target = 破坏库 API 契约**: "无 target 全模块类型级图" 是
   既有语义 (cross_module/boundary 等金标准测试), 不是 bug。用户价值在
   CLI 设计视图 (用户看"整个设计"期望实例级内部), 故 opt-in + CLI 入口启用
   = 库稳定 + 用户收益两得。8 个回归测试因此恢复原状不动。
4. **DRIVER self-loop 标记会污染"内部驱动存在"断言**: 输出端口节点自带
   s==d DRIVER (设计标记, [FIX 2026-07-08]), 断言实例内部驱动必须排除
   自环 (s != d), 否则弱断言永远绿、掩盖真实缺失。

## 📌 状态

- ✅ A1 (CLI 入口 opt-in) / A2 修复 + unit 5; 全量回归 2913 passed
- A3 (端口自环计入源) + 待验证候选 (inout/struct/interface/时钟域) 仍在审计清单
