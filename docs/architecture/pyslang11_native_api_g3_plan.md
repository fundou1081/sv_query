# G3 计划: pyslang 11.0 native API 替换 (ARCHITECTURE_TODOLIST #7)

> **时间**: 2026-08-29 GMT+8
> **作者**: AI 助手
> **前置**: option A 验证完成 (iter_053/054) — 发现 2 个 native 缺陷 (GAP-1/2, 已修) +
> 2 个已接受差异 (GAP-3/4); 方豆拍板 "按 1 做" (native 更正确 = bugfix 接受, 输出变化 OK)
> **状态**: 计划待方豆确认 (D1-D3), 确认后进入实施

---

## 0. 遇到的问题 (为什么现在写 G3)

ARCHITECTURE_TODOLIST #7 目标是 "用 `inst.hierarchicalPath` / `inst.portConnections` /
`inst.body` 替代自建 MIG"。option A (diff 验证) 已完成, 等价性结论已齐:

- **GAP-1/GAP-2** (native 缺陷) 已修 → 常规场景 native 与递归**完全一致**
- **GAP-3/GAP-4** (native 更正确) 已拍板接受 → 切换后 MIG 输出会变 (增加嵌套 generate
  实例 / conditional-generate parent 更完整), 下游 6 项目回归会出现差异

现在需要一份**可执行的替换计划**: 替换点在哪、分批怎么排、风险、回退。

---

## 1. 现状盘点 (探索结果, 2026-08-29)

### 1.1 MIG.build 的真实结构 — 已半 native

`src/trace/core/module_instance_graph.py` 有**两条并行路径**:

| 路径 | 入口 | 状态 |
|---|---|---|
| **SemanticAdapter path** (L133-231) | `MIG.build(adapter)`, 生产**唯一**调用方 `unified_tracer.py:516` | ✅ 活跃。实例枚举走递归 `semantic_adapter.get_module_instances()`; 但 `hierarchicalPath` / `portConnections` / 端口方向位宽 **已经直接读 pyslang symbol** |
| **SyntaxTree path** (Phase 0-2, L233+) | `MIG.build(trees_dict)` | ☠️ **死代码** — 无生产调用、无测试调用。含 `_iter_children` (5 处)、`_get_parent_path`、`_find_all_hierarchy_instantiations` 等一整条 AST 字符串 kind 匹配实现 |

### 1.2 todolist "分批" 与现状的映射 — 实际只剩一个替换点

| todolist 分批 | 现状 | 结论 |
|---|---|---|
| 先 hierarchicalPath | MIG.build 已用 (L143) | ✅ 已完成 |
| 再 portConnections | MIG.build 已用 (L153) + POC 实证 (`sim/tests/poc/test_portconn_native_poc.py`, darkriscv, **5 passed**) | ✅ 已完成 |
| 再 body | MIG.build 已用 | ✅ 已完成 |
| **(实际剩余的替换点) 实例枚举** | `semantic_adapter.get_module_instances()` 递归 walk (L282-409) | ⬅️ **真正的 G3 替换点** |

### 1.3 get_module_instances() 的 5 个生产调用方

| 调用方 | 用途 | 切换影响 |
|---|---|---|
| `module_instance_graph.py:136` | MIG.build 实例列表 | 核心目标 |
| `unified_tracer.py:935` | list_instances (走 `_parse_instance_node` 的 SyntaxTree 分支: 读 `.type.value` + `.name`) | wrapper 需有 `.type.value`/`.name` ✓ native 有 |
| `graph_builder.py:373` | 收集 target 子树路径 (只读 `._symbol.hierarchicalPath`) | ✓ native 有 |
| `connection_extractor.py:123/147` | root module 判定 + 端口映射 (读 `.type.value` / `.parent_module` / `._symbol.hierarchicalPath`) | ✓ 兼容; ⚠️ 见 R2 |
| `connection_extractor.py:183/283` | **读 `inst.instances[0].decl.name.value`** | ⚠️ **native wrapper 没有 `.instances`** — 见方案 A 的 wrapper 补齐 |

### 1.4 wrapper API 差异 (方案 A 的关键约束)

