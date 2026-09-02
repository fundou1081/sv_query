# Iteration 102: 缺陷 C + D 修复 — LHS 拼接位置映射 + localparam ternary 常量边

**Metadata**:
- **Iteration #**: 102
- **Task Tree Level**: L1 (缺陷 A-F 修复)
- **Parent Task**: 缺陷修复 (iter_088~100 发现)
- **Created**: 2026-09-02 GMT+8
- **Author**: AI 助手 (方豆 "继续")
- **Outcome**: ✅ 成功 (C/D 修复, 回归测试补齐)

## 🎯 本次目标

修复缺陷 C (LHS 拼接位置映射丢失, 笛卡尔积) 和 D (localparam 常量在
ternary 真分支无驱动边)。

## 📊 当前状态 / 预期结果

- C: `{y_hi, y_lo} = {a, b}` 产生 4 条边 (a→y_hi, a→y_lo, b→y_hi, b→y_lo)
- D: `(a > SAT) ? ZERO : a+b` 真分支 ZERO (localparam) 无常量边

## 🔬 实际结果

### 缺陷 C: assign_extractor._handle_concat_assign (根因)

- 注释声称 "对齐映射 rhs_signals[i] → lhs_elements[i]", 实际是**嵌套循环**
  对每个 LHS 元素遍历全部 RHS 信号 = 笛卡尔积
- 修复: zip(lhs_elements, rhs_signals) 位置对齐; LHS 节点创建保持独立循环
  (RHS 对应位是常量时节点也要存在)
- 验证: {y_hi,y_lo}={a,b} → a→y_hi, b→y_lo (2 边); {y_hi,y_lo}={a,8'd0}
  → a→y_hi (y_lo 常量无边, 正确)

### 缺陷 D: assign_extractor._build_ternary_edge_signals (根因)

- ternary 分支提取 `_extract_arm_signals` 拿到的名字 'ZERO' 会被
  `_filter_compile_time_signal_names` (LocalParameter) 滤掉 → 常量边丢失
  (字面量 8'd255 直接走常量边, 所以 case27 正常)
- 修复: `_resolve_const_value` (module.body.lookupName → sym.value, 如
  ZERO → '8'd0') 提升到函数级:
  1. `_extract_arm_signals` 的 arm key 解析为常量值
  2. **leaf_signals 同步解析** (第一版只改了 arm key, leaf 还是 'ZERO',
     cond_map key 与 leaf 交集失败 → 边仍丢失; 修后两处一致)
- 验证: `(a > SAT_VAL) ? ZERO : a+b` → 8'd0→y DRIVER cond='a > SAT_VAL' ✓

### 回归测试更新

- test_concat_truth.py: +3 (LHS 位置映射精确 + 无笛卡尔积反例)
- test_parameter_filter_truth.py: 节点集 +8'd0; +test_true_branch_constant_edge

### 验证

- T5/T7 truth 12 passed
- 全量 (unit+cli+integration+root, 排除 usage): 1 failed = picorv32 ELK (暂缓) ✓

## 💡 关键发现 / 决策

1. **注释与实现不符是 bug 温床**: C 的注释写着位置映射, 实现是嵌套循环 —
   写 truth 测试时实测发现。
2. **两处解析必须一致**: D 第一版只改 arm key 没改 leaf → 交集失败, 边仍丢 —
   修这类"映射 key 变换"bug 必须同时改所有消费该 key 的地方。

## 📌 状态

- ✅ 缺陷 C 修复 (zip 位置对齐) + 3 回归测试
- ✅ 缺陷 D 修复 (常量值解析) + 2 回归测试
- 下一步: 缺陷 E (indexed part-select 动态索引) / F (generate-if shift)
