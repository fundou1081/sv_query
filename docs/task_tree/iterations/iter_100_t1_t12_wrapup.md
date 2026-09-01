# Iteration 100: Truth 层扩充 T1-T12 收尾汇总

**Metadata**:
- **Iteration #**: 100
- **Task Tree Level**: L1 (Truth 层扩充 T1-T12)
- **Parent Task**: L3_truth_expansion
- **Created**: 2026-09-02 GMT+8
- **Author**: AI 助手 (方豆 "按这个顺序来推进吧")
- **Outcome**: ✅ 成功 — T1-T12 全部完成, truth 层 32 → 112 测试

## 🎯 本次目标

收尾: 汇总 T1-T12 成果, 更新所有追踪文档, 汇总顺带发现的缺陷。

## 📊 当前状态 / 预期结果

- 12 项 truth 扩充全部完成 (iter_088~099)
- 预期: 文档同步 + 全量验证

## 🔬 实际结果

### 成果清单 (12 文件 + 5 新 fixture, 80 新测试)

| T# | 文件 | 测试 | 锁定的 1:1 语义 | iter |
|---|---|---|---|---|
| T1 | test_assign_chain_truth | 9 | assign 二元运算 / wire 链 + 位选精确结构 | 088 |
| T2 | test_clock_reset_truth | 9 | always_ff 异步复位 / case-in-seq CLOCK 条件 | 089 |
| T3 | test_case_branch_truth | 8 | case 分支条件边 (含字面量归一化) | 090 |
| T4 | test_bit_select_truth | 10 | BIT_SELECT 回边 / bit_slice / part-select 占位 | 091 |
| T5 | test_concat_truth | 3 | RHS 拼接无跨边 | 092 |
| T6 | test_function_task_truth | 6 | function 调用节点 / task 形参真边 | 093 |
| T7 | test_parameter_filter_truth | 5 | 参数过滤反例 / 条件保留参数名 | 094 |
| T8 | test_alias_truth | 3 | alias 方向 (source→target) | 095 |
| T9 | test_class_oop_truth | 4 | class 三件套 + 方法体成员边 | 096 |
| T10 | test_generate_if_case_truth | 6 | generate 编译期分支选择 | 097 |
| T11 | test_layout_truth | 9 | SVG 渲染结构 (op/信号分类) | 098 |
| T12 | test_query_truth | 8 | fanin/fanout 精确驱动集 | 099 |

新 fixture (golden_mini 既有池): golden_dataflow_32_task_call / 33_parameter_filter
/ 34_alias / 35_class_oop (+ 复用 1/3/4/5/9/16/17/19/25/28/30/31 + fsm_demo + orphan_01)

**全量验证**: truth 层 17 文件 108 passed + 4 skipped (既有 d1 mutex skip), 0 failed。

### 顺带发现 (记录待方豆定夺, 均未烘焙进 golden)

| # | 缺陷/quirk | 影响 | 记录位置 |
|---|---|---|---|
| A | assign 边 expression = 整份源文件+空字节 | handshake/dataflow/viz 消费 | iter_088 |
| B | net-decl wire 显式位宽 [15:0] 被忽略 → width=(1,0) | width 下游 | iter_088 |
| C | LHS 拼接位置映射丢失 (笛卡尔积 4 边) | 文档标"完整支持"不符 | iter_092 |
| D | localparam 常量在 ternary 真分支无驱动边 | 分支常量不可见 | iter_094 |
| E | indexed part-select `+:` 动态索引 → bus[?:?] 占位 | 功能缺口 | iter_091 |
| F | generate-if 内 shift 赋值 (<< / >>>) 无 DRIVER 边 | generate_if_alu | iter_097 |

## 💡 关键发现 / 决策

1. **集合相等断言** (多节点/边 = 偏离) 是 truth 层的正确粒度 — 比存在性断言
   更能捕获提取逻辑漂移, 12 项统一采用。
2. **truth 层 = 缺陷探测器**: 写 golden 时实测暴露 6 个真实缺陷/quirk —
   扩充 truth 的额外价值。
3. **缺陷不烘焙进 golden**: 已知坏行为不断言 (修好后再补), 避免 golden 变成
   锁定 bug 的障碍。

## 📌 状态

- ✅ T1-T12 全部完成, truth 层 32 → 112 测试全绿
- ⚠️ 缺陷 A-F 记录, 待方豆定夺修复优先级
- 文档: overview / TEST_MAP / CURRENT_TODO / L3_truth_expansion 同步更新
