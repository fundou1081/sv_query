# Iteration 054: 修 native GAP-1/GAP-2 + GAP-3 决策确认

**Metadata**:
- **Iteration #**: 054
- **Task Tree Level**: L1
- **Parent Task**: ARCHITECTURE_TODOLIST #7 迁 pyslang 11.0 native API
- **Created**: 2026-08-29 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (GAP-1/GAP-2 修复, GAP-3 拍板, 2 xfail 转正)

## 🎯 本次目标

方豆指示 "按1 做":
- **GAP-3 决策 = 选项 1**: native 找全嵌套 generate 实例是 **bugfix, 接受** —
  G3 计划按"接受下游 6 项目输出变化"写
- 同时执行推荐的下一步: **修 native 的 GAP-1/GAP-2** (不碰 MIG, 符合 option A 边界)

## 📊 当前状态 / 预期结果

iter_053 发现 3 个 MIG 级差异并固化为 2 xfail + 1 能力锁定:
- GAP-1: generate block parent (`top` vs `top.gen_loop[0]`)
- GAP-2: InstanceArray native 提取错 (1 假实例 vs 3 真实例)
- GAP-3: 嵌套 generate 递归漏 4 个, native 找全 (已拍板接受)

预期: GAP-1/GAP-2 修复后, verify_native_parity.py 相应 fixture 变 EQUIVALENT,
2 个 xfail 转正为普通断言。

## 🔬 实际结果

### 1. pyslang 结构探测 (先探索后决策)

- `InstanceArraySymbol`: kind=`SymbolKind.InstanceArray`, `.name`="u_arr",
  `.elements` = list of `SymbolKind.Instance`, 每个元素有:
  `hierarchicalPath`="top.u_arr[0]", `arrayName`="u_arr", `definition.name`="sub",
  `portConnections` 完整
- `GenerateBlockSymbol` / `InstanceArraySymbol` 都有 `hierarchicalPath`
- 数组在 generate 内: 递归 parent = 元素自身 hp (`top.gen_loop[0].u_arr[0]`),
  与顶层数组行为一致

### 2. native_adapter.py 修复 (只改 native, 不碰 MIG)

- **GAP-1**: `_walk_instance` 的 parent 改为 `hierarchicalPath 去掉最后一段`
  (不再信任调用方传下的外层 parent — 那会丢 generate 段)
- **GAP-2**: 新增 `_walk_instance_array`, 子循环加 `InstanceArray` 分支且
  **必须排在 `'Instance' in kind` 之前** (`SymbolKind.InstanceArray` 也含
  "Instance" 子串, 原实现误匹配成普通实例 → 假实例 `top.u_arr` 类型 `u_arr`)
  - 数组元素 parent = 自身 hp (复刻递归 InstanceArray 分支的 child_path 语义)
- generate block 内的子循环同样补 InstanceArray 分支 (for 循环里 `sub u_arr[2]()`)

### 3. 复跑 verify_native_parity.py (8 fixtures)

| fixture | 修复前 | 修复后 |
|---|---|---|
| generate_block | DIFF (GAP-1) | ✅ EQUIVALENT |
| instance_array | DIFF (GAP-2) | ✅ EQUIVALENT |
| nested_generate | DIFF (GAP-3) | DIFF (**已拍板接受**, native 找全) |
| conditional_generate | EQUIVALENT | DIFF (**新发现, 已接受**, 见下) |

### 4. 新发现: conditional generate 的 parent (已按 GAP-3 先例接受)

递归对 plain GenerateBlock (if-generate) **透明**: `top.enable_block.u_sub` 的
parent = `top` (丢失 generate 路径); native (修后) = `top.enable_block` (完整路径)。

- id/type/端口表完全一致, **只有 parent 字段不同**
- MIG parent 的下游消费: `get_instances_by_parent` **无调用方** (死代码),
  `graph/models.py:590` 仅序列化输出 → 风险低
- 与 GAP-3 同类 (native 更正确, 输出会变), 沿用方豆 "按 1 做" 先例接受,
  固化进测试 `test_conditional_generate_parent_native_scoped`

### 5. 测试 (sim/tests/unit/test_native_adapter_parity.py)

- GAP-1/GAP-2 的 `expectedFailure` 转正为普通断言 (含 parent_module 对比,
  比原来的 (id, def_name) 更严)
- 新增 conditional-generate parent 行为固化
- 结果: **13 passed, 0 xfail** (原 10+2xfail)

## 💡 关键发现 / 关键技术 / 决策

1. **'Instance' in kind 是陷阱**: `SymbolKind.InstanceArray` 含 "Instance" 子串 —
   kind 字符串匹配必须按 GenerateBlockArray → GenerateBlock → InstanceArray →
   Instance 的顺序, 或精确比较 SymbolKind 枚举。这是 GAP-2 根因。

2. **递归自身的 parent 语义不一致** (三套规则):
   | 场景 | 递归 parent |
   |---|---|
   | 普通实例 | hp 去最后一段 (`top`) |
   | generate-for (GBA) | hp 去最后一段 (`top.gen_loop[0]`) |
   | if-generate (GB) | 外层路径 (透明, `top`) — **丢失 generate 段** |
   | 数组元素 | 元素自身 hp (child_path 语义) |
   native 统一为 "hp 去最后一段 = 完整作用域路径", 除数组元素 (复刻 child_path)。
   3/4 场景与递归一致, GB 场景 native 更正确 (已接受)。

3. **修复边界**: native_adapter 生产代码无消费方 (option A 未接线), 修复
   零生产影响; 全部差异用脚本 + 测试固化, G3 计划有据可依。

## 📌 已知差异清单 (G3 计划输入, 更新版)

| ID | 场景 | 差异 | 状态 |
|---|---|---|---|
| GAP-1 | generate block parent | 已对齐递归 | ✅ 修 |
| GAP-2 | InstanceArray | 已加分支, 与递归一致 | ✅ 修 |
| GAP-3 | 嵌套 generate | 递归漏、native 找全 | ✅ 方豆拍板接受 (bugfix) |
| GAP-4 | conditional generate parent | 递归丢 generate 段、native 完整 | ✅ 按 GAP-3 先例接受 (新) |
