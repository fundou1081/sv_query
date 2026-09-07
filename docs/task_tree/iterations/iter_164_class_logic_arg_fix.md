# Iteration 164: Class 域 P1 修复 — 方法调用 logic 实参 Conversion 壳丢实参

**Metadata**:
- **Iteration #**: 164
- **Task Tree Level**: L1
- **Parent Task**: L1_class_domain_gaps (tasks/L1_class_domain_gaps.md)
- **Created**: 2026-09-06 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (P1 修复; P2 判定为混淆不存在)

## 🎯 本次目标

方豆 "先处理发现的 class 域问题" — iter_163 实证的两个隐患:
- P1: 方法调用实参 logic (4 态) 端口 → 方法展开断 (bit 通)
- P2: unified_tracer 连续 build 状态退化 (疑)

## 📊 当前状态 / 预期结果

- P1 复现 (plain, 无 covergroup): logic din → top.p.addr 不建, fanin 空。
- P2 复现: 同一 tracer build→查询→再 target build 第二次不展开。
- 预期: 根因定位 + 修复 + 回归。

## 🔬 实际结果

**P1 根因 (运行时插桩定位)**: `_parse_invocation_call` 对实参逐项分派:
logic din → bit 形参 (4→2 态) 时 slang 在实参上插隐式
**ExpressionKind.Conversion** 壳 (iter_136 端口同款壳 — 此处调用实参)。
Conversion 无 `.expr` 无 `.symbol` → 守卫
`if not hasattr(expr,'expr') and not is_semantic and "Assignment" not in kind_str:
continue` **静默 continue 丢实参** → call_args=[] (插桩实证: logic → [],
bit → ['din']) → param_map 空 → 方法体成员赋值展开 `continue` (形参无映射
且 d 非 class 成员) → 实例成员节点不建。整链下游 (receiver_id 解析/
internal_drivers/嵌套展开) 无差别, 断点只在实参解析。

**修复** (function_extractor._parse_invocation_call):
- 实参循环顶部剥 Conversion 链 (operand) 再走标准 kind 分派
- Assignment 分支 rhs 同样剥壳 (output/命名实参对称)
- 命名参数分支经 get_signal 已剥 (get_signal 内部处理 Conversion), 不重复

**P2 判定 = 混淆 (不存在)**: iter_163 的 P2 复现 fixture 全是 logic 端口
(covergroup fixture SRC 用 logic) — 干净 bit fixture 复测: 连续
build(无 target) → trace_class_instances → build(target) → 重建 → fanin
全程稳定 (top.p.addr 恒在, fanin 恒通)。P2 = P1 同一现象的错误归因,
**如实修正** (iter_163 文档的 P2 行 + 本迭代记录; unified_tracer 无需改动)。

**测试**: test_class_method_call_logic_arg.py 6 (logic 实参驱动实例属性 /
bit 不回归 / 多参混合 logic+bit / 命名参数 .d(din) logic / module function
logic 入参 / 连续 build 稳定 — P2 复测锁定)。Q4 端到端 fixture 升级为
logic 端口 (原用 bit 规避 — 现为 P1 修复的回归覆盖)。

## 💡 关键发现 / 决策

- **Conversion 壳是系统性模式**: iter_136 (input 端口连接) → iter_164
  (调用实参)。凡是 logic↔bit 宽度/态匹配处 slang 都可能插 Conversion;
  两个提取路径都需剥壳。同类自查: 其他取信号名处 (connection/arg/rhs)
  若依赖 `.symbol`/`.expr` 判语义, 对 Conversion 会静默丢 — 已覆盖的
  是端口连接 + 调用实参; 残留风险点登记 (load/操作数路径可后续扫)。
- **插桩 > 猜测**: 三个探针 (call_args 位置参数打印错→重打; 语义树找不到
  Call 节点→语句不在符号树) 后才用运行时插桩一步定位。诊断纪律验证。
- **如实修正 P2**: 两次独立报告的"状态退化"实为 P1 (logic fixture) 误归因;
  保留 test_sequential_builds_stable 作回归锁定, 防止将来真退化逃逸。
