# L3 Truth 层扩充 T1-T12 — 1:1 golden 缺口补齐

> **创建**: 2026-09-02 GMT+8
> **背景**: 方豆 "继续扩充 truth 层, 添加更多 golden。先分析缺哪些" → gap 分析产出 12 项缺口
> (T1-T12), 方豆拍板 "按这个顺序来推进吧"。
> **父任务**: Test_Assets_ABC → C 组扩 truth 层 (iter_083 后继续)

## Gap 分析结论 (2026-09-02)

truth 层 32 测试 / 5 文件, 1:1 golden 只覆盖 generate-for (#18) / generate 内 wire (#6) /
ternary (#15) / 跨模块连接 (L2)。18 种"完整支持"语法中 12 种无 1:1 锁定。

| # | 缺口 | 锁定语义 | 候选 fixture | 优先级理由 |
|---|---|---|---|---|
| T1 | assign 链基础数据流 (#1/#5) | `y=a+b; z=y<<2` 精确节点/边 | `golden_dataflow_1_op` / `5_combined` | 最基础语义无锁定 |
| T2 | always_ff + clock/reset (#2) | CLOCK/RESET 边精确结构 | `fsm_demo.sv` / orphan_01 | 时钟/复位核心 |
| T3 | case 多分支条件边 (#7) | 每分支 condition 边 | `golden_dataflow_9_case` / `16_nested_case` / `17_if_case_mixed` | case 最常用控制流 |
| T4 | 位选 RHS/LHS (#8/#9) | bit-range 保留 | `golden_dataflow_3_slice` / `25_array_index` | bit_select_handler 刚重写 |
| T5 | concat LHS/RHS (#10/#11) | 拼接展开精确边 | `golden_dataflow_4_concat` | — |
| T6 | function/task 调用 (#13/#14) | 调用边 + 形参映射 | `golden_dataflow_19_function_multi` / `28_func_bitmix` | iter_076 刚修 task 形参 |
| T7 | parameter/localparam 过滤 (#17) | 反例式: 参数不在图中 | 任意 fixture | 过滤错污染全图 |
| T8 | alias 方向语义 (#12) | refs[0]=target | dataflow_fixtures | 方向反是静默错误 |
| T9 | class 成员 DRIVER 边 (#16) | class 方法体赋值 | cva6_alu_pattern | C 组计划遗留 (iter_075 修过) |
| T10 | generate-if/case 内 wire (#23/#24) | 有条件支持现状锁定 | `golden_dataflow_30_generate_if` / `31_generate_case` | 行为边界值得锁死 |
| T11 | L4 SVG 布局 golden (非 generate) | 普通图/层级图布局 | case_demo / hierarchy | 只有 case27 一个 SVG 级 truth |
| T12 | trace 查询精确 driver 集 | "谁驱动这个信号"精确集合 | strict_uart / minimal_3module | 核心产品承诺, 现仅 ≥N 下界断言 |

## 判定 (每个 T#)

- 新增/扩展 truth 测试文件, 断言**精确**节点/边/标签 (非 ≥N 下界)
- 该文件 pytest 全绿
- 迭代记录 + CURRENT_TODO 勾选 + overview 更新 (代码+文档同 commit)

## 状态日志

- **2026-09-02** — 创建任务文件, gap 分析完成, 方豆 "按这个顺序来推进吧"
