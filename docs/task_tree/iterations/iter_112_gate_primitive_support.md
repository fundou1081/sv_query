# Iteration 112: 门级原语 (Gate Primitive) 提取支持 — leaf cell 建模

**Metadata**:
- **Iteration #**: 112
- **Task Tree Level**: L2 (openrtl 工业算法摸底 → 缺口修复)
- **Parent Task**: [tasks/L2_gate_primitive_support.md](../tasks/L2_gate_primitive_support.md)
- **Created**: 2026-09-03 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功

## 🎯 本次目标

修复摸底发现的**门级原语缺口**: KoggeStone-BrentKung (纯门级加法器) 的
`xor xor0(S[0], A[0], B[0])` 结构 — xor16.S[0..15] 全无 DRIVER + pg16 的
and/xor 实例触发 ConnectionExtractor 无限递归 (`BrentKung.and0.and0...` ×21)。
方豆拍板方案 A: 原语建模为 leaf cell。

## 📊 当前状态 / 预期结果

- 修复前: xor16.S 16 bit 无人驱动 ("谁驱动 S[0]" 无答案); connection 递归
  假节点污染图
- 预期: 门输出 = 隐式连续赋值, 每个输入端子 → 输出 DRIVER 边 (与 assign
  二元操作数约定一致); 原语不再当模块实例展开

## 🔬 实际结果

### 根因链 (iter_112 前调查, 详见任务文件)

1. pyslang 门原语 kind = `SymbolKind.PrimitiveInstance` — 无 definition/body/端口
2. native 实例枚举用 `'Instance' in kind` **子串匹配** → 原语被当模块实例
3. PrimitiveInstance 的 wrapper `.type.value` = **实例名自己** ('and0') →
   connection_extractor inst_module_name 解析 (def 空 → type==inst_name) 回落到
   `_get_parent_module_name` → inst_module_name == parent_module → get_path
   parent 匹配到它自己 → 无限递归被 `depth>20` 截断 → `top.and0.and0...` ×21
4. driver 侧原语无 assign 语义对象 → 输出永远无人驱动

### 修复 (4 处, 全根因层)

| # | 文件 | 改动 |
|---|---|---|
| 1 | `native_adapter.py` | `PrimitiveInstance` 显式过滤 (walk body / generate block / array elem) — recursive 参照实现 (精确匹配) 本就不收, 过滤即对齐 parity |
| 2 | `semantic_adapter.py` | `get_generate_instances` 两处 `'Instance' in kind` 排除 PrimitiveInstance; 新增 `get_primitive_instances(module)` + `get_primitive_genvar_context()` (遍历同 get_assignments, 下钻 generate, 记 genvar ctx) |
| 3 | `driver_extractor.py` | 新增 `_create_primitive_edges` (两处 extract 循环调用): portConnections[0].left = 输出端子, [1..] = 输入端子 → 每输入端子 DRIVER→输出 (宿主模块作用域, `_get_signal` 带 genvar ctx 解析) |
| 4 | `connection_extractor.py` | get_path 防自环兜底 (`other_info is info` 跳过) — 原语已过滤, 此 guard 兜底同类自匹配 |

### 验证

- pg2-in-top 复现: instances `['u1']` (原语不再枚举), 递归节点 0,
  `top.u1.a0 ← A[0]/B[0]` (and0) + `top.u1.x0 ← A[0]/B[0]` (xor0) 进图
- 真实 KoggeStone-BrentKung (target=BrentKung, 143 instance paths):
  `BrentKung.xor16_1.A[i]/B[i] → S[i]` ×32 条实例作用域门边;
  xor16 独立 top: S[0..15] 全部可达驱动 (修复前 0)
- generate-for 内门: Y[i] ← A[i]/B[i] 逐 entry 展开 (genvar ctx 替换)
- 新测试: unit `test_gate_primitive.py` (8) + truth `test_gate_primitive_truth.py`
  (6, fixture golden_dataflow_40_xor16_gate.v = 真实 xor16.v) — 14 passed
- 定向回归 45 passed; native parity 8 EQUIVALENT + 2 已接受 GAP (基线一致)
- 全量回归 (非 usage) 后台跑完: 见下方状态

## 💡 关键发现 / 决策

1. **子串匹配是万恶之源**: `'Instance' in kind` 三处 (native walk / generate /
   generate_instances) 全部把 PrimitiveInstance 误收 — 过滤必须三处同步 +
   recursive 参照一致, 否则 parity 破。
2. **leaf cell 语义 = 隐式连续赋值**: 门输出 DRIVER 边与 assign 二元操作数
   完全同构 (X^Z → X,Z 各驱动 Y), "谁驱动 S[0]" 答 A[0]/B[0] — 零新概念,
   复用现有解析 (get_signal + genvar ctx + 宿主作用域)。
3. **门无自身作用域**: 输出落在宿主模块 (原语无 body) — 与模块实例输出走
   实例端口节点不同, 这是 leaf cell 的本质差异。
4. **剩余观察 (非本次范围)**: BrentKung.S 顶层位仅总线级 CONNECTION (实例输出
   → 父总线), 位级驱动解析依赖既有 cross-module 语义 — 与 pg2 场景一致,
   属既有设计; 位级 CONNECTION 展开是独立特性, 另议。

## 📌 状态

- ✅ 代码 + 测试 (unit 8 + truth 6) + 本文档; 全量回归结果见 commit 时
- 任务文件: docs/task_tree/tasks/L2_gate_primitive_support.md
