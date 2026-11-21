# P193.2 asset inventory and migration rules

> **状态**: 清单/规则，**未移动任何文件**。
> **来源**: 2026-11-21 external trial review
> **目标**: 主仓库只留契约、验证报告、用户文档；开发日记/协作记录移出。
> **日期**: 2026-11-21

## 1. 当前资产

| 路径 | 大小 | 文件数 | 内容 | 建议 |
|---|---:|---:|---|---|
| `agents/` | 1.9 MB | 194 | worker tasks/handoffs/iterations/reviews | 私有归档 |
| `memory/` | 68 KB | 10 | 开发记忆/日记 | 私有归档 |
| `docs/task_tree/` | 3.3 MB | 708 | 历史任务树/迭代记录 | 私有归档 |
| `docs/sessions/` | 12 KB | 1 | 会话记录 | 私有归档 |
| `docs/archive/` | 4.0 MB | 316 | 历史清理文档 | 私有归档 |
| `docs/refactoring/` | 56 KB | 6 | 重构过程记录 | 私有归档 |
| `docs/lessons/` | 72 KB | 1 | 经验记录 | 私有归档 |
| `docs/debugging_lessons/` | 52 KB | 3 | debug 过程记录 | 私有归档 |
| `scripts/debug/` | 16 KB | 4 | 一次性调试脚本 | 私有归档 |
| `.dsh/` | 4 KB | 1 | benchmark 旁路 skill | 私有归档 |
| `.claude/` | 20 KB | 4 + symlink | 内部 agent 规则 | 私有归档 |
| `.agents/skills/{add-component,code-cleanup,debug-fault}` | ~20 KB | 3 | 内部开发 skill | 私有归档 |
| `.agents/skills/query-protocol/` | ~16 KB | 2 | 对外 query 协议 | **保留** |
| `docs/validation/` | 4.6 MB | 319 | 真实验证证据 | **保留，脱敏** |
| `docs/images/` | 6.8 MB | 60 | 文档图片 | 保留/压缩 |

`docs/dev/` 需要拆分：

- 保留：`SEMANTIC_CONTRACTS`、`CLAIMS`、`ENVELOPE_*`、`COMMAND_SURFACE_RATCHET`、`BIT_SELECT_HINTS`、`REPO_HYGIENE`、`CODING_STYLE`、`PROJECT_ADAPTATION`、`SNAPSHOT_SURFACE`；
- 归档：`HANDOFF*`、`REPORT_STATUS`、`WORKFLOW`、`DISCIPLINE`、`REVIEW_*` 等内部流程。

## 2. 必须先决策：git 历史

**只 `git rm` 不够。**

当前公开 GitHub 仓库的旧 commit 仍包含：

- agent 协作记录；
- 本机绝对路径；
- 内部讨论。

外部 clone 默认会拉取完整历史，即使工作树已删除。

可选方案：

### A. 新公开仓库（推荐）

- 用当前干净工作树创建 `sv_query-public` 新仓库；
- 只导入保留文件，创建新的初始历史；
- 旧仓库转私有/归档；
- PyPI 项目、README 链接、GitHub Actions 重新指向新仓库。

优点：历史彻底干净；缺点：stars/issues/releases 迁移，工作量大。

### B. 重写当前仓库历史

- `git filter-repo` 删除私有路径/替换作者信息；
- force push；
- 所有 collaborators 重新 clone。

优点：保留仓库 URL；缺点：破坏历史，风险高。

### C. 只清工作树

- `git rm` + 新 commit；
- 旧历史仍可访问。

**不满足隐私目标**，只适合确认旧历史无敏感内容的情况。

## 3. 迁移规则（待批准后执行）

1. 在仓库外创建：
   ```text
   ../svq-internal-archive/2026-11-21/
   ```
2. 用 `cp -a` 保留完整文件，再 `git rm -r`；
3. 不删除外部归档，不加入主仓库；
4. 更新：
   - `AGENTS.md` 中 `.claude` / `.agents` 引用；
   - `docs/INDEX.md` 中 task_tree/sessions/archive 行；
   - `KNOWN_LIMITATIONS` 中 task_tree/`.dsh` 引用；
   - README / USER_GUIDE 的链接；
5. 全仓 `~`、`/home/`、`C:\Users\`、token 扫描；
6. `check_docs --strict` + `check_plan` + 全量测试；
7. `git archive`/clean clone 验证没有私有文件与绝对 symlink；
8. CI 增加隐私扫描 gate。

## 4. 需要脱敏的保留文档

当前 `~` 命中（全仓 115 文件），主要集中在：

```text
docs/validation/       42
docs/archive/          31
docs/task_tree/         8
docs/dev/               3
docs/debugging_lessons/ 1
docs/lessons/           1
docs/sessions/          1
```

迁移后仍需处理：

- `docs/validation/P187_*` 和 `p187_cva6_*` 中的绝对路径；
- `docs/USER_GUIDE.md`、`CONTROL_FLOW.md`、`EVIDENCE_FEATURE.md`、`FILELIST.md` 等；
- `tools/verify_native_parity.py` / `tools/smoke_real_projects.py` 的本机默认路径；
- `tools/fix_hardcoded_paths.py`（迁移工具本身含路径样例）→ 私有归档。

## 5. 外部链接影响

- `AGENTS.md` 是当前 agent 入口，含 `.claude`/`.agents` 路由；迁移后需改成公开 contributor guide 或保留精简版；
- `docs/INDEX.md` 是文档真相源，必须同步删除/改写被归档条目；
- `KNOWN_LIMITATIONS` 引用的 iter 文档需改成摘要或指向私有归档说明；
- 已发布 PyPI 包不包含这些目录，但 GitHub 仓库是外部第一入口。

## 6. 验收

```text
主仓库无 agents/ memory/ docs/task_tree/ docs/sessions/ docs/archive/
主仓库无 ~
主仓库无绝对 symlink
clean clone 可安装 + pytest 绿
docs/INDEX 无死链
CI 隐私 gate 绿
```

## 7. 待确认

请先选择历史策略：

```text
A. 新公开仓库（推荐）
B. 重写当前仓库历史
C. 只清工作树（不满足隐私目标）
```

确认后再执行文件移动。
