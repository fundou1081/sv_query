# Iteration 173: adapter 拆解方案稿 (含回归测试计划) — 待拍板

**Metadata**:
- **Iteration #**: 173
- **Task Tree Level**: L1
- **Parent Task**: L1_adapter_split (tasks/L1_adapter_split.md)
- **Created**: 2026-09-08 GMT+8
- **Author**: AI 助手
- **Outcome**: 📋 方案稿交付 (待方豆拍板 D1-D4)

## 🎯 本次目标

方豆 "接下来拆 semantic，做好方案和我讨论。包括回归测试计划。哪些改动用哪些
测试来确保。" — 先出方案, 不动代码。

## 📊 当前状态 / 预期结果

- A 路线前两项 (文档清理 iter_171 / 缓存目录 iter_172) ✅。
- 预期: 基于实测的诊断 + ≥2 方案 + 分步验证 gate + 区域→测试映射。

## 🔬 实际结果 (诊断实测)

1. **发现比"拆文件"更值钱的问题**: `core/base.py` (2,341 行) = ASTWalker +
   PyslangAdapter (2,067 行) + 3 个 Collector — 在 **src/ 从未实例化**
   (`grep 'PyslangAdapter(' src/` = 0), 只有 8 处**类型注解** + 4 个回归测试
   直接实例化 (1,546 行)。运行时唯一 adapter = `SemanticAdapter`。
   2026-07-15 V2 清理删了 `core/pyslang_adapter.py` (158 行) 却漏了 base.py 这层。
2. SemanticAdapter 3,049 行 / 77 方法 / 42 个外部调用 (≈150 调用点); 消费者
   driver(21)/connection(19)/function(18)/load(15)/clock(11)/bitselect(10)/class(9)…
3. 7 个 ≥100 行条目 = 1,239 行 = 40%, 头号是 **474 行
   `_extract_signals_from_expr`** (还被 13 处外部调用); 33 个方法零外部调用。

## 📋 方案 (见 docs/architecture/semantic_adapter_split_plan.md)

- 拆成两件事: **P-A** base.py 死层处置 (A1 删 / A2 半删 / A3 标注) +
  **P-B** SemanticAdapter 分域 (B1 mixin 零调用方改动 / B2 显式依赖 / B3 机械搬运)
- 推荐: P-A=A1 (先做 legacy 测试等价矩阵), P-B=B1 起步 (可演进 B2),
  474 行巨函数单列 Step 3
- 路线 Step 0-10, 每步 1 commit + 全绿 + 可回滚; **Step 0 = API 面冻结测试**
  (77 方法名 + inspect.signature) 作安全网; 零改名策略
- 回归映射: 6 个 mixin 域各有"快 gate + 深 gate"两档; 基线 unit 1112 /
  unit+regression 2059 / cli+integration 739 / truth 19 文件;
  计数只增不减; golden 需重生成即停下报告

## 💡 关键发现 / 决策

- **先诊断再拆**: 原以为任务是"3,049 行拆 6 个文件", 实测发现真问题是
  "两套 adapter 并存, 其中一套 2,341 行已死" — 不做这一步就去拆活文件, 等于
  在错误的病灶上花两天。
- **安全网优先**: API 面冻结测试必须**第一个做** (Step 0) — 42 个外部方法 /
  150 调用点是本次重构唯一真正的风险面, 有了机制保护, 之后每步都能快速判断
  "有无行为变化"。
- **既有守卫测试的先例**: V2 的 `test_no_pyslang_adapter_legacy.py` 就是防重现
  的机制 — 本次删除后应把它扩展到 base.py (防止 legacy 层回来)。
