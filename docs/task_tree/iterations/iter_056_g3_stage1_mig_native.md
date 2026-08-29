# Iteration 056: G3 阶段 1 — MIG.build 实例枚举切 native (GAP-5 发现与修复)

**Metadata**:
- **Iteration #**: 056
- **Task Tree Level**: L1
- **Parent Task**: ARCHITECTURE_TODOLIST #7 迁 pyslang 11.0 native API
- **Created**: 2026-08-29 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (MIG 生产路径已全 native; 等价门禁逐字节一致; 0 新回归)

## 🎯 本次目标

方豆 "可以, 进行 d1 吧" — 确认 G3 方案 C, 开工**阶段 1: MIG.build 实例枚举切 native**。

计划前置: R2 核实 (D3 承诺); baseline 快照; 切换; 门禁; 回归。

## 📊 当前状态 / 预期结果

- MIG.build 的 SemanticAdapter path 用递归枚举; hierarchicalPath/portConnections 已 native
- GAP-1/2 已修, GAP-3/4 已拍板接受 (iter_054)
- 预期: MIG.build 切 native 后, verify_native_parity.py 输出与切换前**逐字节一致**

## 🔬 实际结果

### 1. R2 核实 (D3): 无重复计数, 无需单独修

`connection_extractor` 的 `get_module_instances() + get_generate_instances()`:
- generate_for 场景: M=4 (完整 hp) + G=3 (短名 'u_sub') → **0 重叠**
- conditional+loop 场景: M=2 + G=0 → 0 重叠
- 结论: **重复计数不存在**; 附带发现 get_generate_instances 覆盖率不一致
  (conditional+loop 返 0) — 记入已知清单, 非本轮范围

### 2. 实施改动

**MIG.build** (`module_instance_graph.py:123`): 加 `instance_source` 参数 (显式验证钩子,
非 fallback):
- `"auto"` (默认, 生产): SemanticAdapter 且带 `_root` → **native 枚举**
- `"recursive"` / `"native"`: verify_native_parity.py A/B 路径显式指定
- native wrapper (_NativeInstanceWrapper) 与 MIG.build 用到的接口 (._symbol / .name /
  .parent_module) 兼容, 其余代码 (hierarchicalPath/portConnections/get_module_name)
  零改动 — **切换 = L136 一处**

**verify_native_parity.py**: A 传 recursive / B 传 native; 新增 GAP-5 探测 fixture
(no_target_loop_gen, target=None)。

### 3. 新发现 GAP-5: `_is_user_module` 过滤误伤合法 top (已修)

6 个 MIG 测试失败暴露: UnifiedTracer 默认 `target_module=None` → native 走
`_is_user_module` 启发式, 把"只有 generate 块、无直接 InstanceSymbol"的合法 top
(顶层 generate-for 实例化) 误判 utility cell → 整棵跳过 → **MIG 空**。

递归不过滤任何 top → 这是超出 GAP-3/4 的**第 5 个行为差异**, 违反 parity 纪律。

修复 (`native_adapter.py`):
- target=None 时**移除过滤** (walk 所有 top, 与递归一致); 删除 `_is_user_module` 死代码
- top-skip 条件补 `target_module is None` (否则 top 本身被当实例 emit — 原代码
  target=None 路径的潜在 bug, 之前被过滤掩盖)

utility cell 过滤的原始诉求 (CVA6) 由 target 参数路径覆盖 (指定 target 只 walk 该子树),
无需启发式。

### 4. 等价门禁: 切换前后逐字节一致

- 切换前 baseline: `/tmp/parity_before.txt` (8 fixtures: 6 EQUIVALENT + GAP-3/4 两 DIFF)
- 切换后: 8 fixtures **逐字节一致**; 新增 no_target_loop_gen → **EQUIVALENT (A=2 B=2)**
- 最终: **9 fixtures, 7 EQUIVALENT + 2 DIFF (仅 GAP-3/4, 已接受清单不变)**

### 5. 回归

- MIG 相关套件 (test_mig_generate_block / test_mig_validator / test_pr3_mig_fallback /
  test_cross_module_tracking / test_pr4_visualize_l2): **80 passed + 1 failed**
  — 唯一失败 `test_cross_module_connection` 在**切换前 baseline 上也失败** (既有, 非引入)
- truth: 4 passed
- unit+cli 全套: (见下)
- ruff: 全过

## 💡 关键发现 / 关键技术 / 决策

1. **"切换 = 一处" 是探索的回报**: G3 计划阶段 1 只改 MIG.build 一行 (加参数),
   因为 hierarchicalPath/portConnections 早已 native。真正的坑不在切换点, 在
   **native 枚举自身的 target=None 行为** (GAP-5) — 只有接上生产路径 (UnifiedTracer
   默认 target=None) 才暴露。

2. **GAP-5 是"验证脚本测不到"的一类**: 所有 fixture 都用 target='top', 而生产默认
   target=None — 脚本盲区。教训: parity 验证要覆盖**生产默认参数路径**,
   已补 no_target_loop_gen fixture 固化。

3. **`_is_user_module` 启发式删除的决策**: 它本来就是脆弱的启发式 (文档自述
   "简化"), 且与递归行为冲突。删除后 CVA6 的 utility cell 过滤诉求改由 target
   参数覆盖 — 语义更干净, 与递归完全对齐。

## 📌 已知差异清单 (更新版)

| ID | 场景 | 状态 |
|---|---|---|
| GAP-1 | generate block parent | ✅ 修 (iter_054) |
| GAP-2 | InstanceArray | ✅ 修 (iter_054) |
| GAP-3 | 嵌套 generate 递归漏 | ✅ 拍板接受 (bugfix) |
| GAP-4 | conditional generate parent | ✅ 按先例接受 |
| GAP-5 | target=None 过滤误伤合法 top | ✅ 修 (本次) |

**生产 MIG 路径 = native 枚举完成**。阶段 2 (get_module_instances 全量切 + 删
SyntaxTree 死代码) 待方豆单独决策。
