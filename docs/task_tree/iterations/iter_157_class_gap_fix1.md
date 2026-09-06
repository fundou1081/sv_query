# Iteration 157: class 方法缺口修复轮 1 — E7 继承 / E8 数组 / E3 跨实例参数

**Metadata**:
- **Iteration #**: 157
- **Task Tree Level**: L2 (class 对抗 backlog 逐个修)
- **Parent Task**: [class_tracing_plan.md](../../architecture/class_tracing_plan.md)
- **Created**: 2026-09-06 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (unit +3; 回归 2008 passed)

## 🎯 本次目标

方豆 "先 commit 然后逐个修" — iter_156 对抗 backlog 缺口逐个修 (本轮 E7/E8/E3)。

## 🔬 实际结果

| # | 缺口 | 修法 | 证据 |
|---|---|---|---|
| **E7** 继承方法 | `_find_class_method` 沿 **extends 链递归父类** (baseClass.name / syntax extendsClause; name→ClassSymbol map; seen 防环) | sub_packet 实例调父 set → fanin(p.data)={d} |
| **E8** class 数组 receiver | thisClass 为 **ElementSelect** (arr[0]) → value.symbol + selector 常量 → receiver_id `top.arr[0]`; 类型剥 elementType → class | fanin(arr[0].data)={d0} / arr[1]={d1} 元素隔离 |
| **E3** 跨实例成员参数 | 成员展开 rhs 含 "." (other.data): 头是 class 型形参 → 实参替换 (src=top.p2.data) | fanin(p1.data)={p2.data, d} 链到底 |

**遗留登记 (需隐式 this / 低价值)**:
- E5/E13 方法内嵌套调用 (helper(d) / i.set): 隐式 this 调用 thisClass 为空
  → 需外层 receiver 传递机制 (架构级专项)
- E15 默认参数无实参 (p.set()): 默认值常量驱动 — 低价值边缘

## 📌 状态

- ✅ E7/E8/E3 修 (unit +3 固化); 回归 2008 passed / 25 class truth
- 🗒️ 遗留: E5/E13 (隐式 this 专项) / E15 (低价值)
