# Iteration 154: C4 查询层 class kind 收束 + namespace 规则 + 冲突检测 (D5)

**Metadata**:
- **Iteration #**: 154
- **Task Tree Level**: C4 (class 追踪迭代 — 按架构决策 D5)
- **Parent Task**: [class_tracing_plan.md](../../architecture/class_tracing_plan.md)
- **Created**: 2026-09-06 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (unit +3; 回归见 commit)

## 🎯 本次目标

C4: 查询层 class kind 收束 (类型级非数据端点) + namespace 规则 + 冲突检测。

## 🔬 实际结果

### 实证 (隐患确认)

1. **类型级被当数据端点**: fanin(packet.data) = {packet.addr} — 类型级方法体
   DRIVER (iter_075 结构建模) 被数据 fanin 当"模板驱动"答案 (≠ 任何实例
   真实驱动) — D3 矛盾
2. **同名 class 静默丢**: 两文件各定义 packet (成员 addr vs b) → 图只有
   packet.addr, packet.b **静默缺失** — 且 get_classes **按 name 去重**
   在源头杀第二个定义, class_graph_builder 冲突检测永远看不到 → 形同虚设
3. filter 行为: class 类型级在 _filter_by_target 后加入 = 隐式保留 (未定义
   行为, D5 隐患)

### 修复

| # | 内容 | 位置 |
|---|---|---|
| C4-A | 类型级 CLASS_PROPERTY 非数据端点: fanin (主循环 + _find_drivers depth=1) 守卫返回空 — 模板驱动不作实例答案; 实例级 (CLASS_INSTANCE_PROPERTY/REG) 不受影响 | query/signal.py ×2 |
| C4-B | namespace 规则注释: class 类型级在 filter **之后**加入 = 显式保留 (全局定义); 勿移 filter 前 | unified_tracer _step_class |
| C4-C | 冲突检测: class_graph_builder build 同名告警 + 首定义保留; **get_classes 去重改对象身份 (id)** — 同名不同定义暴露给检测 (根因修) | class_graph_builder + semantic_adapter get_classes ×2 |

### 证据

- fanin(packet.data) = [] (类型级); fanin(top.p.addr) = {din} (实例保持)
- 同名 packet: WARNING "同名 class 定义冲突... 保留首定义" + packet.addr 在
  packet.b 不在 (告警可见, 非静默)
- unit +3 (TestClassKindSemantics: 类型级空/实例保持/冲突告警+首保)

## 💡 关键发现

1. **get_classes 按 name 去重 = 静默杀同名定义的源头**: 去重本意是
   Semantic/SyntaxTree 双来源重复 — 应按对象身份 (id), 非 name。按 name
   去重让 C4-C 冲突检测永远不触发 (检测在 class_graph_builder, 但输入已
   被去重)。
2. **类型级 DRIVER (方法体) 保留在图但查询层不消费为数据**: 结构信息
   (定义内依赖) 留可视化/结构查询, 数据答案走实例 — D3 的一致实现。

## 📌 状态

- ✅ C4-A kind 收束 (类型级非数据端点, fanin 双路径守卫)
- ✅ C4-B namespace 规则注释 (类型级 = filter 后显式保留)
- ✅ C4-C 冲突检测 (get_classes 身份去重根因修 + class_graph_builder 告警)
- ✅ unit +3; 全量回归见 commit
- 下一步: C5 (Accuracy Claim hybrid 域转正 — class 追踪域稳定后声明)
