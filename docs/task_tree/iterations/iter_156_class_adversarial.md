# Iteration 156: class 对抗测试 — 19 场景暴露问题 + E11/E4 修复

**Metadata**:
- **Iteration #**: 156
- **Task Tree Level**: L2 (对抗验证 — C1~C4 后 class 域找问题)
- **Parent Task**: [class_tracing_plan.md](../../architecture/class_tracing_plan.md)
- **Created**: 2026-09-06 GMT+8
- **Author**: AI 助手
- **Outcome**: ⚠️ 部分 (12 场景通过 + 2 真 bug 修复 + 5 缺口登记)

## 🎯 本次目标

方豆 "构造极端测试用例, 找出 class 可能出现的问题 (含提取不正确)"。

## 🔬 实际结果

### 19 对抗场景结果

**✅ 通过 (12)**: E1 多实例隔离 (p1/p2 fanin 各自) / E2 方法内成员交叉
(data=addr+d) / E6 条件方法体 / E9 package class / E10 命名参数 / E14 位选
rhs / E16 solve-before 约束提取 (trace_constraints 含 a/b) / E17 空类 /
E18 实例名==类名 / E19 两实例各自调 / (E12 类型级 fanin 空 = C4 设计)

**❌ 修复 2 真 bug**:

| # | 场景 | 问题 | 修复 |
|---|---|---|---|
| E11 | module 有同名 function `set` + class 方法 set | module 定义优先 → class 方法链断 (fanin 空) | receiver_class_name 存在时**优先 class 方法**查找 (thisClass 明确) |
| E4 | `assign out = p.get()` (return data) | 建假节点 `top.get`, fanin(out)={top.get} — class 函数返回未映射 | class 函数返回 = internal_drivers[func_name] (return 表达式) → receiver 成员 (receiver.data); module 隐式返回假节点跳过 (not receiver_id) |

**📋 缺口登记 (5, C1 扩展 backlog)**:

| # | 场景 | 缺口 |
|---|---|---|
| E3 | p1.copy(p2): data=other.data (跨实例成员参数) | rhs 是成员引用 (other.data) — 需参数 class 型映射 |
| E5/E13 | 方法内调方法 (set 调 helper / p.set_inner 调 i.set) + 方法内成员链 (data=tmp) | 方法体内嵌套调用未展开; rhs 成员 (tmp) 非形参被 skip |
| E7 | 继承 (sub_packet extends packet, p.set 在父类) | _find_class_method 需沿 extends 链 |
| E8 | class 数组实例 arr[0].set | receiver 是数组元素 (ElementSelect) 未解析 |
| E15 | 默认参数无实参 p.set() | param_map 无实参 → 默认值未用 |

## 📌 状态

- ✅ E11 (优先序) + E4 (函数返回) 修复; module 函数路径不回归
- 🗒️ E3/E5/E7/E8/E13/E15 = class 方法调用扩展 backlog (CURRENT_TODO 登记)
- 回归见 commit; 固化对抗测试 (通过场景锁定 + E11/E4 回归) 待加
