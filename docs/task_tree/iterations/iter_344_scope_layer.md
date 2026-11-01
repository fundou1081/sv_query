# Iteration 344: capabilities mode + scope aggregate（PLAN P44）

**Metadata**:
- **Iteration #**: 344
- **Task Tree Level**: L2（PLAN `P44.2/P44.3`）
- **Created**: 2026-11-01 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "更新文档，按优先级做"）
- **Outcome**: ✅ 完成（mode/scope；2696 passed）

## 🎯 定位调整

产品方向明确：
- Scope = 入口/上下文（够用即可）
- Trace/Verify = 核心价值

## 🔧 实现

### capabilities mode

- 每命令新增 `mode`：scope/trace/verify/locate/state/exp；
- 映射见 contract 文档。

### scope 聚合

新增 core `scope <path>`：
- module_type/parent/children；
- ports（canonical_id/internal_signal）；
- parameters；
- 支持顶层模块 path（MIG 没有 top instance 时用 adapter topInstances）；
- 标准 envelope；unknown 显式错误。

## 🧪 测试

- `test_scope.py` 4：详情/canonical、顶层 children、unknown、capabilities mode；
- 契约 +1：scope_result/port/param/child；
- 全量 **2696 passed / 0 failed**。

## ⚠️ 边界

- scope 顶层 ports 从 adapter port declarations 取，internal 以 `path.port` 表示；
- scope 不做 fanin/fanout，连接仍用 `connections`；
- 后续 scope 只补 interface/generate/class 可发现性，不再扩语义。

## 🔗 相关

- 计划: [PLAN.md P44.2/P44.3](../../../PLAN.md)
- 产品方向: [product_direction_2026-10-31](../../architecture/product_direction_2026-10-31.md)
