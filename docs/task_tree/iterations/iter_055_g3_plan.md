# Iteration 055: G3 计划 — pyslang 11.0 native API 替换计划文档

**Metadata**:
- **Iteration #**: 055
- **Task Tree Level**: L1
- **Parent Task**: ARCHITECTURE_TODOLIST #7 迁 pyslang 11.0 native API
- **Created**: 2026-08-29 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (G3 计划文档交付, 待方豆确认 D1-D3)

## 🎯 本次目标

方豆 "先1, 写 g3 计划文档" — ARCHITECTURE_TODOLIST #7 子任务:
"G3 计划: 替换点 + 风险 + 回退策略"。

## 📊 当前状态 / 预期结果

option A 完成 (iter_053/054): GAP-1/2 修, GAP-3/4 拍板接受。G3 计划需要回答:
**替换点到底在哪、分批怎么排、风险、回退**。

## 🔬 实际结果

### 探索结论 (先探索后决策)

1. **MIG.build 已半 native**: SemanticAdapter path (生产唯一路径) 的
   hierarchicalPath/portConnections/端口方向位宽 **已直接读 pyslang symbol** —
   todolist 的"分批" (先 hierarchicalPath, 再 portConnections, 再 body) **实际上已完成**。
   真正剩余的替换点 = **实例枚举** (`semantic_adapter.get_module_instances()` 递归 walk)。

2. **SyntaxTree path (Phase 0-2 + `_iter_children` 5 处) 是死代码**: 无生产调用
   (唯一 MIG.build 调用方 unified_tracer.py:516 传 adapter), 无测试调用。

3. **`get_module_instances()` 有 5 个生产调用方**: MIG / unified_tracer:935 /
   graph_builder:373 / connection_extractor:123,147。其中 connection_extractor:183/283
   读 `inst.instances[0].decl.name.value` — **_NativeInstanceWrapper 没有 `.instances`**,
   wrapper API 不完全兼容 (全量切换的前置工作)。

4. **POC 已实证**: `sim/tests/poc/test_portconn_native_poc.py` (darkriscv native
   portConnections) **5 passed**; Phase 1 记录性能 265ms → 60ms; benchmark 工具链就绪。

### 交付物

`docs/architecture/pyslang11_native_api_g3_plan.md`:
- 现状盘点 (替换点映射表)
- **方案对比**: A 全量切 (get_module_instances 内部) / B 只切 MIG / **C 推荐 (B 先行 A 后续)**
- 实施细节: 阶段 1 改动点 = MIG.build L136 一处 + 验证矩阵 + 已接受差异清单 (GAP-3/4)
- 风险清单 R1-R6 (含 R2 connection_extractor 重复计数、R5 6 项目 strict 编译阻塞)
- 回退策略 (单点 revert + verify_native_parity.py 门禁 + baseline 存档)
- **待方豆拍板 D1-D3**

## 💡 关键发现 / 关键技术 / 决策

1. **计划要根据现状写, 不是照抄 todolist**: 原 todolist "分批" 假设 MIG 全自建,
   实测 hierarchicalPath/portConnections 早已在用 — 替换点只剩实例枚举。计划据此收敛。

2. **两阶段 (B 先行 A 后续) 的理由**: MIG-only 切换爆炸半径最小且门禁现成
   (verify_native_parity.py 就是 MIG 四表 A/B); 全量切换需要先补 wrapper API
   (`.instances` 等) + 核实 R2 — 分两次小爆炸而非一次大爆炸。

3. **wrapper API 契约是方案 A 的关键约束**: `SemanticInstanceWrapper` 的
   `.instances`/`.parent`/`get_parent_module()`/数组 name 回退, native wrapper 缺 —
   直接切会让 connection_extractor:183/283 崩。这是"先探索"才发现的, 若不探索直接
   按测试文档 L4-13 原计划切, 会踩坑。

## 📌 待方豆确认

- D1: 方案 C (B 先行 A 后续) 是否同意
- D2: 阶段 1 (MIG-only 切换) 是否现在开工 (接受 R5: 6 项目回归暂不可跑)
- D3: R2 (get_generate_instances 重叠) 是否单独修
