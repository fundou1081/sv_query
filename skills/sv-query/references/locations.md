# sv_query 项目位置与目录结构

---

## 1. 主目录 (USER_PROFILE.md 指定, 唯一工作目录)

```
<PROJ_DIR>/sv_query/
```

**永远在这里工作, 不要去 `[agent-runtime-cache]/` (那个是 agent runtime cache)**

---

## 2. 目录结构

```
<PROJ_DIR>/sv_query/
├── run_cli.py                 # CLI 入口
├── pyproject.toml             # 项目配置 (pyslang>=10,<12 锁版本)
├── README.md                  # 用户文档
├── EXAMPLES.md                # 使用案例
├── docs/                      # 详细文档
│   ├── USER_GUIDE.md
│   ├── PYSLANG_COMPAT.md
│   ├── EVIDENCE_FEATURE.md
│   ├── CDC_ANALYSIS.md
│   └── ... (60+ 文件)
├── src/
│   ├── cli/                   # CLI 命令 (typer-based)
│   │   ├── run_cli.py
│   │   ├── _evidence_helpers.py  # evidence 共享逻辑
│   │   └── commands/
│   │       ├── trace.py
│   │       ├── dataflow.py
│   │       ├── controlflow.py
│   │       ├── cdc.py
│   │       ├── risk.py
│   │       ├── sva.py
│   │       ├── verify.py
│   │       ├── timing.py
│   │       ├── coverage.py
│   │       ├── visualize.py
│   │       ├── diff.py
│   │       ├── snapshot.py
│   │       ├── search.py
│   │       └── stats.py
│   └── trace/                 # 核心分析引擎
│       ├── unified_tracer.py     # 统一入口
│       └── core/
│           ├── _pyslang_compat.py  # [Stage 6] v10/v11 兼容层
│           ├── graph_builder.py    # 构建信号图
│           ├── semantic_adapter.py # pyslang semantic API 适配
│           ├── driver_extractor.py # driver 提取
│           ├── sva_extractor.py    # SVA 提取
│           └── visitors/
│               ├── constraint_visitor.py
│               └── signal_expression_visitor.py
├── sim/                       # 测试 + 仿真
│   ├── test_simple.sv
│   ├── test_cdc.sv
│   ├── TEST_REPORT.md
│   └── tests/
│       ├── regression/        # 回归测试
│       ├── integration/       # 集成 + 兼容测试
│       └── unit/              # 单元测试
├── examples/                  # 示例 .sv 文件
├── scripts/                   # 工具脚本
│   └── (LLM helper: <SKILL_DIR>/scripts/sv_analyze.py)
```

---

## 3. agent runtime cache (不要用)

```
[agent-runtime-cache]/sv_query/  # agent runtime cache (有下划线)
```

历史原因: agent runtime maps workspace 映射到 `[agent-runtime-cache]/` (有下划线), 但 USER_PROFILE.md 写的是 `<PROJ_DIR>/` (无下划线) 是真主目录。

**可能状态**:
- 内容可能比主目录新 (agent runtime auto-sync)
- 也可能比主目录旧 (用户手动改了主目录没同步)
- inode 不同, 不是 hardlink
- git remote 相同 (同一个 GitHub repo)

**规则**:
- 所有 sv_query 工作在 `<PROJ_DIR>/sv_query/`
- `[agent-runtime-cache]/sv_query/` 视为只读缓存
- 改完代码 `git push` 后, agent runtime cache会自动更新

---

## 4. 如何确认当前在哪

```bash
cd <PROJ_DIR>/sv_query
pwd
# <PROJ_DIR>/sv_query

git remote -v
# origin  https://<REPO_URL>.git

git log --oneline | head -3
# 看你最近的 commit
```

跟 `[agent-runtime-cache]/sv_query` 对比 (用 rsync / diff -rq):

```bash
diff -rq <PROJ_DIR>/sv_query [agent-runtime-cache]/sv_query 2>&1 | head
# 如果输出空 = 一致
# 如果有 "Only in" = 不同步
```

---

## 5. 给 agent 的硬规则

1. **永远** `cd <PROJ_DIR>/sv_query` 不去 `[agent-runtime-cache]/`
2. **永远** 先 `pwd && git status` 确认
3. **永远** 修改后跑测试 + commit
4. **永远** `git push` 同步到 GitHub (让 agent runtime cache自动更新)
5. **不要** 删 `[agent-runtime-cache]/sv_query` (它是 agent runtime workspace, 删了 agent won't see it)
