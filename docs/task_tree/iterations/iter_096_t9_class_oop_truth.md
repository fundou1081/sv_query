# Iteration 096: T9 — class OOP 1:1 truth

**Metadata**:
- **Iteration #**: 096
- **Task Tree Level**: L3 (Truth 层扩充 T1-T12)
- **Parent Task**: L3_truth_expansion → T9
- **Created**: 2026-09-02 GMT+8
- **Author**: AI 助手 (方豆 "按这个顺序来推进吧")
- **Outcome**: ✅ 成功 (4 passed)

## 🎯 本次目标

T9: 为 class (#16) 建立 1:1 golden — class 定义/实例化/方法体赋值 (C 组计划
遗留项, iter_075 修复过)。

## 📊 当前状态 / 预期结果

- 无 class fixture (regression 用内联源码), 无 1:1 锁定
- 预期: CLASS/PROPERTY/INSTANCE 节点 + IS_INSTANCE_OF/CONSTRAINS/DRIVER 边

## 🔬 实际结果

### 新增 fixture golden_dataflow_35_class_oop.sv + test_class_oop_truth.py (4 测试)

**packet 类 (成员 addr/data + task set_addr) + top 实例化**:
- 5 节点精确: packet (CLASS) / packet.addr, packet.data (CLASS_PROPERTY)
  / top.pkt (CLASS_INSTANCE) / top.din
- 4 边精确: CONSTRAINS ×2 (类→成员) + IS_INSTANCE_OF (new()) +
  packet.addr→packet.data DRIVER (**iter_075 方法体赋值锁定**)
- 节点 kind 精确断言

### 说明
- gap 分析里我写 "cva6_alu_pattern" 是错的 (该 fixture 无 class) —
  实际用新 fixture 35 (class 定义 + 实例化 + 方法体)

## 💡 关键发现 / 决策

1. class 三件套 (定义/实例化/方法体赋值) 语义现在有 1:1 锁定。
2. iter_075 修复 (方法体成员 DRIVER 边) 有了 golden 保护。
3. 教训: gap 分析中的 fixture 候选必须实测确认 (cva6_alu_pattern 记错)。

## 📌 状态

- ✅ test_class_oop_truth.py 4 passed (T9 完成)
- 下一步: T10 generate-if/case 内 wire
