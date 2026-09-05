# Iteration 139: 条件控制信号 (en/sel) 从数据 fanin 排除 — iter_138 方案 2

**Metadata**:
- **Iteration #**: 139
- **Task Tree Level**: L2 (准确性审计 → iter_138 拍板实施 / iter_128 同规则扩展)
- **Parent Task**: [signal_graph_accuracy_audit.md](../../architecture/signal_graph_accuracy_audit.md)
- **Created**: 2026-09-05 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (全量回归见 commit)

## 🎯 本次目标

方豆拍板 iter_138 方案 2: "在已经有 condition 记录信号的情况下, 就不需要
在 driver 重复了" — 三态/条件赋值 (三目/case) 的**控制信号** (en/sel) 不
作为数据 fanin 源; 控制关系已存在 DRIVER.condition 字段 (铁律16) +
BRANCH/CASE 条件边, fanin_detailed 仍可查。

## 🔬 实际结果

### 根因 (iter_138 诊断确认)

三态 `sda = en ? data : z`: data→sda **DRIVER/continuous (cond=en)** +
en→ternary 节点 **BRANCH_CONDITION** → BRANCH_RESULT → sda。fanin 主循环
对非 DRIVER/CONNECTION 边 fallthrough 递归 → BRANCH 链被追 → 经
"PORT_IN via CONNECTION → 顶层输入 append" 规则把使能抓进结果 —
i2c 双驱动: en_slave (经实例 PORT_IN→CONNECTION) 混入, en_master
(顶层直接 BRANCH_CONDITION, 递归无 incoming) 缺 — **不对称杂音**。

### 修复 (query/signal.py 主循环)

CLOCK/RESET 守卫 (iter_128) 扩展为条件边族同规则 (不 append 不递归):
BRANCH_CONDITION / BRANCH_TRUE / BRANCH_FALSE / BRANCH_RESULT /
CASE_SELECT / CASE_ITEM / CASE_RESULT。
数据分支本身 (a/b/data) 走各自 DRIVER 边 (cond=sel/en), 不受影响。

### 验证

- i2c 双驱动 (iter_138 场景4): fanin(top.sda) =
  {data_master, data_slave, u_slave.data} — **en 杂音清除** (双侧对称:
  en_master/en_slave 都不进)
- 纯 ternary y=sel?a:b: {a, b} 保持 (sel 不进) — 修复前本就干净, 回归锁定
- case: {a, b, c} 保持 (CASE_* 排除不破坏 case 数据源 — 分支数据走 DRIVER)
- fanin_detailed: a 的 condition='sel' 仍可查 (不丢失控制信息)
- unit +4 (TestInoutTriStateControlExclusion) — 36 passed (A1/A2/A3 文件)
- 受影响子集 1221 passed (unit 全套 + truth + regression)
- 全量主回归 (2026-09-05 实测): **3058 passed / 22 skipped** (3054+4 新;
  唯一 fail [serv] = HOME 重定向 env 假失败, 真实 HOME 通过) — 零代码回归

## 💡 关键发现 / 决策

1. **铁律16 与方案 2 同源**: ENABLE 用 TraceEdge.condition 属性 (非独立边
   类型) — 条件信号进数据结果 = 与 DRIVER 重复 (方豆语), 违反铁律16 精神。
2. **控制边排除是 iter_128 的通用化**: CLOCK/RESET (时序采样) + BRANCH/CASE
   (条件分支) = "非数据驱动关系不进数据 fanin" 的同一规则; 控制信息保留在
   边的 condition 字段与条件边 (fanout include_conditional / fanin_detailed)。
3. **不对称杂音根因链**: BRANCH fallthrough → PORT_IN via CONNECTION append
   规则 → 顶层输入 en 被当外部源 — 排除控制边在源头断链, 比改 PORT_IN
   append 规则更精确 (PORT_IN append 对真数据链仍需要)。

## 📌 状态

- ✅ 条件边族 (BRANCH_*/CASE_*) 不进数据 fanin (CLOCK/RESET 同规则)
- ✅ i2c en 杂音清除 (双侧对称); ternary/case 数据源保持; condition 仍可查
- ✅ unit +4; 受影响子集 1221 passed; 全量回归见 commit
