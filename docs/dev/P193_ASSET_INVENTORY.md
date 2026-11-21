# P193.2 privacy / public asset policy

> **状态**: 公开仓库已裁剪并重写历史；私有资产与旧历史在 `sv_query_private`。
> **日期**: 2026-11-21

## 公开仓库保留

- `src/` / `sim/tests/` / `tools/` / `config/` / `examples/`
- `README.md`、`LICENSE*`、`CHANGELOG.md`、`RELEASE.md`
- `AGENTS.md`、`CONTRIBUTING.md`、`TESTING.md`、`PLAN.md`
- `docs/USER_GUIDE.md`、`docs/KNOWN_LIMITATIONS.md`、`docs/INDEX.md`
- `docs/dev/` 中契约、gate、编码/查询协议文档
- `docs/architecture/`、`docs/validation/` 中的公开证据
- `.agents/skills/query-protocol/`

## 已移入私有归档

```text
agents/  memory/  docs/task_tree/  docs/sessions/  docs/archive/
docs/refactoring/  docs/lessons/  docs/debugging_lessons/
scripts/debug/  .dsh/  .claude/
.agents/skills/{add-component,code-cleanup,debug-fault}/
docs/dev/{HANDOFF*,REPORT_STATUS,WORKFLOW,DISCIPLINE,REVIEW_*}
tools/fix_hardcoded_paths.py
```

私有归档：

```text
https://github.com/fundou1081/sv_query_private
```

## 规则

- 不把个人路径、开发日记、worker 协作记录提交到公开仓库；
- 不在公开仓库新增绝对路径 symlink；
- 隐私扫描：
  ```bash
  git grep -n '/Users/' || true
  python3 tools/check_repo_hygiene.py
  ```
- 历史重写后，公开仓库只从干净根继续提交。
