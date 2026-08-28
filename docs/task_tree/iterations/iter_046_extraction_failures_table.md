# Iteration 046: #4 建 EXTRACTION_FAILURES.md 集中表

**Metadata**:
- **Iteration #**: 046
- **Task Tree Level**: L1
- **Parent Task**: ARCHITECTURE_TODOLIST #4
- **Created**: 2026-08-28 21:45 GMT+8
- **Author**: 方豆 / DSH Agent
- **Outcome**: ✅ **成功** — 文档任务完成, 扫描全仓 fallback 模式并分类登记

---

## 🎯 本次目标

用户指令: **"继续"** → #4 建 `docs/EXTRACTION_FAILURES.md` 集中表。

背景: ARCHITECTURE_REVIEW 2026-08-27 §三.7 指出 "代码库有多少处 silent fallback?"
需要系统性登记, 不能靠"代码看像"。

---

## 🔬 全仓扫描结果 (2026-08-28)

| 模式 | 数量 | 判定 |
|---|---|---|
| `try/except + pass` (吞异常) | **113 处** | ⚠️ 大部分违规, 需逐点审查 |
| `fallback / 退化 / 兜底` 关键词 | **121 处** | ⚠️ 需区分设计 vs silent |
| `getattr(x, None/"")` (静默 default) | 37+ 处 | ⚠️ 部分合规 |
| `return None/[]/''` (sentinel) | 大量 | ✅ 合规 (显式契约) |

## 📋 分类体系 (5 类)

- **A: 合规** — 显式 sentinel + warning (NO_TREE_MARKER / Bug #2/#3 修复)
- **B: 待审查** — 113 处 try/except+pass, 其中 P0 是 4 处 `except Exception: pass`
- **C: 待审查** — 121 处 fallback 关键词 (elk_bridge 25 处最多)
- **D: 合规** — 显式 sentinel 返回 (get_signal → None 等)
- **E: 待审查** — getattr+default 37 处 (大部分合规, 关键路径需 warning)

## 🔗 关联已修 Bug

- **Bug #2/#3** (connection_extractor 端口方向): warning + extra 模式,
  作为"不能改行为但必须暴露问题"的标准参考
- **NO_TREE_MARKER** (coverage_generator): 作为"提取失败返回 sentinel"的正面标准

## 🛠️ 清理优先级

- P0: 4 处 `except Exception: pass` (native_adapter / coverage_models / compiler)
- P1: uvm_testbench 6 处 TypeError pass (加 logger.debug)
- P2: 113 处逐点审查
- P3: elk_bridge 25 处抽查

---

## 💡 关键发现

1. **113 处 try/except+pass 是最大存量** — 但**不是都违规**: 判定标准是
   "失败是否静默产出错误数据"。可选增强 (如 source_location) 可留 debug 日志。
2. **Bug #2/#3 的修复模式可复用** — warning + extra + 保持兼容行为,
   是"清理 silent fallback 而不破坏行为"的标准做法。
3. **文档本身是活文档** — 维护纪律要求新发现必须登记, 修一条移一条。
