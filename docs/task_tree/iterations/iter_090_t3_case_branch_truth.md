# Iteration 090: T3 — case 多分支条件边 1:1 truth

**Metadata**:
- **Iteration #**: 090
- **Task Tree Level**: L3 (Truth 层扩充 T1-T12)
- **Parent Task**: L3_truth_expansion → T3
- **Created**: 2026-09-02 GMT+8
- **Author**: AI 助手 (方豆 "按这个顺序来推进吧")
- **Outcome**: ✅ 成功 (8 passed)

## 🎯 本次目标

T3: 为 case 多分支条件边 (#7) 建立 1:1 golden —
with_case (普通 4 分支) + nested_case (嵌套复合条件) + if_case_mixed (if+case 混合)。

## 📊 当前状态 / 预期结果

- truth 层无 case 分支条件边锁定
- 预期: 精确 (src, dst, kind, condition) 四元组边集

## 🔬 实际结果

### 新增 test_case_branch_truth.py (8 测试)

**with_case (9_case)**:
- 6 节点精确 (无常量节点); 5 DRIVER 边条件精确
- **锁定字面量归一化行为**: 2'b00 → 'sel == 2'b0', 2'b01 → 'sel == 2'b1'

**nested_case (16_nested_case)**:
- 9 节点精确 (含 8'd0/8'd255); 11 DRIVER 边复合条件
  'sel == 2'b1 && sub_sel == 2'b0' 精确

**if_case_mixed (17_if_case_mixed)**:
- 9 节点精确; 8 DRIVER + 6 CLOCK + 6 RESET 条件精确
  (复位 '!rst_n' / en 分支 / case 分支复合条件)

### 小修
- with_case.y 声明 `output reg` 但分类 PORT_OUT (输出端口优先于 reg) —
  首版断言 REG 错误, 修正为 PORT_OUT (分类器实际行为)

## 💡 关键发现 / 决策

1. **字面量归一化是 case 条件的关键行为**: 2'b00/2'b01 归一化为 2'b0/2'b1 —
   不锁定则改归一化逻辑不会被发现。
2. 复合条件 ('!(!rst_n) && en && mode == ...') 合成正确 — 嵌套控制流语义
   值得 1:1 锁定。
3. 分类器: `output reg` → PORT_OUT (端口优先), 断言 kind 前先实测确认。

## 📌 状态

- ✅ test_case_branch_truth.py 8 passed (T3 完成)
- 下一步: T4 位选 RHS/LHS
