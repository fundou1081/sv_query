# L1: adapter 层拆解 (base.py 死层 + SemanticAdapter 分域)

> **Created**: 2026-09-08 GMT+8
> **Status**: ✅ **CLOSED (iter_174~177)** — Step 0-10 全部完成; 移出代替删除 — 方豆 "接下来拆 semantic，做好方案和我讨论。包括回归测试计划。"
> **方案文档**: [semantic_adapter_split_plan.md](../../architecture/semantic_adapter_split_plan.md)

## 诊断要点 (实测)

- `core/base.py` (2,341 行: ASTWalker + PyslangAdapter + 3 Collector) 在 src/ **从未
  实例化** — 仅 8 处类型注解 + 4 个回归测试直接实例化 (1,546 行测试)
- `core/semantic_adapter.py` (3,049 行 / 77 方法 / 42 个外部调用) 是唯一运行时 adapter
- 7 个 ≥100 行条目占 40%, 含 474 行 `_extract_signals_from_expr` (13 处外部调用)
- 33 个方法零外部调用 (含明显死 API)

## 待决策 (D1-D4)

D1 base.py 死层本次删除? (建议删, 需先做 legacy 测试等价矩阵)
D2 拆分方式 B1 mixin (建议) vs B2 显式依赖
D3 474 行巨函数是否一并拆 (建议一并)
D4 opensource 套件纳入哪些 gate (建议 Step 2 + 收尾)

## 路线 (Step 0-10)

0 API 面冻结测试 → 1 legacy 等价矩阵 → 2 删 base.py → 3 拆巨函数 →
4-9 逐域 mixin 搬迁 (source/classes/ports/connections/exprs/modules) →
10 死 API 清理 + 文档

详见方案文档 §3/§4 (分步验证 gate 与 区域→测试 映射表)
