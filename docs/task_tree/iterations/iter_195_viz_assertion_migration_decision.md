# Iteration 195: viz 断言迁移"决策就绪"整理 + 上游 issue 文本

**Metadata**:
- **Iteration #**: 195
- **Task Tree Level**: L2 (测试语义 / 决策准备)
- **Parent Task**: iter_188 的 13 个 skip (方豆 "继续")
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ 决策就绪 (未改任何断言 — 迁移属产品语义决策)

## 🎯 本次目标

iter_188 把 Ventus viz 套件的 14 failed 转成 0 failed + **13 个明确 skip**, 但那 13 条
的迁移需要"可视化语义"决策。本轮**不改断言**, 只把每条的原意图 vs 当前输出能否验证
**实测清楚**, 变成可拍板的表。

## 🔬 实际结果

实测方法: 跑生成器产出 artifact → 在 SVG 文本里搜原断言依赖的标记
(`stroke-dasharray` / 文本关键词 / 颜色 / `<polygon>` / 宽高比)。

| 结论 | 条数 | 说明 |
|---|---|---|
| ✅ 可直接迁移 | 3~4 | chain 异常类 (SVG 有 `<polygon>` + `#cc8800` + 图例文本 X_DRIVER/DANGLING/ORPHAN); trace 的 "0 loads" 应改为断言 **stdout** |
| ⚠️ 需先定产品语义 | 7~8 | pipeline 的阶段/控制簇/方向 (SVG 里**无** "stage"/"control" 文本)、timing 的 critical path 高亮 (SVG 里**无** "critical") |
| 🔧 需先补 CLI 能力 | 2 | `visualize pipeline` **没有 `--png`** (只有 chain 有) |

**额外发现 (重要)**: 原 `rankdir=LR` 断言早已不成立 —— 当前 pipeline 产物宽高比
**0.28 (竖版)**。也就是说这批断言里至少有 1 条在 V100 之前就已经和实际输出脱节,
不能简单当成"改名导致的失效"。

**根因归纳**: 同一 CLI 内 `--dot` 有**三种语义** —— `visualize module` 输出 DOT、
`visualize pipeline/chain` 输出 SVG、`trace` 根本没有 `--dot` (改
`--format dot --output`)。这是这批断言集体失效的根因。

交付: `docs/architecture/ventus_viz_assertion_migration.md` (逐条表 + 三个待决问题:
pipeline/timing 产品契约 / 是否统一 viz 输出 flag / PNG 能力)。

**同时整理**: `docs/task_tree/iterations/iter_189_addsyntaxtree_sigtrap_guard.md`
追加"可直接提给上游的 issue 文本" (标题/环境/5 行复现/期望 vs 实际/我们在项目里的
workaround), 方豆决定是否提交。

## 💡 关键发现 / 关键技术 / 决策

1. **"决策就绪"本身是交付物**: 13 个 skip 卡在"要不要重写断言"这个产品问题上;
   把每条的原意图 + 当前输出证据列成表, 决策成本从"重新读 500 行测试"降到"看一张表"。
2. **不要按实现反推契约**: pipeline/timing 的断言应该由"图该表达什么"决定, 而不是
   看渲染器碰巧输出了什么。所以这类**必须**方豆定语义, 我不擅自重写。
3. **旧断言可能本来就错**: `rankdir=LR` 实测宽高比 0.28 (竖版) → 提醒: 迁移时不能
   假设"旧断言 = 曾经正确的契约"。

## 📢 待方豆决定

见 `docs/architecture/ventus_viz_assertion_migration.md` 末尾三问; 另有 push (23 commit)、
`check_regression.py` 阈值、上游 issue 是否提交。
