# Iteration 095: T8 — alias 方向语义 1:1 truth

**Metadata**:
- **Iteration #**: 095
- **Task Tree Level**: L3 (Truth 层扩充 T1-T12)
- **Parent Task**: L3_truth_expansion → T8
- **Created**: 2026-09-02 GMT+8
- **Author**: AI 助手 (方豆 "按这个顺序来推进吧")
- **Outcome**: ✅ 成功 (3 passed)

## 🎯 本次目标

T8: 为 alias 方向语义 (#12) 建立 1:1 golden — SV 规范 alias LHS=target, RHS=source,
驱动方向 source → target (方向反是静默错误)。

## 📊 当前状态 / 预期结果

- 无 alias fixture (integration test_aliases.py 用内联源码), 无 1:1 锁定
- 预期: 精确节点集 + 方向边 + 无反向边

## 🔬 实际结果

### 新增 fixture golden_dataflow_34_alias.sv + test_alias_truth.py (3 测试)

**alias_demo (alias x=a; y=b; t=b; z=t)**:
- 6 节点精确 (a, b, t, x, y, z)
- 4 条 DRIVER 边方向精确: a→x, b→y, b→t, t→z (alias 链 b→t→z)
- 无反向边断言 (x→a 等不存在)

### 小修
- 首版 test_no_reverse_edges 用无模块前缀的短名集合 → 永不匹配 (空断言) —
  修正为完整节点 id 交集检查

## 💡 关键发现 / 决策

1. alias 方向实现正确 (source→target) — 实测验证 + 锁定。
2. alias 链 (b→t→z) 传递正确。
3. 教训: 反例断言必须用真实节点 id, 不能用短名 (容易写成永不失败的假断言)。

## 📌 状态

- ✅ test_alias_truth.py 3 passed (T8 完成)
- 下一步: T9 class 成员 DRIVER 边
