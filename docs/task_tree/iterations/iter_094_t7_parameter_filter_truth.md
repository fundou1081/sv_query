# Iteration 094: T7 — parameter/localparam 过滤 1:1 truth

**Metadata**:
- **Iteration #**: 094
- **Task Tree Level**: L3 (Truth 层扩充 T1-T12)
- **Parent Task**: L3_truth_expansion → T7
- **Created**: 2026-09-02 GMT+8
- **Author**: AI 助手 (方豆 "按这个顺序来推进吧")
- **Outcome**: ✅ 成功 (5 passed) + 发现 localparam-in-ternary quirk

## 🎯 本次目标

T7: 为 parameter/localparam 过滤 (#17) 建立反例式 1:1 golden —
参数名绝不出现在信号图中。

## 📊 当前状态 / 预期结果

- 过滤逻辑错 = 污染整个图, 无 golden 保护
- 预期: 反例断言 (参数不在图) + 条件串保留参数名

## 🔬 实际结果

### 新增 fixture golden_dataflow_33_parameter_filter.sv + test_parameter_filter_truth.py (5 测试)

**param_filter (WIDTH/SAT_VAL 参数 + ZERO localparam)**:
- 反例断言: WIDTH/SAT_VAL/ZERO 不在节点集
- 节点集精确: a, b, y, y.ternary_SAT_VAL_a
- 条件串保留参数名: '!(a > SAT_VAL)' (不解析为 8'd255)
- 参数值不泄漏: 8'd255 无常量节点
- ternary 结构精确

### ⚠️ 顺带发现 quirk D: localparam 常量在 ternary 真分支无驱动边

- `assign y = (a > SAT_VAL) ? ZERO : a + b;` — 真分支 ZERO (8'd0) **不产生
  常量边** (只有假分支 a+b 的驱动)
- 对比 case27 的 ternary (8'd255 有常量边) — 可能是 localparam 值解析差异
- 记录待定, 不烘焙进 golden (fixture 注释已说明)

## 💡 关键发现 / 决策

1. 参数过滤正确 (名字/值都不泄漏) — 反例式断言最直接有效。
2. 条件串保留参数名 (非值) 是当前行为 — 1:1 锁定。
3. localparam-in-ternary 常量边缺失 — 候选缺陷, 待方豆定夺。

## 📌 状态

- ✅ test_parameter_filter_truth.py 5 passed (T7 完成)
- ⚠️ quirk D 记录, 待方豆定夺
- 下一步: T8 alias 方向语义
