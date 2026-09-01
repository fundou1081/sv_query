# Iteration 097: T10 — generate-if/case 内 wire 1:1 truth

**Metadata**:
- **Iteration #**: 097
- **Task Tree Level**: L3 (Truth 层扩充 T1-T12)
- **Parent Task**: L3_truth_expansion → T10
- **Created**: 2026-09-02 GMT+8
- **Author**: AI 助手 (方豆 "按这个顺序来推进吧")
- **Outcome**: ✅ 成功 (6 passed)

## 🎯 本次目标

T10: 为 generate-if/case 编译期分支选择 (#23/#24) 建立 1:1 golden —
激活分支被提取, 未激活分支绝不出现在图中。

## 📊 当前状态 / 预期结果

- 有条件支持语法 (#23/#24) 的行为边界无锁定
- 预期: 精确节点集 + 边集 + 未激活分支反例断言

## 🔬 实际结果

### 新增 test_generate_if_case_truth.py (6 测试)

**generate_if_demo (30, MODE=1 → gen_adder 激活)**:
- 5 节点精确 (MODE/W 参数不在图)
- 6 边精确; 反例: op2→result 不在 (gen_subtractor 未实例化)

**generate_case_demo (31, SEL=2 → gen_subtractor 激活)**:
- 5 节点精确 (SEL/W 参数不在图)
- 6 边精确; 反例: op1→result 不在 (gen_adder 未实例化)

### 备注
- generate_if_alu (TWO_CYCLE_ALU=0 else 分支) 实测只有 2 条 BIT_SELECT 边,
  **无 DRIVER 边** — shift 赋值 (<< / >>>) 在 generate-if 分支内未提取,
  独立候选缺口 (记录, 待方豆定夺, 不在本次 golden 范围)

## 💡 关键发现 / 决策

1. generate 编译期分支选择实现正确 (激活分支才提取) — 锁定。
2. parameter 驱动分支选择且被过滤 — 与 T7 呼应。
3. generate_if_alu 的 shift-in-generate 无 DRIVER 边 — 新候选缺口, 记录。

## 📌 状态

- ✅ test_generate_if_case_truth.py 6 passed (T10 完成)
- ⚠️ generate_if_alu shift 缺口记录, 待方豆定夺
- 下一步: T11 SVG 布局 golden (非 generate)
