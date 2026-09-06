# Iteration 158: E5/E13 方法内嵌套调用展开 (隐式 this + 成员 receiver)

**Metadata**:
- **Iteration #**: 158
- **Task Tree Level**: L2 (class 对抗 backlog 逐个修 — E5/E13)
- **Parent Task**: [class_tracing_plan.md](../../architecture/class_tracing_plan.md)
- **Created**: 2026-09-06 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (unit +2; 回归 2011 passed)

## 🎯 本次目标

方豆 "继续做 e5 e13", 提醒 **仅编译期可确定, 动态判定文档标记**。

## 🔬 实际结果

### 实现 (function_extractor, 静态限定)

`_expand_nested_class_calls(method, receiver, class, param_map, ...)`:
- 遍历方法体 (StatementList.body.list → ExpressionStatement.expr) 找 Call
- receiver 编译期确定: 隐式 this (thisClass=None) → 外层 receiver (同类);
  显式成员 (i.set: thisClass NamedValue i, 外层 class 有该成员且 class 型)
  → receiver.i + 成员类型 class
- 实参: 形参名经外层 param_map 传调用点信号 (symbol.name — 曾误取 symbol
  对象 str 产 'Symbol(...)' 垃圾节点, 实测修)
- 递归 (depth≤3 防自/互递归)

**关键坑 (本次 debug)**:
1. `list(StatementList)` 抛异常 (迭代空/异常) → 被外层 except 静默吞 →
   嵌套展开静默不跑 — 删多余 list(body) (body 直接 _walk)
2. StatementList 迭代含 syntax 深层节点干扰 call 定位 — 收敛 attr 遍历
   (expr/stmt/list/statements/body)
3. 实参 symbol 对象 str 垃圾 — 取 symbol.name

### 动态分派文档标记 (方豆提醒, 不建模)

- virtual 方法 override 实际分派 (运行时对象类型未知) → 按声明类型静态
  展开 (默认方法非 virtual = 静态绑定 ✓)
- 句柄运行时重指向 (p.i 被重新 new 到别实例) → 建模静态赋值关系
- 遍历句柄集合动态调用
- 数组成员 receiver (组合数组) → backlog
记录于本文件 + 不建模注释 (代码内)。

### 证据

- E5: fanin(p.data) = {d, p.tmp} (成员链 data=tmp + helper(d) 隐式 this
  展开 tmp←d); fanin(p.tmp) = {d}; 无垃圾节点
- E13: fanin(p.i.val) = {d} (set_inner → i.set 成员 receiver 组合链)
- unit +2 (TestNestedMethodCall); 回归 2011 passed (27 class truth)

## 📌 状态

- ✅ E5/E13 静态部分修 (隐式 this / 成员 receiver / 递归防环)
- ✅ 动态分派文档标记; unit +2; 回归 2011 passed
- backlog: 数组成员 receiver (组合数组) / E15 默认参数 (低价值)
