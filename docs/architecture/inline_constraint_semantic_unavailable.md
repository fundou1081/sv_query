# Architecture Decision: Inline Constraint (randomize-with) 语义不可达 — 暂缓, 文档化维护

**Status**: 🔒 **DECIDED** (2026-09-03 方豆拍板: "先不做 inline 分析, 结论记录下来用一个文档维护, 业务未来会有改善")
**Owner**: 方豆 / AI 助手
**Scope**: class/constraint 子图提取域 (inline 约束); 兼 SVA/过程体域 syntax-vs-semantic 边界
**Affects**: `class_graph_builder.py` (未改 — 无代码变更), `sva_extractor.py` (iter_121 已修, 本决策解释其 syntax 属性), 未来 inline-constraint 提取

---

## 📌 Context (为什么有这个决策)

1. 对抗验证 (方豆 "constraint covergroup sva") 发现 backlog #7: `it.randomize() with { x > 5; }`
   inline 约束不产 CONSTRAINT 节点 (named `constraint c {}` 正常)。
2. iter_123/124 专项尝试 3 版 (广语义遍历 / 定向窄扫 / 全语法扫) — 全部受阻;
   深挖出 pyslang 环境脆弱性 (syntax 遍历结果依赖进程内 import 顺序)。
3. 方豆质疑方法论: "为什么用 syntax? 不是 semantic?" — 要求先确认 semantic 侧可行性 (不可妥协)。
4. **验证结论: inline 约束在 pyslang 语义侧没有信息 (非 API 用法问题, 是语义模型固有不对称)**。
5. 方豆裁决: 暂缓 inline 分析, 结论落档维护, 未来业务改善时再启。

## 🔬 验证证据 (2026-09-03)

全语义树 kind 盘点 (源码同时含 named + inline 约束):

| 观测 | 值 | 含义 |
|---|---|---|
| `SymbolKind.ConstraintBlock` | **×1** | 只有命名的 `constraint c {...}` (class 成员) 建符号 |
| `StatementKind.List/Block` | ×9 / ×1 | 过程体语句是 **StatementKind** (非 SymbolKind) — 语义树不把语句/表达式细化成 symbol |
| inline 块 (randomize-with) | **0 符号** | slang 语义阶段不给调用点 inline 约束建任何 symbol (属调用上下文, 求值期处理); SymbolKind 无 Randomize/InlineConstraint 类 |

即: pyslang v11 语义树 = 声明/作用域级符号 (Class/ClassProperty/Subroutine/ConstraintBlock/ContinuousAssign/ProceduralBlock...), **procedural 语句体内部只以语法节点 + 惰性符号引用存在**。声明级约束有符号、调用点 inline 约束没有 — **固有不对称**。

## 🎯 Decision (locked)

### D1. Inline (randomize-with) 约束 — 语义提取不可行, 暂缓整体分析

- **原因 (明确)**: 语义树无该信息 (见证据) — 不是 API 不会用; syntax 是唯一入口,
  但受 pyslang import-order 环境 bug 制约 (见下), 且 syntax 方案会产生 iter_121 式
  症状补丁。方豆拍板暂缓, 未来业务改善后再评估。
- **不做什么**: class_graph_builder 不改; inline 约束保持"无 CONSTRAINT 节点"现状
  (named 约束完整可用)。

### D2. 方法论边界正式记录: "Semantic-only" (2026-08-26 D1) 的作用域

- 2026-08-26 case27 决策 D1 "用 Semantic API only, 不用 Syntax" 针对 **RTL 顶层
  提取域** (assign/always/端口/generate 结构)。
- **本决策正式划定例外域**: SVA property/sequence 信号列表、断言语句、procedural
  内部、inline 约束 — 语义树无符号 → 既定 **hybrid** (syntax 取文本 + semantic 做
  符号级校验/消歧)。iter_121 即在该域内。

### D3. iter_121 的 4 个 syntax 症状补丁 → 未来 semantic 消歧改进点 (非推翻)

formal 当信号 / 函数当信号 / local var 当信号 / 参数不替换 — 本质是符号解析问题。
语法层靠"节点型语境猜型"修补; 未来更干净: syntax 取标识符后, 用语义符号 kind
(Net vs Function vs Parameter vs LocalAssertionVar) 消歧。列入维护清单。

## 📌 方案考量 (≥2)

| 方案 | 做法 | 结论 |
|---|---|---|
| A semantic 硬做 | 从语义树找 inline 约束符号 | ❌ 不可行 — 无符号 (证据) |
| B syntax 提取 | 全语法扫 + receiver 类解析 | ⚠️ 可行但: ① pyslang import-order env bug (同进程 import 顺序改变 syntax 遍历结果 — d1 mutex 同族) ② 语义消歧仍缺 → 症状修 |
| **C 暂缓 + 文档维护** (选) | 现状保持 (named 约束可用), 结论/证据/观察点落档 | ✅ 采纳 (方豆) |

## 🔭 未来改善观察 (业务改善时启动的信号)

1. **pyslang 升级**: slang 若把 inline 约束建成符号 (ConstraintBlockSymbol 覆盖
   调用点 / 新增 Randomize 语义节点) → 语义提取立即可做, 无需 syntax。
2. **pyslang import-order env bug 修复**: alias bridge 注册时序稳定后, syntax
   路径可用 → 可做 syntax+semantic 消歧分层 (标识符 → symbol kind 区分
   函数/参数/信号/local)。
3. **iter_121 症状补丁 → semantic 消歧重构**: 用 symbol kind 替代节点型猜型
   (SVA 4 项)。
4. **复核 D2 边界**: SVA/procedural/inline 是否随 pyslang 演进回归纯语义。

**复现与证据**:
- 复现: `/tmp/adv_verify.py` (CONSTRAINT-inline), `/tmp/adv_probe.py`
- iter_121/122/123/124 迭代记录 + CURRENT_TODO backlog #7
