# Iteration 084: B 组收尾 — TESTING.md 环境验证手段 (方豆 "接下来b")

**Metadata**:
- **Iteration #**: 084
- **Task Tree Level**: L1
- **Parent Task**: Test_Assets_ABC → B 组收尾 (环境假象文档化)
- **Created**: 2026-09-01 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (B 组环境问题正式文档化, 后人不再误判)

## 🎯 本次目标

方豆 "接下来b" — B 组主体已在 iter_082 完成 (2 断言修复 + 12 环境定性)。
剩余收尾: 把"沙箱 cache 不可写导致 CLI 测试假失败"的验证手段写进 TESTING.md,
避免后续 session/人重复误判。

## 📊 当前状态 / 预期结果

- iter_082 发现: 12 个 integration 失败全是 `~/.svq/cache` 不可写 (HOME 限制),
  可写 HOME 下 integration 417 passed + 5 skipped, 0 failed
- 但 TESTING.md 无此记录 — 后续跑测试看到这些失败会误判为回归
- 预期: TESTING.md 已知限制表 + 验证方法节

## 🔬 实际结果

TESTING.md 更新:
1. **已知限制表** 新增行: `~/.svq/cache` 不可写 (沙箱/受限 HOME) 🔴 env (iter_082)
2. **新增小节** "沙箱 / 受限环境验证手段 (iter_082 定型)":
   - 根因: `ast_cache.py:30 CACHE_DIR = Path.home() / ".svq" / "cache"`
   - 影响面: human_output / tree_output / real_project_viz / trace_include_flags 等
     所有 run_cli.py subprocess 测试
   - 验证命令: `HOME=/tmp/svq_home python3 -m pytest sim/tests/integration -q`
   - 判定原则: 失败含 Operation not permitted → 先排除环境, 再判真回归

## 💡 关键发现 / 决策

1. **环境问题的文档化 = 防误判投资**: 一次记录, 避免每次 session 把 12 个假失败
   当回归排查 (iter_080 我就差点误判 integration baseline)。
2. **只记文档不改代码**: cache 路径可配置化 (env var) 是另一种方案, 但动 src/
   功能代码成本高、收益低 — 沙箱限制是工具环境特有, 本机/CI 无此问题。
   记录验证手段足够。

## 📌 状态

- ✅ TESTING.md 更新 (已知限制 + 验证手段)
- 提交: TESTING.md + 本记录
