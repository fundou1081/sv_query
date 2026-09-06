# Iteration 159: 组合数组 receiver + E15 默认参数语义 (缺口收尾)

**Metadata**:
- **Iteration #**: 159
- **Task Tree Level**: L2 (class 对抗 backlog 收尾)
- **Parent Task**: [class_tracing_plan.md](../../architecture/class_tracing_plan.md)
- **Created**: 2026-09-06 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (unit +2; 回归见 commit)

## 🎯 本次目标

方豆 "继续" — class 对抗 backlog 剩余: 组合数组 receiver (E13+E8 组合) +
E15 默认参数语义。

## 🔬 实际结果

### 组合数组 receiver (嵌套内 ElementSelect)

`_expand_nested_class_calls` 的 ElementSelect 分支 (原 continue) → 解析:
value = 外层实例成员 (bus, class 数组) + selector 常量索引 → receiver
`top.p.bus[0]`, class = 成员类型剥 elementType (inner)。
变量索引 (generate/循环) = 动态 → 跳过 (静态限定)。

### E15 默认参数无实参 (语义定案)

p.set() 无实参 → 形参用默认常量 (8'h5) — data 数据源是**常量**, 无信号
可追 → fanin 空 = 合理 (不建假信号源); 常量驱动不展开; 测试锁定不崩 +
无垃圾节点。

### 证据

- 组合数组: fanin(top.p.bus[0].val) = {d}
- E15: build 不崩, fanin(p.data) 空 (常量源), 无 Symbol(...) 垃圾
- unit +2; 回归见 commit

## 📌 状态

- ✅ 组合数组 receiver (静态成员数组 + 常量索引); E15 语义定案 (常量源
  空答合理)
- ✅ class 对抗缺口全清单闭环: E11/E4/E7/E8/E3/E5/E13/E15 + 组合数组
- 动态分派 (virtual/句柄重指向/句柄集合) = 文档标记不建模 (iter_158 注)
