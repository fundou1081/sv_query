---
name: sv-query
description: SystemVerilog RTL 静态分析 CLI (sv_query)。当用户问 RTL 验证 / "这个信号谁驱动" / "找 CDC 路径" / "信号风险评分" / 给 .sv 文件让 agent 分析时使用。命令: trace (fanin/fanout/evidence), dataflow, cdc, risk, sva, verify。核心: evidence 返回源码位置 + credibility_score (0-1, <0.7 需人工确认)。LLM 友好 (4 个关键 flag + 13 种 stable error_code, 见 references/llm-mode.md)。只支持 pyslang v10/v11。
---

# sv-query

SystemVerilog RTL 信号追踪查询引擎 CLI 工具 (`sv_query` 项目)。

> 项目位置: `<PROJ_DIR>/sv_query` (USER_PROFILE.md 主目录, 唯一工作目录)
> 主入口: `python3 run_cli.py <command> [subcommand] [options]`
> 测试: 全量基线见 [docs/INDEX.md](../../docs/INDEX.md) (含 pulp_axi 5 个 xfail for low-memory machine (<16GB) 环境限制), v10/v11 100% 双版本兼容
> 依赖: `pyslang>=10.0.0,<12.0.0` (含 `_pyslang_compat.py` shim 桥接 v10/v11 差异)

## ⚠️ 安装占位符配置 (重要)

使用此 skill 前, 请将本文档中的占位符替换为你的实际路径:

| 占位符 | 含义 | 示例 |
|--------|------|------|
| `<PROJ_DIR>` | sv_query 项目父目录 | `~/projects` 或 `~/work` 或 `/opt/dev` |
| `<REPO_URL>` | sv_query GitHub 仓库 URL | `https://github.com/YOUR_USER/sv_query.git` |
| `<SKILL_DIR>` | 本 skill 安装路径 | `~/.claude/skills/sv-query/` |
| `<PROJ>` | 你要分析的项目名 | `my_rtl_design`, `cva6`, `picorv32` 等 |

### 配置示例

将 `<PROJ_DIR>/sv_query` 全文替换为你的真实路径, 例如:
- 你的路径: `~/projects/sv_query` → `<PROJ_DIR>` = `~/projects`
- 你的路径: `/opt/dev/sv_query` → `<PROJ_DIR>` = `/opt/dev`

### `scripts/sv_analyze.py` 配置

脚本默认 `<PROJ_DIR>` = `~/projects` (Linux/macOS 通用约定)。如需修改:

```bash
# 方法 1: 环境变量 (推荐, 不改源码)
export SV_QUERY_DIR=/path/to/your/sv_query

# 方法 2: 改源码 (永久)
# 编辑 scripts/sv_analyze.py line ~40, 改 Path.home() / "projects" / "sv_query" 为你的路径
```

### `scripts/sv_analyze.py` 安装路径

```bash
# 默认在 <SKILL_DIR>/scripts/sv_analyze.py
# 例: ~/.claude/skills/sv-query/scripts/sv_analyze.py

# 可复制到任何 PATH 目录:
cp <SKILL_DIR>/scripts/sv_analyze.py /usr/local/bin/
```

---

## 何时使用

当用户:

- 问"这个信号谁驱动的 / 哪里被读" → `trace fanin/fanout`
- 给一个 `.sv` 文件, 想做静态分析 → 主入口 `run_cli.py`
- 要做 CDC 检查 → `cdc analyze`
- 要做数据流追踪 → `dataflow analyze`
- 要做风险评分 → `risk analyze`
- 要找 SVA / 验证缺口 → `sva` / `verify gap` (见 references/commands.md)
- 要把分析结果跟源码位置对齐 → 加 `--evidence` 标志

## 辅助脚本

`scripts/sv_analyze.py` 是给 LLM agent 用的 Python helper (5 种常用模式: trace/fanin/evidence/dataflow/risk/cdc/verify), 自动加 `--json -q --max-results 50`, 输出可直接 `json.loads()`:

```python
import sys
sys.path.insert(0, "<SKILL_DIR>/scripts")
from sv_analyze import trace_evidence
result = trace_evidence("sim/test.sv", "top.data")
# result 是 dict, 自动处理 error_code 分类
```

或 CLI:
```bash
python3 <SKILL_DIR>/scripts/sv_analyze.py sim/test.sv top.data --mode evidence
```

## 何时不使用

- 用户要的是 lint / 编译 / 仿真: 用 Verilator / Icarus, 不是 sv_query
- 用户要综合 / 物理设计: sv_query 只做静态分析
- 用户已经在用别的 RTL 分析工具 (Verible, Surelog, etc.): 不切

---

## 快速开始 (30 秒)

```bash
cd <PROJ_DIR>/sv_query

# 1. 看命令
python3 run_cli.py --help

# 2. 跑一个 trace, 贴 evidence
python3 run_cli.py trace evidence -f sim/test_simple.sv top.data

# 输出:
#   Signal: top.data
#   Source: 'data = din;'

# 3. 跑风险分析, 拿完整 evidence JSON
python3 run_cli.py risk analyze -f sim/test_simple.sv --evidence --json | python3 -m json.tool
```

