# PLAN — 全局唯一计划树

> **唯一真相源**：sv_query **所有代码修改计划**只登记在本文件。
> 迭代记录（[docs/task_tree/iterations/](docs/task_tree/iterations/)）是**历史**；本文件是**现在做什么、做到哪**。
>
> 维护规则见 [AGENTS.md §2](AGENTS.md)；机械校验：`python3 tools/check_plan.py`。
>
> 格式（每行一项，子项用 `-- ` 前缀，id 全局唯一）：
> ```
> current item : P13.6 多驱动标记 + 静态 memory 位精度 <待做>
>
> P0 建图层与查询层的结构化拆分 <已完成>
> -- P0.1 图快照基线工具 <待做>
> ```
> 状态词表：`待做` / `进行中` / `已完成` / `阻塞` / `放弃`（只能这五个）。
> 父项可整体标 `进行中`（表示该组在做）；**叶子项**最多一项 `进行中`，
> 且当 `current item` 标为 `进行中` 时，它必须是那个叶子项。
> **全部完成时**：`current item` 可指向最后完成项并标 `已完成`（无 `待做/进行中/阻塞` 时才允许）。

## 当前项

current item : P13.6 多驱动标记 + 静态 memory 位精度 <待做>

## 计划树

P0 建图层与查询层的结构化拆分 <已完成>
-- P0.1 图快照基线工具：图的节点/边 snapshot diff（拆 P0.2 的前提） <已完成>
-- P0.2 拆 `_trace_drivers_recursive`（343 行）：wrapper 跨实例 / 位级提升 / 自环分类 / q-d 互补 / 边过滤 / 源分类 六类规则拆成独立策略函数 <已完成>
-- P0.3 `GraphBuilder` 6 个后处理 pass 改声明式 pipeline（inputs/outputs，与 UnifiedTracer 一致） <已完成>
P1 视图层去双命名空间 <已完成>
-- P1.1 `visualize module` 换实例级边推导（不再依赖 MIG 的类型映射） <已完成>
-- P1.2 删 `ModuleInstanceGraph.port_to_internal` / `internal_to_port` / `get_internal_signal` / `get_port_path` <已完成>
P2 边缘场景补测 <已完成>
-- P2.1 位选跨模块 / interface 成员 / inout 三态 / class-struct 成员 的 drive-load 回归 <已完成>
P3 长期 backlog <已完成>
-- P3.1 `UnifiedTracer` 三个巨型私有方法（173 / 134 / 151 行） <已完成>
-- P3.2 缓存只有总量 LRU 上限，无"按工程过期" <已完成>
-- P3.3 [docs/EXP_IDEAS.md](docs/EXP_IDEAS.md) 的 10 条退役想法 —— 未来逐个重做 <已完成>

## 已完成（保留最近记录，便于核查上一轮）

P5 位级 drive/load 精度修复 <已完成>
P6 表达式驱动的逐位映射 <已完成>
P7 位精确性扩展（续） <已完成>
P8 常量位分解 <已完成>
P9 signedness 建模与符号扩展 <已完成>
P10 整数类型位宽提取 <已完成>
P11 packed struct/union 宽度、signedness 与成员布局 <已完成>
P12 packed 成员位级查询桥 <已完成>
-- P12.1 成员位 → 聚合位换算（parent 链，struct/union/嵌套） <已完成>
-- P12.2 未被引用的成员节点补齐（查询可达） <已完成>
-- P12.3 测试与文档 <已完成>

P13 信号追踪能力补强（2026-10-27 评审 backlog） <进行中>
-- P13.1 缓存 key 纳入 SVQ_BIT_BRIDGE 模式（P0 静默错误） <已完成>
-- P13.2 粗粒度回退显式标记（precision/warnings） <已完成>
-- P13.3 capabilities bit_precision 契约 + 输出 is_signed/parent/bit_range <已完成>
-- P13.4 深层 packed 成员节点（o.inner.a） <已完成>
-- P13.5 三元/case 分支按位映射 <已完成>
-- P13.6 多驱动标记 + 静态 memory 位精度 <待做>
-- P11.1 聚合宽度/signedness（var/net/port，含嵌套） <已完成>
-- P11.2 成员宽度/位偏移（p.a → 4 位 + 在 p 中的位段） <已完成>
-- P11.3 测试与文档：聚合/成员矩阵 + 基线 <已完成>
-- P10.1 `integer/int/byte/shortint/longint/time` 位宽（syntax keyword + semantic bitWidth） <已完成>
-- P10.2 懒建节点宽度回填 + 缓存版本 <已完成>
-- P10.3 测试与文档：类型矩阵 + 图基线 <已完成>
-- P9.1 图节点 signedness：TraceNode.is_signed + adapter 提取 + 序列化/缓存版本 <已完成>
-- P9.2 查询层：有符号字面量 & 有符号信号扩展（符号位/零扩展） <已完成>
-- P9.3 测试与文档：signed/unsigned 扩展矩阵 + 图基线 <已完成>
-- P8.1 拼接字面量段逐位（`{a, 4'h0}`） <已完成>
-- P8.2 常量源切片值位（`y=4'hA` → 1'b1/1'b0） <已完成>
-- P8.3 测试与文档：常量/零扩展/位运算常量 <已完成>
-- P7.1 直接拷贝 `assign y=a` 的查询层位映射（one 模式也能位精确） <已完成>
-- P7.2 纯拼接 `{a,b}` 逐位映射（按表达式顺序 + 操作数宽度切段） <已完成>
-- P7.3 测试与文档：拷贝/拼接/多驱动/常量边界 <已完成>
-- P6.1 查询层 fanin：按运算符把 s[i] 映射到操作数位（同索引/前缀/移位） <已完成>
-- P6.2 查询层 fanout：按运算符把 a[i] 映射到结果位（前缀/移位） <已完成>
-- P6.3 测试与文档：运算符矩阵 + 粗粒度回落 + 不得跨位 <已完成>
-- P5.1 F1 缺位回退按位过滤（消切片/多驱动跨位污染） <已完成>
-- P5.2 F2 位节点死胡同补父总线追溯（消断链） <已完成>
-- P5.3 位级测试加强：逐位对应 + 负向污染/断链守卫 + 反例固化 <已完成>
-- P5.4 F3 slice 节点按位展开（LHS/RHS 切片 → 逐位节点 + 偏移映射） <已完成>
-- P5.6 F5 load 方向位精度（fanout 按位；表达式驱动需逐位边） <已完成>
-- P5.5 F4 bus↔无位节点侧合成位桥（one 默认 / full 可选；iter_293） <已完成>

P4 已完成归档 <已完成>
-- P4.1 单一命名空间收口：影子节点归零、extractor 4→2（iter_276） <已完成>
-- P4.2 删除 `port_to_internal` 自映射（iter_277） <已完成>
-- P4.3 `distance` 真实跳数 + 底座健壮性审计（iter_278） <已完成>

## 变更记录

| 日期 | 变更 |
|---|---|
| 2026-10-25 | 建立本计划树；P0~P3 来自底座审计结论（iter_278） |
| 2026-10-26 | P0/P1/P2/P3 全部完成（iter_279~288）；计划树进入"无待办"状态 |
| 2026-10-27 | P5~P12 位精确性系列完成（iter_289~300）；P13 评审 backlog 登记（iter_301，见 architecture/trace_capability_review_2026-10-27） |
