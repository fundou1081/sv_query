# Iteration 064: 测试写法修正 — AST 断言升级为行为断言

**Metadata**:
- **Iteration #**: 064
- **Task Tree Level**: L2
- **Parent Task**: iter_062/063 测试质量改进
- **Created**: 2026-08-29 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (行为断言补齐, 772 passed)

## 🎯 本次目标

方豆质疑: "测试用例的写法有问题? 都只检验 semantic ast 结果" —
审视 iter_062 新增测试, 把纯 AST 断言升级为**行为断言** (铁律13: 先推导行为金标准)。

## 📊 当前状态 / 预期结果

- 4 个新测试文件, 部分只断言"节点存在" (AST 解析结果)
- 预期: 每个域补行为断言 (边/查询/分析输出)

## 🔬 实际结果

### 断言类型盘点 (审视结论)

| 文件 | 原断言类型 | 行为缺失 |
|---|---|---|
| test_module_synth_advanced | 混合 (5 个 DRIVER 边断言 + 节点) | ✅ 已含行为 |
| test_constraint_advanced | **几乎全 AST 节点断言** (无一条边断言) | 🔴 约束真实行为 = CONSTRAINS 边 |
| test_covergroup_advanced | 全 AST 结构断言 (coverpoint/bins 字段) | 🔴 covergroup 行为 = analyzer 缺口检测 |
| test_sva_advanced | 部分 (signals 提取) | 🟡 SVA 行为 = signal_refs 索引查询 |

### 行为断言补齐

1. **constraint (6 处)**: 每个测试加 `_assert_constrains` (CONSTRAINS 边断言):
   - soft → len/prio; dist → val; randc → mode; solve → a/b/c/d;
     嵌套 foreach → m; this.x → this.x 节点
2. **sva (2 处)**: 系统函数测试加 signal_refs 索引 + get_assertions_for_signal
   查询断言; 无界范围测试加反查断言
3. **covergroup (2 处)**: 新增 TestCovergroupBehavior — CovergroupAnalyzer 联动
   (iff coverpoint / transition bins 参与覆盖缺口检测)

### 验证

- 4 个测试文件: 7+7+11+9 = **34 passed** (原 32 + 2 行为测试)
- regression 全量: **772 passed** + 2 failed (pre-existing) / ruff 全过

## 💡 关键发现 / 关键技术 / 决策

1. **方豆的质疑准确**: constraint/covergroup 测试确实只验证了"pyslang 接受 +
   提取器产出节点" (AST 层), 没验证"分析行为" (约束→变量边 / 覆盖缺口 /
   信号关联)。AST 断言只能证明"解析不崩", 不能证明"分析正确"。
2. **各域的行为金标准不同**:
   - module → DRIVER 边 (信号谁驱动)
   - constraint → CONSTRAINS 边 (约束块约束谁)
   - sva → signal_refs (断言关联哪些信号)
   - covergroup → analyzer 缺口 (覆盖完整性)
   补测试必须按**各自域的行为语义**断言, 不是统一格式。
3. **测试写法原则 (沉淀)**: 语法覆盖测试 = AST 断言 (验证解析) **+** 行为断言
   (验证分析)。两者缺一不可 — 前者防语法回归, 后者防语义回归。
