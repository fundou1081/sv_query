# Iteration 099: T12 — trace 查询精确 driver 集 1:1 truth

**Metadata**:
- **Iteration #**: 099
- **Task Tree Level**: L3 (Truth 层扩充 T1-T12)
- **Parent Task**: L3_truth_expansion → T12 (最后一项)
- **Created**: 2026-09-02 GMT+8
- **Author**: AI 助手 (方豆 "按这个顺序来推进吧")
- **Outcome**: ✅ 成功 (8 passed) — **T1-T12 全部完成**

## 🎯 本次目标

T12: 为 trace 查询层 (L3 query) 建立 1:1 golden — "谁驱动这个信号" 的
**精确 driver/load 集** (现有 test_fan_query 是 ≥N 下界, 非精确)。

## 📊 当前状态 / 预期结果

- 核心产品承诺 (精确驱动者) 无精确 golden
- 预期: fanin/fanout 精确集合断言

## 🔬 实际结果

### 新增 test_query_truth.py (8 测试)

**combined (5_combined)**:
- fanin(y) 精确 = {prod[15:8]} (8'd128 常量无节点)
- fanin(sum) 精确 = {a, b}
- fanout(a) 精确 = {sum, prod} (链透传)
- 位选边界: prod[15:8] 无 DRIVER 驱动 (BIT_SELECT 回边不进 fanin) — 深度语义锁定
- 不透传: fanin(y) 不含 prod/sum

**with_case (9_case)**:
- fanin(y) 精确 = {a, b, c, d} (case 全分支源去重)
- sel 不在 y 的驱动集 (选择信号非数据源)
- fanin(sel) = {} (输入端口无驱动)

## 💡 关键发现 / 决策

1. fanin 默认深度 = 直接 DRIVER 驱动 (不透传中间 wire), 位选节点无驱动源 —
   这些语义现在被精确锁定。
2. "谁驱动这个信号" 首次有精确 golden — 查询层不再裸奔。

## 📌 状态

- ✅ test_query_truth.py 8 passed (T12 完成)
- 🎉 **T1-T12 全部完成**: 12 文件 + 5 fixture, truth 层 32 → 112 测试
- 汇总: 见 iter_100 (truth 层扩充收尾)
