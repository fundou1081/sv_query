# Iteration 171: 文档清理与文档卫生 (A 路线第一项)

**Metadata**:
- **Iteration #**: 171
- **Task Tree Level**: L1
- **Parent Task**: L1_docs_cleanup (tasks/L1_docs_cleanup.md)
- **Created**: 2026-09-08 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (归档 63 份; 4 项检查全 0; 工具 + 纪律落地)

## 🎯 本次目标

方豆 "先进行A，先把文档清理。" — 处理全面回顾里的 P0 文档债 (膨胀 370 份 /
计数矛盾 / 死链 / 无机械化检查)。

## 📊 当前状态 / 预期结果

- 370 md;99 份 docs/ 平铺;3 份索引 (INDEX/DOC_INDEX/LLM_INDEX);
  计数在 15+ 处各写一份 (2958/3071/2009/2031...);代码注释引用已删文件。
- 预期: 归档过期稿 + 唯一索引 + 计数单一真相源 + 检查工具。

## 🔬 实际结果

**盘点** (脚本, 不凭感觉): 370 md = iterations 159 + docs 99 + archive 48 +
architecture 18 + tasks 17 + root 11 + refactoring 5 + sim 4 + 其他;零入链 119。

**归档 63 份 → `docs/archive/2026-09-08-cleanup/`** (git mv 保留历史;9 类原因
写入该目录 README): 可视化历史稿 13 / 计划重构稿 20 / 审计一次性报告 15 /
重复索引 2 / 专向参考稿 7 / 实验功能薄文档 4 / 重复 TESTING 1 / sim 旧报告 4 /
根目录过期设计稿 2。

**约束遵守**:
- 代码/测试引用的文档不打散: `docs/VIZ_DESIGN_SPEC.md` (viz_legend.py 引用),
  `docs/ARCHITECTURE_REVIEW_2026-07-15.md` / `CODE_DISCIPLINE_FIX_COMPLETENESS.md`
  (测试注释引用) — 归档后**同步更新引用路径** (4 处测试注释)。
- 链接改写脚本: 解析 md 内相对链接 → 指向归档目标时按新位置重写 (22 文件),
  归档内相对链接修复 11 处。

**新增 `tools/check_docs.py`** (4 项): ① 死链 ② 非归档文档引用归档路径
(历史日志豁免: iterations/memory/CHANGELOG/todolist/evolution) ③ docs/ 下
未登记 INDEX ④ 全量级计数 (≥1000) 与 INDEX 基线不一致 (分套件计数不算)。

**收敛结果**: 死链 37→0 / 归档越界 18→0 / 未登记 36→0 / 计数漂移 33→0。

**顺带修复的既有错误**:
- `docs/CONTROL_FLOW_DESIGN.md` 从不存在 (代码注释 2 处引用) → 改为 `CONTROL_FLOW.md`
- `pyproject.toml` 注释引用已删除的 `_pyslang_compat.py` → 改为 v11-only 说明
- 我自己在 iter_170 task 文件里的悬空规划引用 (`class_parameterized_plan.md`
  从未创建) → 改为指向 iter_170 记录
- `docs/TESTING.md` 与根 `TESTING.md` 重复 → 归档 docs 版 (AGENTS 设施表以根为准)

**纪律落地**: AGENTS.md v1.5 新增 "🧹 文档卫生" 5 条 (唯一入口 / 归档不删 /
计数单一真相源 / 历史快照豁免 / 提交前跑 check_docs.py)。

## 💡 关键发现 / 决策

- **文档债的可检测化才是根治**: 靠人肉记忆维护 370 份必然烂;4 条机器规则
  (死链/越界/登记/计数) 把"文档卫生"变成可 CI 的硬约束 — 这是本次最有价值的产出,
  归档本身只是一次性动作。
- **归档不删 + 引用重写 = 零信息损失**: 63 份全部 git mv (历史可追), 链接自动
  重写后无一处断链;比"删除+人工回忆"安全一个量级。
- **计数漂移的根因是"多处真相源"**: 之前每轮迭代都往文档里写 "N passed", 十几个
  数字必然互相矛盾。收敛到 INDEX 一节后, 历史快照 (迭代记录/CHANGELOG) 明确豁免。
- 检查器自身也要防误报: 目录链接/代码块伪链接 (`](node)`) 会假阳性 → 只查 .md 目标;
  AGENTS 里解释归档约定的路径也触发误报 → 改写表述而非放宽规则。
