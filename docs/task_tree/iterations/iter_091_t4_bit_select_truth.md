# Iteration 091: T4 — 位选 RHS/LHS 1:1 truth

**Metadata**:
- **Iteration #**: 091
- **Task Tree Level**: L3 (Truth 层扩充 T1-T12)
- **Parent Task**: L3_truth_expansion → T4
- **Created**: 2026-09-02 GMT+8
- **Author**: AI 助手 (方豆 "按这个顺序来推进吧")
- **Outcome**: ✅ 成功 (10 passed)

## 🎯 本次目标

T4: 为位选 RHS/LHS (#8/#9) 建立 1:1 golden —
with_trunc (截断/切片) + array_index (字节切片 + indexed part-select + ternary mux)。

## 📊 当前状态 / 预期结果

- truth 层无位选 BIT_SELECT 回边 / bit_slice 保留锁定
- 预期: 精确节点集 + BIT_SELECT 回边 + slice DRIVER bit_slice + 位选节点 bit_range

## 🔬 实际结果

### 新增 test_bit_select_truth.py (10 测试)

**with_trunc (3_slice)**:
- 7 节点精确 (含 a[15:8] / sum[7:0] 位选节点)
- 2 BIT_SELECT 回边精确; slice DRIVER 边 bit_slice 精确 ('[7:0]' / '[15:8]')
- 位选节点 bit_range 精确

**array_index (25_array_index)**:
- 24 节点精确 (4 字节切片 + part + sum_lo[7:0] + [?:?] + ternary)
- 5 BIT_SELECT 回边精确 (4 字节 + sum_lo)
- 字节驱动边 bus[N:M]→byteN
- **锁定 indexed part-select 当前行为**: `bus[{sel,3'b000} +: 8]` → `bus[?:?]`
  节点 (未解析), DRIVER → part
- ternary mux 结构 (BRANCH_TRUE/FALSE/CONDITION/RESULT)

### 锁定了一个边界行为
- indexed part-select (`+:` 动态索引) 解析为 `bus[?:?]` 占位节点 — 这是
  当前实现的局限 (非错误), 1:1 锁定现状, 将来若改进需更新 golden

## 💡 关键发现 / 决策

1. 位选语义 = BIT_SELECT 回边 (位选节点→base) + slice DRIVER 边 (位选节点→消费者,
   带 bit_slice) + 节点 bit_range — 三者都要锁定。
2. `+:` indexed part-select 动态索引未解析 → `[?:?]` 占位 — 值得单独报告
   (功能缺口, 非本次范围)。

## 📌 状态

- ✅ test_bit_select_truth.py 10 passed (T4 完成)
- 下一步: T5 concat LHS/RHS
