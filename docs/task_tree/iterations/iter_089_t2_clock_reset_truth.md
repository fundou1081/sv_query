# Iteration 089: T2 — always_ff + clock/reset 1:1 truth

**Metadata**:
- **Iteration #**: 089
- **Task Tree Level**: L3 (Truth 层扩充 T1-T12)
- **Parent Task**: L3_truth_expansion → T2
- **Created**: 2026-09-02 GMT+8
- **Author**: AI 助手 (方豆 "按这个顺序来推进吧")
- **Outcome**: ✅ 成功 (9 passed)

## 🎯 本次目标

T2: 为 always_ff + clock/reset (#2) 建立 1:1 golden —
orphan_01 (异步复位 + 时序 ternary) + fsm_demo (case-in-sequential 状态机)。

## 📊 当前状态 / 预期结果

- truth 层无 CLOCK/RESET 边精确结构锁定
- 预期: 精确节点集 + 边集 (含 condition), parameter 过滤反例断言

## 🔬 实际结果

### 新增 test_clock_reset_truth.py (9 测试)

**orphan_01 (always_ff 异步复位 + ternary)**:
- 8 节点精确 (y REG + 5 端口 + 8'd0 CONST + y.ternary_sel OP_TERNARY)
- 11 边精确 (含 condition): CLOCK×2 (!rst_n / !(!rst_n)) + RESET×2 + 3 条件 DRIVER
  + BRANCH_TRUE/FALSE/CONDITION/RESULT
- 分类计数: CLOCK=2 RESET=2 DRIVER=3 BRANCH_*=4

**fsm_demo (case-in-sequential 状态机)**:
- 12 节点精确; parameter IDLE/RUN/DONE/ERR **不在图中** (过滤生效, 反例断言)
- 5 个寄存器都是 REG
- CLOCK 边条件集精确 {'' , IDLE, RUN, DONE, ERR}, 总数 17 (4 输出 × 4 分支 + state_q)
- y_idle case 分支精确: IDLE→2'b1, RUN/DONE/ERR→2'b0 (DRIVER 条件)
- 状态转移: next_state→state_q + start→ternary→next_state

### 小修
- 首版 test_case_branch_drivers 漏过滤 CLOCK 边 (CLOCK 也指向 y_idle) →
  断言集合含 clk 条件边 → 修正为仅 DRIVER 边后全绿 (教训: 目标节点的边
  可能有多 kind, 断言前按 kind 过滤)

## 💡 关键发现 / 决策

1. CLOCK/RESET 边带 condition (每分支一条) — 异步复位场景 CLOCK 边也有
   条件 ('!rst_n' / '!(!rst_n)'), 1:1 锁定必须含 condition。
2. parameter 过滤在 fsm_demo 验证生效 (IDLE..ERR 无节点) — T7 的反例断言
   在这里已初见雏形。
3. 断言目标节点的边时先按 kind 过滤 (CLOCK/DRIVER 可能同目标)。

## 📌 状态

- ✅ test_clock_reset_truth.py 9 passed (T2 完成)
- 下一步: T3 case 多分支条件边
