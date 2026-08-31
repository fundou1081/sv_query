# Iteration 077: id() 复用非确定模式全仓扫描

**Metadata**:
- **Iteration #**: 077
- **Task Tree Level**: L2
- **Parent Task**: C 组功能缺口修复 (方豆 "一起做" — A+B+C)
- **Created**: 2026-09-01 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 完成 (扫描确认无新增风险, 零代码改动)

## 🎯 本次目标

iter_075 (#41) 关键发现承诺的跟进: "全仓需检查 id(n) 复用模式" —
#41 的 bug 是 Python id 复用导致 walk 的 seen set 误判已访问 (5 次跑 4 次丢节点)。
扫描 src/ 确认是否还有同类非确定源。

## 📊 当前状态 / 预期结果

- 已知: class_graph_builder 的 seen set 已修 (iter_075, 去 seen 保 depth)
- 预期: 找到所有 id() 做 seen/key 的地方, 逐一定性安全 or 有风险

## 🔬 实际结果

### 扫描发现 7 处 id() 模式, 全部安全

| 位置 | 模式 | 判定理由 |
|---|---|---|
| `_common.py:597/661/721` `_extract_base_chain` | 调用内 `visited` 防环 | `cur`/`acur` 每轮被局部变量持有, 无 GC 窗口 |
| `constraint_visitor.py:80-96` | 函数局部 visited | `child_list` 持有所有 child 强引用至函数结束 |
| `base.py get_module_instances` | 函数局部 visited + 树遍历 | 递归栈 + AST 树持有所有节点 |
| `semantic_adapter._genvar_context` | 实例级 id-keyed dict | 同一 AST 树全程存活 (per-build adapter), 无跨 pass 残留 |
| `semantic_adapter._fixed_names` | 同上 | 同上 |
| `controlflow._blocks` | per-command analyzer | 每命令新建, 树存活 |
| `get_modules` seen_ids | 函数局部 | 无跨调用共享 |

### 关键区分 (为什么这些安全而 #41 有 bug)

#41 的 seen set 遍历的是**多个独立语句** (siblings, 彼此无父子引用):
前一条语句处理完不再被引用 → GC → 新语句的对象复用其 id → 误判已访问 → 跳过。

而全仓其余 id() 模式全部作用在**同一棵 AST 树**上:
- root 被 compiler/adapter 持有, 整个分析期间所有节点存活
- 对象不 GC → id 不复用 → seen/key 判定确定

## 💡 关键发现 / 决策

1. **id() 非确定只在"对象集合跨调用变化"时出现** — 判定标准不是"有没有 id()",
   而是"seen set 的生存期 vs 对象集合的生存期"。
2. **per-pass 新建的 adapter/analyzer + AST 树存活 = id-keyed dict 安全**。
3. 已修处 (class_graph_builder) 是唯一越界案例 — 它跨方法体语句遍历。
4. 零代码改动 — 无新增风险, 扫描结论记录即可。

## 📌 状态

- ✅ 扫描完成: 全仓无其他 id() 复用非确定源
- 提交: 仅本迭代记录 (无代码改动)
