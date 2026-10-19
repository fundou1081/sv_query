# AGENTS.md — sv_query 协作规则 (流程)

> **强制**。本文件只写"怎么做"，细则与背景全部外链。
> 细则: [DISCIPLINE](docs/dev/DISCIPLINE.md) · [CODING_STYLE](docs/dev/CODING_STYLE.md) · [WORKFLOW](docs/dev/WORKFLOW.md) · [CHECKLIST](docs/dev/REVIEW_CHECKLIST.md)
> 导航: [文档索引](docs/INDEX.md) · [当前任务](CURRENT_TODO.md) · [测试](TESTING.md) · [已知限制](docs/KNOWN_LIMITATIONS.md)

## 0. 恢复上下文 (压缩 / 新 session 必做)

1. 本文件 → 2. [CURRENT_TODO.md](CURRENT_TODO.md) → 3. [DISCIPLINE.md](docs/dev/DISCIPLINE.md)
→ 4. 最近 10 个 commit + [overview](docs/task_tree/overview.md) 末尾 3 行

禁止凭残留印象继续工作。

## 1. 铁律 (违反任一条 = 停手、回滚、报告方豆)

1. **禁 `--no-strict`** — 命令失败要诊断根因，不许开逃生口
2. **禁 silent fallback** — 失败必须显式：报错 / sentinel / 抛异常
3. **禁 `except ...: pass`** — 吞异常让"失败"与"正常"不可区分
4. **禁 `-f` / `--file` 传 filelist** — filelist 一律 `--filelist`（误用触发原生 SIGTRAP）
5. **失败按序归因** — fixture → 功能代码 → filelist → 环境 → (最后) 工具自身 bug
6. **不改用户的 RTL / 工程文件** — 写能力只进 `tools/`，且默认关闭
7. **`core` 层只读** + JSON + 稳定 schema（消费者是 agent）
8. **同一语义只允许一份实现** — 发现两份就合并或删除，不要"分别对齐"
9. **降级必须显式** — 实验能力进 `exp/` 并在 `capabilities` 降级，不伪装稳定
10. **登记缺陷写可观察后果** — 什么输入 → 什么错误输出，按输入形态枚举

## 2. 任务流程

- **开工**（缺一步不动手）：建 `docs/task_tree/tasks/L<N>_<任务>.md` → 更新 [CURRENT_TODO.md](CURRENT_TODO.md)
  → 挂到 [overview](docs/task_tree/overview.md) → 写可验证的 sub-task
- **迭代**：一个迭代 = 一个可观察动作，各自写 `docs/task_tree/iterations/iter_NNN_*.md`
  （**边做边写**，失败也如实写；迭代号只增不减）
- **收尾**：`CURRENT_TODO` 移入"最近完成" + `overview` 加汇总行 + 新文档登记 [INDEX](docs/INDEX.md)
  + 计数只改 INDEX 的"当前基线"
- **完成判定**：**代码 ✅ + 测试 ✅ + 文档 ✅**。只做完代码就说"完成" = 谎报进度

## 3. 提交前必跑 (全部 0 退出码)

```bash
python3 -m pytest sim/tests/ -m "not opensource" -q -p no:randomly   # 全量门禁
python3 tools/check_docs.py                                          # 死链/归档/未登记
python3 tools/check_except_pass.py                                   # 禁 except:pass
python3 tools/check_cli_layers.py                                    # CLI 分层 R1~R8
python3 tools/gen_cli_surface.py --check                             # CLI 清单一致
git status --porcelain                                               # 只含预期改动
```

涉及查询 / 图 / CLI 语义的改动，**额外**跑真实多文件项目冒烟（[WORKFLOW §4](docs/dev/WORKFLOW.md)）。
逐项自检见 [REVIEW_CHECKLIST](docs/dev/REVIEW_CHECKLIST.md)。

## 4. 汇报与协作

- **主动告知**：缺测试 / 更好的架构 / 更好的方案 / 登记过的局限实际更严重
  → 按 **现状 → 问题 → 建议 → 代价** 说，然后等方豆拍板
- 大改动（架构 / 重构 / 换算法）**先说后做**；小而安全的改动可直接做，但要在总结里列出
- 决策冲突（用户指示 vs 代码事实、新决策 vs 旧决策）→ **停下确认**，不默默照做也不默默改
  （[CODING_STYLE §11](docs/dev/CODING_STYLE.md)）

## 5. 设施位置

设施与"唯一位置"表见 [WORKFLOW §0](docs/dev/WORKFLOW.md)。
**禁止**新建 `records/` `logs/` `notes/` 等与表内重复的平行目录。

## 6. 版本

- **v2.1 (2026-10-19)** — 精简为纯流程规则（≤100 行），设施表移入 [WORKFLOW](docs/dev/WORKFLOW.md)；
  方豆指示："只用规则，维持精简，其他都 link 出去"
- v2.0 (2026-10-19) — 522 行拆为入口 + `docs/dev/` 四份细则；新增产品不变量 I1~I5
- v1.0~v1.7 历史见 `git log -- AGENTS.md`