`SemanticInstanceWrapper` (semantic_adapter.py:2465) 有:
`name` (含数组元素 arrayName+arrayPath 回退)、`type`、`parent_module`、
**`instances`** (= [SemanticInstanceDeclWrapper])、`get_parent_module()`、
`_get_parent_module_safe()`、`parent` 属性。

`_NativeInstanceWrapper` (native_adapter.py) 只有: `_symbol`、`parent_module`、`type`、`name`。
**缺**: `instances`、`get_parent_module()`、`_get_parent_module_safe()`、`parent`; 且
`name` 对数组元素返回空串 (SemanticInstanceWrapper 有 arrayName 回退)。

---

## 2. 方案对比 (≥2, 含推荐)

### 方案 A: 全量切换 — `semantic_adapter.get_module_instances()` 内部改调 native

即 Phase 1 测试文档 (test_native_adapter_parity.py L4-13) 原本设计的路径:
"如果一致 → 可以安全切换 semantic_adapter.get_module_instances() 内部"。

- **利**: 单一枚举真源; 5 个调用方统一受益 (嵌套 generate / conditional-generate 行为一致);
  不引入"两套枚举并存"的长期不一致
- **弊**: 需补齐 `_NativeInstanceWrapper` API (`instances` decl wrapper、`parent`、
  `get_parent_module()`、数组 name 回退) — 触碰返回类型契约, 工作量 + 回归面;
  5 个调用方行为**同时**变 (虽然都是已接受的 GAP-3/4 变化);
  `connection_extractor` 的 `get_module_instances() + get_generate_instances()` 潜在
  重复计数问题 (R2) 会在切换后放大

### 方案 B: 只切 MIG — `MIG.build` 直接用 `native_adapter.get_module_instances_native`

- **利**: 爆炸半径最小 — MIG 只用 `_symbol` / `parent_module` / `get_module_name`,
  wrapper 兼容已被 verify_native_parity.py 在 MIG 四表层面实证; 改动 ≈ MIG.build L136 一处;
  回退 = 一行 revert
- **弊**: 其余 4 个调用方保持递归 (两套枚举并存); 嵌套 generate 实例只在 MIG 里出现,
  connection_extractor / graph_builder 看不到 → 不一致会持续存在

### 方案 C (推荐): B 先行 → 验证 → A 后续 (两阶段)

**阶段 1 (本轮)**: 方案 B — MIG.build 切 native
- 改动单点、门禁现成 (verify_native_parity.py = MIG 四表 A/B)、风险可控
- 产出: MIG 全 native + 全套回归 + (一旦 6 项目可编译) 等价性实测 + 性能 benchmark

**阶段 2 (单独决策)**: 方案 A — `get_module_instances()` 全量切 native
- 前置: 补 `_NativeInstanceWrapper` 全 API + 单测; 核实 R2 (get_generate_instances 重叠)
- 顺带: 删除 SyntaxTree 死代码 (Phase 0-2 + `_iter_children` 5 处) — 减维护面
- 理由: 阶段 1 的 MIG 回归数据 = 阶段 2 的风险样本; 分两次小爆炸, 而不是一次大爆炸

---

## 3. 实施细节 (阶段 1)

### 3.1 改动点

`module_instance_graph.py:136`:
```python
instances = adapter.get_module_instances()   # 递归
# ↓ 改为
if hasattr(adapter, "_root"):
    instances = get_module_instances_native(adapter._root, adapter._target_module)
else:
    instances = adapter.get_module_instances()  # 防御: 非 SemanticAdapter 保持旧行为
```
- `SemanticAdapter` 已有 `_root` / `_target_module` 私有属性 (读, 不写)
- MIG.build 其余代码 (hierarchicalPath / portConnections / get_module_name) 零改动 —
  因为 wrapper 接口 (._symbol / .parent_module) 两种枚举一致

### 3.2 验证矩阵 (阶段 1 完成判定)

