# Iteration 221: 逐文件改造 — 文件 1/N `handshake.py` (含唯一位置实参)

**Metadata**:
- **Iteration #**: 221
- **Task Tree Level**: L1 (纪律强制 · 逐文件执行)
- **Parent Task**: 方豆 "逐文件修改, 全改" (方案 A)
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ 文件 1 完成且全量**改善** (34 → 32 failed)

## 🎯 本次目标

按方案 A **逐文件**彻底移除 `strict`。首个文件选 `handshake.py` —— 它含**全仓唯一的
位置实参** (iter_219 工具定位), 是验证"逐文件方法"的最佳试点。

## 🔬 实际结果

### 改动 (只改这一个文件)

AST 精确区间删除:
- **形参 2 处**: `_build_tracer(...)` 第 3 参数 / `_scan_internal(...)` 第 5 参数;
- **关键字实参 6 处**: 3× `_build_tracer(..., strict=...)` / 2× `UnifiedTracer(..., strict=...)`
  / 1× `_scan_internal(..., strict=...)`;
- **位置实参 1 处** ⚠️: `handshake.py:311` 的 `_scan_internal(..., strict)` (第 5 个位置);
- 残余 `if strict:` → `if True:`。

### 验证 (逐文件配方, 全部通过)

| 检查 | 结果 |
|---|---|
| `python3 -c ast.parse` | ✅ |
| `scan_strict.py` 该文件 | **0 剩余** |
| 冒烟 `handshake scan` / `handshake analyze` | **rc=0** (含位置实参那条调用链) |
| handshake 相关测试 (4 文件) | **297 passed / 13 skipped** |
| **全量 canonical** | **32 failed / 3284 passed** ← 比批次 2 的 **34 failed 改善 2 个** |

**关键**: 全量失败数**下降** (34 → 32) —— 说明 `strict` 移除在修正真实问题
(此前有 2 个失败正是被"降级路径"掩盖的)。

## 💡 关键发现 / 关键技术 / 决策

1. **"逐文件一次提交"是可行且正确的节奏**: 对比此前 5 次"一次改一层"全部回退,
   本次单文件: 改动面小 → 工具可复测 → 冒烟/相关测试/全量三层验证 → 一次通过。
2. **位置实参是真实存在的坑**: `handshake.py:311` 用位置传 `strict`; AST 表驱动定位后
   精确删除, `_scan_internal` 的位置参数不再错位 —— 这正是 iter_218 (116 failed) 的
   怀疑根源, 本次在小范围内被安全处理。
3. **验证顺序有效**: ast.parse (语法) → scan_strict (形态) → 冒烟 (运行时) →
   相关测试 (语义) → 全量 (回归), 五层各挡一类问题。
4. **全量失败数作为"进度指标"**: 每改一个文件后应记录全量失败数; 上升即回退该文件。
   当前基线 **32 failed** (含 16 可视化暂缓)。

## 📢 下一个文件

按 `scan_strict` 的 Top 列表继续 (每文件一次提交 + 五层验证):
`visualize.py`(21) → `trace.py`(15) → `controlflow.py`(9) → `randomize.py`(9) →
`sva.py`(8) → `coverage.py`(7) → `snapshot.py`(7) → ... → `_common.py` → tools/ →
**最后** `src/trace` 的核心 `self._strict` (语义分支, 单独设计)。

## 📎 关联

- 工具: `tools/scan_strict.py`; 方案: `iter_220` 战略结论 (方案 A)
- 备份: `/tmp/src_b4` (本文件改动前状态)
