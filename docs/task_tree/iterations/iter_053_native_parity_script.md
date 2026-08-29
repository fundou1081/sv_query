# Iteration 053: #7 option A — native API vs 自建 MIG diff 验证脚本

**Metadata**:
- **Iteration #**: 053
- **Task Tree Level**: L1
- **Parent Task**: ARCHITECTURE_TODOLIST #7 迁 pyslang 11.0 native API
- **Created**: 2026-08-29 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (option A 验证脚本 + 3 个 MIG 级差异实证)

## 🎯 本次目标

方豆选择 **option A**: 先写 native API vs 自建 MIG 的 diff/parity 验证脚本,
**不替换 MIG 实现**。等价性确认后, 才进入 G3 计划与分批实施。

- 交付物 1: `tools/verify_native_parity.py` — MIG **四表** diff 脚本
- 交付物 2: 真实项目 (CVA6 等) 等价性实证
- 交付物 3: 迭代记录 + 已知差异清单 (供 G3 决策)

## 📊 当前状态 / 预期结果

开工时已有:
- `sim/tests/unit/test_native_adapter_parity.py` — 9 passed, 但**只比实例 (id, def_name) 集合**
- `src/trace/core/native_adapter.py` — `get_module_instances_native()` 已实现 (Phase 1, 2026-06-25)
- `MIG.build(SemanticAdapter)` 已半 native (hierarchicalPath/portConnections 来自 pyslang symbol),
  但实例枚举仍走 `semantic_adapter.get_module_instances()` 递归

预期: 现有 parity 测试覆盖不到的 **MIG 级**差异 (parent / 端口表) 会被新脚本量化出来。

## 🔬 实际结果

### 1. 脚本: `tools/verify_native_parity.py`

两条路径都走 **同一个 MIG.build** (只换实例枚举来源), 隔离枚举差异:
- A) `MIG.build(SemanticAdapter(root, target))` — 递归枚举 (现行)
- B) `MIG.build(NativeAdapterShim(root, target))` — `get_module_instances_native` (native 枚举)

比较 MIG **四张表**: `instances` / `port_to_internal` / `internal_to_port` / `_module_ports`。

### 2. fixtures 结果 (8 项, EQUIVALENT=5, DIFF=3)

| fixture | A/B 实例数 | 结果 |
|---|---|---|
| simple | 3/3 | ✅ EQUIVALENT |
| generate_block | 4/4 | ❌ DIFF (**GAP-1**) |
| conditional_generate | 1/1 | ✅ EQUIVALENT |
| multi_depth | 5/5 | ✅ EQUIVALENT |
| instance_array | 3/1 | ❌ DIFF (**GAP-2**) |
| nested_generate | 0/4 | ❌ DIFF (**GAP-3**) |
| leaf_top | 0/0 | ✅ EQUIVALENT |
| port_connections | 1/1 | ✅ EQUIVALENT |

### 3. 真实项目结果

| 项目 | 编译入口 | 结果 |
|---|---|---|
| **cva6** | `cva6_full.f` | ❌ timescale 错误 (`design element does not have a time scale defined`) |
| **cva6** | `Flist.ariane` (现有测试在用) | ❌ 65 个 elaboration 错误 (`csr_regfile.sv InvalidMemberAccess` 等) |
| **cva6** | `cva6.f` | ❌ 常量折叠错误 (`value must be positive` — `{CVA6Cfg.XLEN-5{1'b0}}`) |
| **darkriscv** | `rtl/darkriscv.v` (单文件) | ⚠️ 编译通过, 但 **leaf 模块无子实例** (A=0 B=0, 无信息量) |
| coralnpu / zipcpu / riscv_core / vortex | — | ⏸ 无现成编译入口, 待人工整理 filelist |

**结论**: 6 个目标项目当前**都不能在 strict 模式下干净编译** — 这是 pyslang 与
这些项目的**已知 elaboration 不兼容** (现有 `sim/tests/usage/` 测试全部靠 `--no-strict`
容忍)。真实项目等价性评估 = **#7 子任务 1 的独立工作**, 前置条件是先解决严格编译
(filelist 整理 / timescale / 常量折叠), option A 不解决这个。脚本已就绪, 编译修好后
`python tools/verify_native_parity.py --all` 即可跑全量评估。

### 4. 测试固化 (sim/tests/unit/test_native_adapter_parity.py)

- 新增 fixture: `instance_array`, `nested_generate`
- `test_generate_block_parent_parity` — GAP-1 固化 (**expectedFailure**, 当前 xfail)
- `test_instance_array_parity` — GAP-2 固化 (**expectedFailure**, 当前 xfail)
- `test_nested_generate_native_finds_all` — GAP-3 锁定 native 能力 (pass)
- 结果: **10 passed + 2 xfailed** (xfail = 已知差异显式可见; 修复后变 XPASS 提醒移除标记)

## 💡 关键发现 / 关键技术 / 决策

### GAP-1: generate block 的 parent_module 不一致 (MIG.parent 受影响)

递归: `parent = 'top.gen_loop[0]'` (hierarchicalPath 去掉最后一段, 完整 generate 路径)
native: `parent = 'top'` (把外层 parent 直接传下去, 不含 generate 段)

**现有 parity 测试测不出来** — 它只比 (id, def_name)。MIG.build 用 `parent_module`
填 `ModuleInstanceNode.parent`, 下游 PathResolver 会消费 → 切 native 必须对齐。

### GAP-2: InstanceArray (数组实例化) native 提取错误

- 递归: 3 个实例 `top.u_arr[0..2]`, 类型 `sub`, 端口表完整
- native: **1 个假实例** `top.u_arr`, 类型 `u_arr` (数组名当模块类型), 端口表全空

根因: native `_walk_instance` 用 `'Instance' in str(child.kind)` 判断,
`SymbolKind.InstanceArray` 也含 "Instance" → 被误当普通实例。native 缺 InstanceArray 分支。

### GAP-3: 嵌套 generate (genvar 循环套循环) 递归漏实例, native 找全

- 递归: **0 个** — GenerateBlockArray 的 entry 里只处理直接 Instance, 不递归
  entry 内层嵌套的 GenerateBlockArray/GenerateBlock → 漏
- native: 4 个全找到 (`top.gen_i[0].gen_j[0].u_sub` ...)

**方向判断**: 这是递归路径的 bug, native 是"修复"。但切 native 会让 MIG 输出
**增加 4 个实例** → 下游 6 项目回归会出现差异 → **必须由方豆决策** (G3 计划输入):
当作 bugfix 接受输出变化, 还是先对齐再切。

### 方法学: parity 验证必须到 MIG 四表, 不能只比实例 id 集合

本次最大教训: 现有 9 个 parity 测试全绿, 但 3 个真实差异一个都没抓到 —
因为比较口径 (id, def_name) 太粗。**等价性验证的契约 = MIG 全量输出四表**。
后续 G3 实施必须把本脚本纳入回归。

## 📌 已知差异清单 (供 G3 决策, 详见上方)

| ID | 场景 | 差异 | 方向 |
|---|---|---|---|
| GAP-1 | generate block | parent_module: `top` vs `top.gen_loop[0]` | native 需对齐递归 |
| GAP-2 | InstanceArray | native 提取错 (1 假实例 + 端口表空) | native 需修 (加分支) |
| GAP-3 | 嵌套 generate | 递归漏 4 个, native 找全 | 输出变化, 需方豆决策 |