| 项 | 手段 |
|---|---|
| MIG 四表等价门禁 | `python tools/verify_native_parity.py` — 已接受差异清单 (GAP-3/4) 不得扩大 |
| 单元 | `pytest sim/tests/unit -q` (baseline: 4 failed = 沙箱 cache artifact) |
| CLI | `pytest sim/tests/cli -q` (baseline: 20 failed = 沙箱 cache artifact) |
| truth | `pytest sim/tests/test_case27_1to1_truth.py -q` (4 passed) |
| integration | 13 pre-existing failed baseline, 不得新增 |
| 真实项目 | 6 项目 strict 编译修复后跑 `verify_native_parity.py --all` (R5 阻塞中) |
| 性能 | `tools/benchmark/run_benchmark.py` 复测 (Phase 1 记录: CVA6 265ms → 60ms) |

### 3.3 已接受差异清单 (切换后 MIG 输出 vs 切换前, 不得扩大)

| ID | 差异 | 方向 |
|---|---|---|
| GAP-3 | 嵌套 generate: 递归漏 4 个实例, native 找全 | 输出**增加**实例 (bugfix) |
| GAP-4 | conditional-generate parent: 递归 `top` (丢 generate 段), native `top.enable_block` | parent 字段变化 |

---

## 4. 风险清单

| ID | 风险 | 影响 | 缓解 |
|---|---|---|---|
| R1 | GAP-3/4 输出变化 → 下游 6 项目回归 diff | 中 (已接受) | 切换前存档全套 baseline + 6 项目 MIG 快照; diff 只允许 GAP-3/4 形态 |
| R2 | `connection_extractor` 的 `get_module_instances() + get_generate_instances()` — 递归枚举**已含** generate 实例, 潜在重复计数 | 低 (现有行为, 非切换引入) | 阶段 1 前核实; 若已重叠, 作为独立 bug 记录, 不阻塞阶段 1 |
| R3 | 阶段 2 wrapper API 缺属性 (`.instances` 等) 导致 connection_extractor:183/283 崩 | 高 (若直接切 A) | 阶段 1 只切 MIG (不读 `.instances`) 规避; 阶段 2 前补全 API + 单测 |
| R4 | MIG.build 读 SemanticAdapter 私有属性 `_root`/`_target_module` | 低 | `hasattr` 防御 + 非 SemanticAdapter 保旧路径 |
| R5 | 6 项目 strict 编译不通过 → 真实项目等价性/回归不可跑 | 中 (子任务 1 前置) | 阶段 1 用 fixtures + 全套测试兜底; 编译修复独立推进 |
| R6 | 性能未验证 | 低 | 阶段 1 末跑 benchmark (工具链已就绪) |

---

## 5. 回退策略

1. **单点回退**: 阶段 1 是 MIG.build 一处改动 → `git revert` 即可, 无状态残留
2. **门禁**: `tools/verify_native_parity.py` MIG 四表 + 已接受差异清单 (GAP-3/4) 为唯一
   等价性契约; 任何后续改动必须维持该清单不变 (新增差异 = 显式记录 + 方豆确认)
3. **baseline 存档**: 切换前 (commit 前一版) 全套测试输出 + 6 项目 MIG 快照, 存
   `docs/architecture/` 或归档目录, 供 diff 追溯

---

## 6. 待方豆拍板

- **D1**: 方案 C (阶段 1 = MIG-only 切换, 阶段 2 = 全量切换 + 死代码删除) 是否同意?
- **D2**: 阶段 1 是否现在开工? (需确认接受 R5: 6 项目回归暂时不可跑, 用 fixtures+全套测试兜底)
- **D3**: R2 (get_generate_instances 与 get_module_instances 重叠) — 阶段 1 前核实,
  若确重叠, 是否单独修 (不阻塞阶段 1)?

---

## 7. 参考

- iter_053: option A 验证脚本 + 3 差异发现
- iter_054: GAP-1/2 修复 + GAP-3/4 拍板
- `tools/verify_native_parity.py`: MIG 四表 diff 脚本
- `sim/tests/poc/test_portconn_native_poc.py`: native portConnections POC (darkriscv, 5 passed)
- `sim/tests/unit/test_native_adapter_parity.py`: 13 passed, 0 xfail
