# sv_query 项目位置与目录结构

---

## 1. 主目录 (USER_PROFILE.md 指定, 唯一工作目录)

```
~/my_dv_proj/sv_query/
```

**永远在这里工作。** 本机只存在这一个 sv_query 副本 ——
历史上的 `~/my_dvproj/` (有下划线) 别名目录**已不存在**, 不要再去那里找。

---

## 2. 目录结构

```
<PROJ_DIR>/sv_query/
├── run_cli.py                 # CLI 入口
├── pyproject.toml             # 项目配置 (pyslang>=10,<12 锁版本)
├── README.md                  # 用户文档
├── EXAMPLES.md                # 使用案例
├── docs/                      # 详细文档 (60+ 文件)
│   ├── INDEX.md                 # 索引 + 测试计数单一真相源
│   ├── USER_GUIDE.md
│   ├── EVIDENCE_FEATURE.md
│   ├── CLI_SURFACE.md
│   ├── EXP_IDEAS.md              # exp 创意清单 (已落地为 svq audit)
│   └── ...
├── src/
│   ├── cli/                   # CLI 命令 (typer-based)
│   │   ├── main.py              # 入口 + 命令注册
│   │   ├── _common.py           # 共用构建/错误处理
│   │   ├── _output.py           # JSON 输出 + 结构化失败
│   │   ├── _registry.py         # 命令注册表 (capabilities 契约来源)
│   │   ├── errors.py            # ErrorCode 枚举 (stable error_code 权威定义)
│   │   ├── _evidence_helpers.py # evidence 共享逻辑
│   │   ├── core/
│   │   │   ├── semantic/        # trace / dataflow / controlflow / verify
│   │   │   ├── locate/          # stats / search / graph / filelist
│   │   │   ├── state/           # snapshot
│   │   │   └── diagnose/        # exp diagnose
│   │   └── view/               # exp review render / architecture graph
│   └── trace/                 # 核心分析引擎
│       ├── unified_tracer.py     # 统一入口
│       └── core/
│           ├── _pyslang_compat.py  # [Stage 6] v10/v11 兼容层
│           ├── graph_builder.py    # 构建信号图
│           ├── semantic_adapter.py # pyslang semantic API 适配
│           ├── driver_extractor.py # driver 提取
│           ├── trace_evidence.py   # evidence + credibility_score
│           ├── analysis/audit.py   # audit 检查项 (exp)
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

## 3. 仓库 remote (没有 `origin`!)

```bash
cd ~/my_dv_proj/sv_query
git remote -v
# backup      https://github.com/fundou1081/sv_query.git (fetch/push)
# ssh-origin  git@github.com:fundou1081/sv_query.git      (fetch/push)
```

⚠️ **这个仓库没有 `origin` remote** —— `git push origin main` 会报
"No such remote 'origin'"。要推用:

```bash
git push backup main       # https
git push ssh-origin main   # ssh
```

---

## 4. 如何确认当前在哪

```bash
cd ~/my_dv_proj/sv_query
pwd
# /Users/fundou/my_dv_proj/sv_query

git remote -v
git log --oneline | head -3
# 看你最近的 commit

git status --porcelain
# 确认工作区干净 (且没有别的 agent 在改同一个文件)
```

---

## 5. 给 agent 的硬规则

1. **永远** `cd ~/my_dv_proj/sv_query` (本机只有这一个副本)
2. **永远** 先 `pwd && git status` 确认
3. **永远** 修改后跑测试 + commit
4. 推送用 `git push backup main` 或 `git push ssh-origin main` (**没有 origin**)
5. **不要** 在没确认的情况下改 `src/cli/_registry.py` 等别人正在编辑的文件
