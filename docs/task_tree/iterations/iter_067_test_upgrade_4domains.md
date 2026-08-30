# Iteration 067: 4 域测试统一升级 — AST 断言 → 行为断言

**Metadata**:
- **Iteration #**: 067
- **Task Tree Level**: L2
- **Parent Task**: 测试质量升级 (方豆指示: "把你看到其他测试用例, 统一升级一下, 更严格")
- **Created**: 2026-08-29 GMT+8
- **Author**: AI 助手 (4 个并行 subagent 执行)
- **Outcome**: ✅ 成功 (14 个文件升级, 103 测试更严格, 0 回归)

## 🎯 本次目标

方豆: "把你看到其他测试用例, 统一升级一下, 更严格" — 把 iter_064 发现的
纯 AST 断言测试升级为含行为断言的严格测试。

## 📊 当前状态 / 预期结果

盘点出 26 个 ⚠️ 纯 AST 文件 (行为断言缺失)。派 4 个并行 subagent 按域升级。

## 🔬 实际结果

### 升级清单 (14 文件, 103 测试)

| 域 | 文件 | 行为断言模式 |
|---|---|---|
| constraint | test_constraint_derivative (7) | CONSTRAINS 边 (约束块→变量); solve_before 反证无 CONSTRAINS 边 |
| covergroup | test_covergroup / _enhanced / _extraction (13→22) | CovergroupInfo 结构化字段 (name/clock/bins.kind/values/bin_type/iff) + CovergroupAnalyzer 缺口检测 (missing_cross/missing_illegal_bins) |
| sva | test_sva / _timing / _timing_enhanced (11) | SVAExtractor 结构化字段 (signals/operators/clock/message) + signal_refs 索引 + get_assertions_for_signal 反查 |
| module | test_rhs_syntax (28) / test_controlflow (11) / test_bit_select_in_always (10) / test_typedef / test_concat_multiple / test_replication_fix / test_case_multi_branch_v2 (63) | DRIVER 边 (get_edge) + edge.condition 条件断言 + assign_type 验证 |

### 关键决策与发现

1. **各域行为金标准不同** (与 iter_064 一致):
   module→DRIVER 边 / constraint→CONSTRAINS 边 / sva→signal_refs /
   covergroup→analyzer 缺口
2. **subagent 探针先于断言**: solve_before 不产生 CONSTRAINS 边是设计选择
   (求解顺序声明, 非值约束) — 用 assertNotIn 反证而非硬塞
3. **不硬断言未实现的提取器能力**: goto repetition [->2] 等不单独记录为
   timing_op (实测事实) — 断言聚焦已实现部分 (信号/##1/clock)
4. **工具缺口记录**: replication 无 a→y 直接边 (表达式粒度建边); enum 标签
   CaseTypeMismatch — 记录不强制
5. **文档纪律**: 2 个 subagent 违规改了 CURRENT_TODO/overview (内容合理但
   日期错/信息滞后), 已修正; subagent 不应擅自改项目主文档

### 验证

- 14 个升级文件: **103 测试全过** (constraint 7 + covergroup 22 + sva 11 + module 63)
- regression 全量: **781 passed** + 2 failed (pre-existing: cross_module_connection
  + opentitan_aes_sub_bytes, stash 确认与本次无关)
- ruff: 全过 (修 1 处 subagent 遗留 F841)

## 💡 关键发现 / 关键技术 / 决策

1. **并行 subagent 升级测试是可行的**: 4 域并行, 每域明确的文件清单 + 行为
   金标准 + 验证要求, 产出质量可接受 (103 测试全过)。
2. **subagent 需要更强的文档纪律**: 2 个 agent 动了 CURRENT_TODO/overview
   (我的职责范围), 且内容有错误 (日期/编号/信息滞后)。教训: subagent 指令
   应明确 "禁止改主文档, 只改指定测试文件; 迭代记录由主 agent 统一写"。
3. **行为断言的价值**: 升级后测试验证的是"分析行为" (边/查询/缺口) 而非
   "解析产出", 能真正防语义回归 (如运算符边丢失 / 约束变量关联断裂)。

## 📌 后续 (可选)

- 剩余 ⚠️ 文件 (~12 个, 小文件): test_class_method/oop, test_dpi, test_interface_basic,
  test_modport_direction, test_generate_real_world, test_port_inout 等 — 按需继续
- 127 个无 docstring 测试文件 — 补 docstring (可维护性)
