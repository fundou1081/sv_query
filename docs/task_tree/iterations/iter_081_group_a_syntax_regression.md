# Iteration 081: A 组完成 — 主路径语法独立 regression (10 文件 +42 测试)

**Metadata**:
- **Iteration #**: 081
- **Task Tree Level**: L1
- **Parent Task**: Test_Assets_ABC → A 主路径语法独立 regression
- **Created**: 2026-09-01 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (A 组 10 文件 42 测试, regression 766→808)

## 🎯 本次目标

A 组: 补主路径语法独立 regression 行为断言 (对齐 constraint/covergroup 密度)。
方豆 "先记录 A B C, 我们逐个做" → 从 A 开始。

## 📊 当前状态 / 预期结果

- assign/always_comb/wire/alias/三元/parameter/localparam/genvar-for/net_decl/latch
  之前靠 integration 顺带测, 无独立 regression 行为断言
- 预期: 每语法 ≥3 测试 (正例边断言 + 反例 + 有效性), 全部全绿

## 🔬 实际结果

### 新增 10 文件 / 42 测试 (全部全绿, ruff clean)

| 文件 | 测试数 | 关键断言 |
|---|---|---|
| test_assign_continuous | 6 | a→y / a&b→y / 向量 / RHS 位选 a[2]→y / 多 assign 独立 / 常量无边 |
| test_always_comb | 5 | 简单 / if-else (条件+常量) / case 分支 / 多语句中间变量链 / 常量无边 |
| test_wire_top | 5 | wire w=a→a→w / 向量 / 表达式 / generate-for 内 / 常量无边 |
| test_alias | 3 | wire alias a→y / 多目标 / **logic alias 编译报错 (CompilationError)** |
| test_ternary | 4 | 简单 (a,b→y + s→ternary_s) / 嵌套 2 层 / always_comb 内 / 常量分支 |
| test_parameter | 4 | parameter/localparam 不产生节点 / 作位宽正常 / RHS 编译期 |
| test_genvar_for | 4 | generate-for wire a→w / genvar 非信号 / 内实例化 / 索引位选 |
| test_net_decl | 5 | logic+assign / wire+assign / 纯声明无入边 / 向量 / 声明即赋值 |
| test_always_latch | 3 | 简单 / if 无 else / 常量无边 |
| test_concat_lhs | 3 | LHS 拼接 x→{y1,y2} / RHS 拼接 a,b→y / 混合 |

### 关键发现 (探针实证, 修正断言口径)

1. **wire y = a 是 Redefinition 冲突** (端口已声明) — fixture 必须用内部信号
   `wire w = a; assign y = w;`
2. **alias 只用于 net**: `alias y = a` 对 logic 变量是非法 SV (pyslang strict 报
   "not a net") — 正例用 wire, 反例锁定 CompilationError
3. **三元条件节点**: s → `y.ternary_s` → y (条件边), 断言需排除 .ternary_s 内部节点
4. **LHS 拼接**: x → `top.{y1, y2}` 拼接节点 (非 x→y1/y2 分开)
5. **RHS 位选**: a[2] → y (位选节点驱动, 非 base a)

### 有效性验证

- revert test_assign_continuous 断言 (get_edge→None) → 测试 FAILED → 恢复 6 passed
  (断言真实绑定修复)

### 回归

- regression 全量: **766 → 808 passed** (+42, 13.9s)
- ruff: 全过 (修了 B017 盲断言 + W292)

## 💡 关键发现 / 决策

1. **fixture 合法性是行为断言的第一道坎**: 3 处探针发现 fixture 本身非法
   (wire 重定义 / alias 用于 logic) — 先探针实际行为再写断言, 避免"为过测试改断言"
   或"断言错的 fixture"。
2. **workflow 并行写测试失败** (9 subagent 全 null) — 改主 agent 直接写,
   探针驱动, 更可靠 (10 文件 ~30min)。subagent 写测试文件方案存档待排查。

## 📌 状态

- ✅ A 组完成 (10 文件 42 测试, regression 808 passed)
- 下一步: B 组 (修 integration 14 pre-existing 失败)
- 提交: 10 测试文件 + TEST_MAP 统计 + 本记录
