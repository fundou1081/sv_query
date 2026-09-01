# Iteration 092: T5 — concat RHS 1:1 truth

**Metadata**:
- **Iteration #**: 092
- **Task Tree Level**: L3 (Truth 层扩充 T1-T12)
- **Parent Task**: L3_truth_expansion → T5
- **Created**: 2026-09-02 GMT+8
- **Author**: AI 助手 (方豆 "按这个顺序来推进吧")
- **Outcome**: ✅ 成功 (3 passed) + 发现 LHS 拼接 bug (记录待定)

## 🎯 本次目标

T5: 为 concat RHS (#10) 建立 1:1 golden — golden_dataflow_4_concat
(`assign y = {a, b}`)。

## 📊 当前状态 / 预期结果

- truth 层无拼接语义锁定
- 预期: 精确节点集 + 边集 (拼接操作数都驱动目标, 无跨边)

## 🔬 实际结果

### 新增 test_concat_truth.py (3 测试)

**with_concat (4_concat)**:
- 3 节点精确 (a, b PORT_IN, y PORT_OUT)
- 2 条 DRIVER 边精确 (a→y, b→y)
- 负断言: 总边数 = 2 (无跨目标/跨 kind 多余边)

### ⚠️ 顺带发现缺陷 C: LHS 拼接位置映射丢失

实测 `assign {y_hi, y_lo} = {a, b}`:
- 预期: a→y_hi, b→y_lo (位置对应)
- 实际: **笛卡尔积 4 条边** (a→y_hi, a→y_lo, b→y_hi, b→y_lo)
- EXTRACTION_COVERAGE 标 #11 LHS concat "完整支持" 与实际不符
- 决策: 不烘焙进 golden; 待方豆定夺 (修 extractor 或接受现状)

## 💡 关键发现 / 决策

1. RHS 拼接语义正确 (操作数→目标, 无跨边) — 锁定。
2. LHS 拼接 (destructuring) 位置映射丢失 — 真实缺陷, EXTRACTION_COVERAGE
   文档与实现不符 (文档该修 or 实现该修)。

## 📌 状态

- ✅ test_concat_truth.py 3 passed (T5 完成)
- ⚠️ 缺陷 C 记录, 待方豆定夺
- 下一步: T6 function/task 调用 (28_func_bitmix 已摸底)
