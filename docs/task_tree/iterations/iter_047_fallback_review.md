# Iteration 047: B/C/E 三类 fallback 逐点审查

**Metadata**:
- **Iteration #**: 047
- **Task Tree Level**: L1
- **Parent Task**: ARCHITECTURE_TODOLIST #4 (EXTRACTION_FAILURES.md 后续)
- **Created**: 2026-08-28 21:50 GMT+8
- **Author**: 方豆 / DSH Agent
- **Outcome**: ✅ **成功** — 36 违规 / 55 合规 / 20 边界, 审查结论已入文档

---

## 🎯 本次目标

用户指令: **"审查 b c e"** → 对 EXTRACTION_FAILURES.md 里分类 B (try/except+pass)、
C (fallback 关键词)、E (getattr default) 做逐点审查。

---

## 🔬 审查方法

先尝试 3 个 subagent 并行审查 (每组 30-45 处), 但 3 个都因输出过长/工具问题
失败。**改用脚本自审**: 提取全部 113 处的 (文件:行号 | 异常类型 | try 上下文 | 前后行),
批量判定 + 关键处抽查上下文。

---

## 📊 审查结果

### 分类 B: 113 处 try/except+pass → 111 处判定 = **36 违规 / 55 合规 / 20 边界**

**违规 36 处** (Exception 过宽 + 数据提取路径, 失败静默丢数据):
- `class_graph_builder.py` (7) — 类约束/成员提取 — **最高危**
- `graph_builder.py` (6) — 图构建
- `load_extractor.py` (7) — 端口/参数
- `sva_extractor.py` (5) — SVA 信号
- `compiler.py` (5) — source_location
- `semantic_adapter.py` (4) — 端口/成员 + Exception 冗余
- `native_adapter.py` (1) — Exception 包揽冗余

**合规 55 处** (防御/可选/sentinel/有注释):
- dataflow NetworkX 无路径 / _dot_common 资源清理 / _common 常量折叠 sentinel
- uvm_testbench / call_graph / covergroup / sva 的 TypeError 跳过 (有注释)

**边界 20 处** (有防御意图但无日志): 建议加 logger.debug

### 分类 C: 121 处 fallback 关键词 = 绝大多数有意设计

- ~85% 有意设计 (优先路径 + fallback helper, 注释明确)
- ~10% 显式 sentinel (NO_TREE_MARKER)
- ~5% 需注意 (driver_extractor:450 filelist mutex)

**无系统性违规。**

### 分类 E: 163 处 getattr+default = 绝大多数合规

- ~95% 防御性 AST 遍历 (kind/name → "")
- ~4% 属性名兼容 (or 链)
- ~1% 需注意 (base.py:521 direction 缺省)

**合规。**

---

## 💡 关键发现

1. **subagent 不适合超长输出审查** — 3 个 subagent 都因输出过长失败。
   改用脚本提取 + 人工判定更可靠。
2. **"违规"的判定核心**: Exception 过宽 (except Exception) + 数据提取路径 +
   无日志 = 三重信号。三者齐备才判违规, 避免误伤防御性代码。
3. **清理优先级已更新**: P0 是 class_graph_builder (约束数据丢失最危险) +
   graph_builder + load_extractor + native_adapter/compiler。

---

## 📌 下一步

- 按 P0-P3 优先级逐步清理 36 处违规 (每次加 logger.warning 或收窄异常)
- 20 处边界加 logger.debug (低成本)