---

## 工作流程 (4 步)

### Step 1: 定位项目 + 验证环境

```bash
cd <PROJ_DIR>/sv_query

# 确认项目在 (USER_PROFILE.md 主目录, 不是 agent runtime cache [agent-runtime-cache]/)
test -f run_cli.py && test -f pyproject.toml && echo "OK" || echo "MISSING"

# 确认 v10/v11
python3 -c "import pyslang; print(f'pyslang {pyslang.__version__}')"
# 期望: 10.0.0+ 或 11.0.0+
```

如果项目位置不对, 立刻告知用户 (见 [references/locations.md](references/locations.md))。

### Step 2: 选择命令 (top 5)

参考 [references/commands.md](references/commands.md) 完整决策树。

| 用户问题 | 命令 |
|---------|------|
| 谁驱动 X / 给我 X 的源码 | `trace evidence X` (95% 用例) |
| 谁读了 X | `trace fanout X` |
| X 怎么到 Y | `dataflow analyze X Y` |
| 跨时钟域问题 | `cdc analyze` |
| 信号风险评分 | `risk analyze` |

其他 9 个命令 (impact/controlflow/timing/sva/coverage/diff/visualize/snapshot/search) 见 references/commands.md。

### Step 3: 跑命令 + 读 evidence

所有带 `--evidence` 的命令返回 2 种格式:

1. **text 模式 (默认)**: 每条结果下方 1 行 `Source: '...';`
2. **JSON 模式 (--json)**: 每条 result 包含 `evidence.source_text` (单行摘要) 和 `evidence.source_range` (start_line/end_line) 字段

证据可信度 (`credibility_score`):
- `1.0`: 直接 always/initial 块内赋值 → 最可信
- `0.9`: 嵌套 block (always 里的 if) → 高可信
- `0.7-0.8`: 跨函数/模块间接驱动 → 中可信
- `<0.5`: 推测性来源 → 低可信, 需人工确认

### Step 4: 解读 + 反馈

- 高可信 (≥0.9): 可以直接作为结论
- 中可信 (0.7-0.8): 报告用户, 让他判断
- 低可信 (<0.7): **必须**告知用户"来源不确定, 需要人工检查" + 给 source_range 让人看具体行

---

## 关键技术细节

4 步工作流程 + credibility/evidence 机制 + constraint 速查见 [references/workflow.md](references/workflow.md).
## 实际项目分析 (工业案例)

实战案例见 [references/cases/](references/cases/).

## 测试 / 验证 (修改项目时)

```bash
# 全量
cd <PROJ_DIR>/sv_query
python3 -m pytest sim/tests/ -q
# 期望: 全量 passed (计数以 [docs/INDEX.md](../../docs/INDEX.md) 为准; 含 7 xfail/xpass for low-memory machine (<16GB) 环境限制)

# 双版本 smoke
python3 -m pytest sim/tests/integration/test_pyslang_version_compat.py -v
```

详细命令参考 → [references/commands.md](references/commands.md)
完整 evidence 字段说明 → [references/evidence.md](references/evidence.md)
pyslang v10/v11 兼容详情 → [references/pyslang-compat.md](references/pyslang-compat.md)

---

## 给 agent 的关键约束

1. **永远** 在 `<PROJ_DIR>/sv_query/` 工作, 不用 `[agent-runtime-cache]/` (那是 agent runtime cache)
2. **永远** 加 `--evidence` 在做信号分析时 (用户没指定时默认加, 哪怕只 text)
3. **永远** 把 `credibility_score < 0.7` 的 evidence 标注为"需人工确认"
4. **永远** 报告 evidence 失败的命令 (例如找不到信号, JSON `ok=false`)
5. **不要** 改 sv_query 内部代码除非用户明确要求 (这是用户维护的项目, 改完要测试 + commit)
6. 跑命令前先 `cd <PROJ_DIR>/sv_query`, 工作目录不对会报 "no such file"

### LLM agent 额外约束

7. **永远** LLM 调用时加 `--json -q` (--quiet 抑制 stderr 警告污染 JSON)
8. **永远** 用 `error_code` 字段分类错误, **不要** 解析 `error` 字符串
9. **永远** 检查 `result.truncated` 字段 (--max-results) 决定是否需要扩大查询
10. **永远** `--summary` 用于 LLM 上下文窗口紧张时 (cdc/risk 返回 top-10 + counts)
11. **永远** 验证 JSON 输出符合 `tools/llm_schema.json` (LLM 框架函数调用)
12. 优先用 evidence + error_code 决策, **不要** 重复尝试命令 (会浪费 token)
13. filelist 解析问题 (axi_pkg 排序, common_cells transitive dep) 不是 sv_query bug, 是 sv 输入工程问题
14. **分析大项目 (84+ files)** 先从 2 module 开始验证 elaboration 干净, 再渐进扩大
15. **不要** 把 .svh 加到 filelist (sv_query 不预处理 \`include, 反而引入新错误)
16. **永远** 排除 `*_tb.sv` 从 filelist (testbench 拖慢且引入 include 错误)"
