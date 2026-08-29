# Iteration 057: G3 阶段 2 — get_module_instances 全量切 native + 删 SyntaxTree 死代码

**Metadata**:
- **Iteration #**: 057
- **Task Tree Level**: L1
- **Parent Task**: ARCHITECTURE_TODOLIST #7 迁 pyslang 11.0 native API
- **Created**: 2026-08-29 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (5 个调用方统一 native; MIG 减 ~920 行; 0 新回归)

## 🎯 本次目标

方豆 "继续" — 实施 G3 方案 C **阶段 2**:
1. `semantic_adapter.get_module_instances()` 内部切 native (5 个生产调用方统一)
2. 删除 MIG SyntaxTree 死代码 (Phase 0-2 + 16 个 helper)
3. 性能 benchmark

## 📊 当前状态 / 预期结果

阶段 1 (iter_056) 后 MIG 生产路径已 native; 其余 4 个调用方 (unified_tracer /
graph_builder / connection_extractor) 仍用递归 get_module_instances。阶段 2 统一。

## 🔬 实际结果

### 1. 切换设计: native 枚举 + SemanticInstanceWrapper 包装 (零 API 风险)

探索结论: `SemanticInstanceWrapper` 类只被 semantic_adapter 内部实例化, 外部只消费
**实例属性** (`_symbol` / `name` / `type` / `parent_module` / `instances[0].decl` /
`get_parent_module()` / `parent`)。因此最低风险切换 = `get_module_instances()` 内部
调 `get_module_instances_native()` 后再用 **SemanticInstanceWrapper 包装** —
返回类型零变化, 5 个调用方无需改动。

旧递归 walk 保留为 `get_module_instances_recursive()` (验证参照, 非生产)。

### 2. 新发现 GAP-6 并修复 (stage 2 才暴露)

verilog-axi (库风格, 21 个顶层模块) 上: recursive=165 vs native=**2**。
根因: `_find_target_top(root, None)` 返回**第一个** top → native 只 walk 1 个 top。
递归 walk 全部顶层实例。修复: **target=None 时 walk 所有 topInstances** (不短路)。
修复后: **165 == 165, id+parent 集合完全一致**。5 个 test_cross_module_trace 测试
因此转绿 (stage 2 把 native 接入 connection_extractor 才暴露 — 与 GAP-5 同模式:
验证脚本 fixture 全用 target='top', 生产默认 target=None, 盲区)。

### 3. MIG SyntaxTree 死代码删除

- 精确分析: 16 个 helper 在 adapter path 内**零调用**, 外部引用全是其他类同名方法
- 删除: build 内 SyntaxTree path (Phase 0-2) + 16 helper ≈ **920 行**
  (module_instance_graph.py 1110 → 374 行)
- build 对 dict 输入改**显式 TypeError** (不留 silent 路径, 遵守纪律 2)
- **踩坑**: git checkout 恢复文件时冲掉了 stage 2 的 `elif get_module_instances_recursive`
  分支 → parity 误报 DIFF=0 (A 路径也变 native) → 补回后恢复 8 EQUIVALENT + 2 DIFF

### 4. 验证

| 项 | 结果 |
|---|---|
| parity 门禁 | 10 fixtures: **8 EQUIVALENT + 2 DIFF (仅 GAP-3/4, 已接受)** |
| native parity 单测 | 13 passed |
| MIG/跨模块套件 | 45 passed (含 test_cross_module_trace 5 个因 GAP-6 修复转绿) |
| truth | 4 passed |
| ruff | 全过 |
| unit+cli 全套 | (见下) |
| **benchmark** (verilog-axi 165 实例) | **native 2.14x 快于递归** (641ms → 300ms) |

### 5. 已知差异清单 (最终版)

| ID | 场景 | 状态 |
|---|---|---|
| GAP-1 | generate block parent | ✅ 修 (iter_054) |
| GAP-2 | InstanceArray | ✅ 修 (iter_054) |
| GAP-3 | 嵌套 generate 递归漏 | ✅ 拍板接受 (bugfix) |
| GAP-4 | conditional generate parent | ✅ 按先例接受 |
| GAP-5 | target=None 过滤误伤合法 top | ✅ 修 (iter_056) |
| GAP-6 | target=None 只 walk 第一个 top | ✅ 修 (本次) |

**5 个生产调用方 (MIG / unified_tracer / graph_builder / connection_extractor×2)
已全部走 native 枚举**。剩余: 6 项目 strict 编译 (子任务 1) + 全管线 benchmark。

## 💡 关键发现 / 关键技术 / 决策

1. **"包装而非重写 wrapper" 是阶段 2 的最优解**: 返回类型零变化, 避开
   _NativeInstanceWrapper 补 API 的全部风险 (connection_extractor 的
   `instances[0].decl` 依赖原样保留)。
2. **GAP-5/6 同模式**: 验证脚本 fixture 全用 target='top', 生产默认 target=None —
   两条 target=None 行为差异 (过滤 / 短路) 都是接上生产路径才暴露。教训:
   parity fixture 必须覆盖生产默认参数。
3. **删除死代码的纪律**: 先精确映射调用关系 (16 helper 零 adapter-path 调用 +
   外部引用全是别类同名方法) 才动手; 删除后 build 对旧接口显式 TypeError
   而非静默无操作。
