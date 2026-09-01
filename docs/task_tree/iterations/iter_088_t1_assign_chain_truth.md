# Iteration 088: T1 — assign 链基础数据流 1:1 truth

**Metadata**:
- **Iteration #**: 088
- **Task Tree Level**: L3 (Truth 层扩充 T1-T12)
- **Parent Task**: L3_truth_expansion → T1
- **Created**: 2026-09-02 GMT+8
- **Author**: AI 助手 (方豆 "按这个顺序来推进吧")
- **Outcome**: ✅ 成功 (9 passed) + 发现 2 个真实缺陷 (已记录待定)

## 🎯 本次目标

T1: 为 assign 链基础数据流 (#1/#5) 建立 1:1 golden —
`golden_dataflow_1_op.sv` (纯 assign 二元运算) + `golden_dataflow_5_combined.sv`
(wire 声明链 + assign 位选)。

## 📊 当前状态 / 预期结果

- truth 层无 assign 基础语义的 1:1 锁定
- 预期: 精确节点集 + 边集断言 (集合相等, 多一个节点/边 = 偏离)

## 🔬 实际结果

### 新增 test_assign_chain_truth.py (9 测试)

**simple_op (1_op)**:
- 节点集精确 = {a, b, sum, prod}; a/b PORT_IN, sum/prod PORT_OUT
- 边集精确 = 4 条 DRIVER (a/b→sum, a/b→prod), 总边数 4

**combined (5_combined)**:
- 节点集精确 = {a,b,c,y,sum,prod,prod[15:8]} (7 节点, 含位选节点)
- 边集精确 = 6 条 (4 net-decl DRIVER + prod[15:8]→prod BIT_SELECT + prod[15:8]→y DRIVER)
- net-decl expression 干净 ('a + b' / 'sum * c') — 已锁定
- slice 边 bit_slice='[15:8]' + 位选节点 bit_range 正确 — 已锁定

### ⚠️ 顺带发现 2 个真实缺陷 (未修, 待方豆定夺)

**缺陷 A: assign 边 expression 提取损坏**
- 现象: `assign sum = a + b;` 的 edge.expression = **整份源文件 + \x00 空字节**
  (从文件头到 pyslang null terminator), 不是 'a + b'
- 范围: **所有 assign 语句边** (net-decl `wire x = expr` 路径正常)
- 下游影响: handshake_detector.py:151/381 用 expression 匹配条件, dataflow.py
  输出 driver, viz_data_models.py:174 边标签
- 根因线索: assign_extractor._resolve_rhs_signals → signal_visitor.get_source_text(rhs_expr)
  返回错误 span

**缺陷 B: net-decl wire 显式位宽被忽略**
- 现象: `wire [15:0] sum = a + b;` → 节点 width=(1,0), 声明 [15:0] 被忽略
  (端口 `input [7:0] a` 的 width=(7,0) 正确)
- 范围: net-decl 路径宽度提取
- 影响: width 下游消费 (viz 宽度显示 / width 过滤)

**决策**: 两个缺陷都不纳入本 golden 断言 (不把已知坏行为当 truth 烘焙),
已写进测试文件 docstring。待方豆定夺是否修复 (修复后需补断言)。

## 💡 关键发现 / 决策

1. **truth 层天然是缺陷探测器**: 写 1:1 golden 时实测真实输出, 立即暴露了
   assign expression 和 net-decl width 两个隐藏缺陷 — 这正是扩充 truth 的价值。
2. **集合相等断言 > 存在性断言**: 既有 truth 用 get_edge 存在性, T1 用集合相等
   (多节点/多边 = 失败), 更符合 1:1 精神, 后续 T# 沿用。
3. **缺陷不烘焙进 golden**: 已知坏字段不断言, 修复后补断言 — 避免 golden 变成
   "锁定 bug" 的障碍。

## 📌 状态

- ✅ test_assign_chain_truth.py 9 passed (T1 完成)
- ⚠️ 缺陷 A/B 记录, 待方豆定夺
- 下一步: T2 always_ff + clock/reset
