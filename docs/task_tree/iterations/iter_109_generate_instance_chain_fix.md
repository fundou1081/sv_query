# Iteration 109: generate-for 实例化链提取修复 (#45 + 连接提取)

**Metadata**:
- **Iteration #**: 109
- **Task Tree Level**: L1 (EXTRACTION_COVERAGE #45 + 连接提取)
- **Parent Task**: openrtl 摸底发现的缺口 (verilog_cordic_core 暴露, 方豆 "发现问题就来修复")
- **Created**: 2026-09-02 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功

## 🎯 本次目标

修复 verilog_cordic_core 暴露的 generate-for 实例化链提取缺口:
`generate for` 实例化子模块 (rotator U×16, 经数组端口 x[i]→U.x→x[i+1] 互连)
不产生实例连接边, 只剩顶层输入 assign。

## 📊 当前状态 / 预期结果

- cordic.v 修复前: 72 节点 / 6 DRIVER / 57 BIT_SELECT (CORDIC 数据通路不可见)
- 最小复现 (genfor_inst.sv): 实例折叠成单 top.g.U + 0 连接边

## 🔬 实际结果

### 三个串联缺口 (逐个定位)

1. **#45: generate-only 实例化模块定义收集不到** — `get_modules` 的
   collect_instances 不递归 GenerateBlockArray/GenerateBlock → rot 端口定义缺失
   → 无方向信息 → 无连接边。
   修复: 收集器下钻 generate 块 (镜像 native_adapter walker)。

2. **连接表达式 ElementSelect/Assignment 未解包** — `get_instance_connection`
   只处理 NamedValue/Assignment-NamedValue/Concat; `.x(arr[i])` (ElementSelect)
   和 `.xo(arr[i+1])` (Assignment-left-ElementSelect) 的 signal_name 停留 "?"
   → 整条 conn 丢弃。
   修复: 新增 `_conn_expr_to_signal` (ElementSelect/RangeSelect/NamedValue 解包)
   + `_eval_select_index` (Literal/Conversion/`i±k` BinaryOp 折叠) +
   `_genvar_index_from_hp` (entry 索引取自 hierarchicalPath 'top.g[2].U' → 2)。
   注意: pyslang IntegerLiteral 的 str() 是类名, 数值在 .value。

3. **实例路径折叠** — connection_extractor 的 gen_block 不带 entry 索引 →
   4 个 U 全折叠成 top.g.U。
   修复: `_get_generate_block_name` 保留 [i] → 路径 top.g[i].U 区分。

### 信号作用域 (generate 段)

- 连接信号 (数组元素等) 声明在模块级, 不是 generate 作用域: top.g[2].U 的连接
  信号用 top.arr[2] (非 top.g[2].arr[2])。connection_extractor 加 _sig_scope
  (inst_path 去掉 .{gen_block}. 段)。

### 设计约定 (保持原行为, 不破坏)

- 输出端口边1 (child_signal_id→inst_port_id) 是 **2026-07-08 故意的自环** —
  作为"模块内部驱动实例输出"标记, test_cross_module_tracking 依赖。不加
  self-loop 防护 (尝试过 → 3 测试破, 回退)。

### 验证

- 最小用例 (genfor_inst.sv): 链完整 a→arr[0]→g[0].U→arr[1]→...→arr[4]→out,
  input/output CONNECTION 索引全解析, 无 '?' 占位
- cordic.v: 72 节点/6 DRIVER → **337 节点 / 180 CONNECTION / 25 DRIVER /
  274 BIT_SELECT / 9 CLOCK** — rotator 实例链 + 嵌套 generate shifter 可见
- 回归: fixture golden_dataflow_38 + truth 测试 (test_genfor_instance_truth 6);
  test_generate_instance_connections 更新到带索引新方案 (路径更正确)

## 💡 关键发现 / 决策

1. **三个缺口串成链**: 模块定义 → 连接表达式 → 实例路径, 缺一环整条 generate
   实例链就灭 — 摸底 (真实项目) 是找到这类链式缺口的最佳手段。
2. **自环输出边是"设计标记"而非垃圾**: 改它之前必须读测试注释 (FIX 2026-07-08
   明确写了用意) — 差点砍掉 3 个测试依赖的行为。
3. **pyslang 陷阱**: IntegerLiteral str()=类名; generate entry 的符号层 genvar
   不解析 (NamedValue 'i'), 索引只能从 hierarchicalPath 取。

## 📌 状态

- ✅ 三缺口修复 + 信号作用域 + 回归测试
- ⏸ 剩余已知 (非本次): CORDIC rotator 内部深 generate 的逐位 DRIVER 仍可能
  不全 (嵌套 generate shifter 的迭代结构), 后续可按图结构深挖
- 全量回归待确认
