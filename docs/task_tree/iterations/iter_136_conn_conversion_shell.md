# Iteration 136: input 端口连接 Conversion 剥壳 — 位宽不匹配静默丢失修复

**Metadata**:
- **Iteration #**: 136
- **Task Tree Level**: L2 (准确性审计 → 连接完整性; iter_119 观察闭环)
- **Parent Task**: [signal_graph_accuracy_audit.md](../../architecture/signal_graph_accuracy_audit.md)
- **Created**: 2026-09-05 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (全量回归见 commit)

## 🎯 本次目标

方豆 "挑几个可修正项目" → 自主挑 iter_119 观察 (slang generate-entry 合并
疑似) 复现。复现结果: **不是 slang 合并, 是 input 端口连接静默丢失**。

## 🔬 实际结果

### 复现 (NESTED_PART_SELECT_CONN fixture, iter_119/120 同源)

- 输出侧 (y): 4 条 leaf→切片连接全建 (iter_120 per-entry 修复后 OK)
- 输入侧 (a): **4 条全缺** (u_m2.a → G2[j].u_leaf.a 无 CONNECTION)
  → 连接图断在 u_leaf.a (PORT_IN 无前驱), 顶层 a 不可达
- iter_119 观察 "G2[0] 缺失" = input 侧残留 (当时 y 侧已修, a 侧未被
  任何断言覆盖 — test_leaf_connects_to_slice 只查 y 侧)

### 根因 (adapter 层, silent drop — 违反 AGENTS.md §2)

`SemanticAdapter.get_instance_connection` (semantic_adapter.py): 端口
**位宽 ≠ 连接位宽**时 (leafm `input a` 1 位接 `a[j*2+:2]` 2 位切片),
pyslang 给 input 表达式包 `ExpressionKind.Conversion` 壳 (operand 才是
RangeSelect)。表达式分支只认 NamedValue/Assignment/ElementSelect/
RangeSelect/Concatenation — **无 Conversion 分支** → signal_name 停留
"?" → 整条 conn 静默不 append (无 warning)。output 侧是 Assignment
(left=RangeSelect) 不受影响 → iter_120 后 y 侧 OK / a 侧残留。
**同类风险**: 任何 input 位宽不匹配/类型转换连接都静默丢, 影响面
不止嵌套 generate。

### 修复 (semantic_adapter.get_instance_connection)

表达式链加 Conversion 剥壳分支: operand **链式剥壳** → 交给
`_conn_expr_to_signal` (RangeSelect → `a[1:0]` 命名) → 保连接。
y 侧已按信号名建模 (扩展/截断不特殊处理), input 侧对称一致。

### 验证

- 复现脚本: nested 4 条 input 连接 MISS → **全 OK** (a[1:0]/a[3:2] 按
  entry 正确切片); 单级同恢复
- unit +3 (TestConversionShellInputConn: nested 4 条在 / 单级恢复 /
  adapter 层不再静默丢) — 17 passed
- 受影响子集 75 passed (nested/cordic/cla/genfor/cross_module/accuracy)
- 全量主回归: 见 commit

## 💡 关键发现 / 决策

1. **iter_119 "slang 合并" 观察实为自身 bug**: y 侧 iter_120 修完,
   残留 a 侧缺口未覆盖断言 — 教训: 修复一个方向 (output) 时要把
   对称方向 (input) 一并验证 (两个方向表达式形态不同: Assignment
   vs 直接 expr)。
2. **pyslang 表达式壳**: 宽度/类型不匹配 → Conversion 包裹。凡按
   expr.kind 分支的解析都要剥壳或递归, 否则静默丢连接。
3. fanin 语义不受影响: leaf (真实 assign) 端口仍是粒度停靠 (iter_132),
   本次修的是**结构层连接完整** (L1)。

## 📌 状态

- ✅ 复现 + 根因 (Conversion 壳) + 修复 + unit +3
- ✅ 受影响子集 75 passed; 全量回归见 commit
