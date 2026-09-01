# Iteration 093: T6 — function/task 调用 1:1 truth

**Metadata**:
- **Iteration #**: 093
- **Task Tree Level**: L3 (Truth 层扩充 T1-T12)
- **Parent Task**: L3_truth_expansion → T6
- **Created**: 2026-09-02 GMT+8
- **Author**: AI 助手 (方豆 "按这个顺序来推进吧")
- **Outcome**: ✅ 成功 (6 passed)

## 🎯 本次目标

T6: 为 function/task 调用 (#13/#14) 建立 1:1 golden —
function_multi (3 function 组合) + 新 fixture task_call (iter_076 形参映射)。

## 📊 当前状态 / 预期结果

- truth 层无 function/task 调用结构锁定
- 预期: function 调用节点 + 实参驱动边 + task 形参映射真边

## 🔬 实际结果

### 新增 test_function_task_truth.py (6 测试) + fixture golden_dataflow_32_task_call.sv

**function_multi (19_function_multi)**:
- 12 节点精确 (含 function 节点 sat_add/clamp + 内部 x/x[7])
- 10 边精确: 实参 (a/b/c) 驱动 sat_add; sat_add→overflow; clamp→z;
  a/b→y (abs_val 分支); x[7]→x BIT_SELECT; ternary 结构

**task_call (新 fixture 32)**:
- 2 节点精确 (din/dout, task formal 不泄漏)
- 1 边精确: din→dout DRIVER — **iter_076 修复的真边锁定**
- 负断言: 无 EmptyArgument 占位边

### fixture 说明
- task 调用场景在 regression (test_task_function.py) 是内联源码; 为 truth 层
  新增 golden_dataflow_32_task_call.sv 到 golden_mini (既有 fixture 池, 非平行体系)

## 💡 关键发现 / 决策

1. function 调用语义 = 调用结果 function 节点驱动输出 + 实参驱动 function 节点 —
   function 名是图节点 (sat_add/clamp), 不是 inline 展开。
2. task 形参映射 (iter_076 修复) 现在有 1:1 锁定 — 修复不会被静默回归。

## 📌 状态

- ✅ test_function_task_truth.py 6 passed (T6 完成)
- 下一步: T7 parameter/localparam 过滤 (反例式)
