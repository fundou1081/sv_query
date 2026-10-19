# 开发纪律 (Development Discipline)

> **本文是 `AGENTS.md` 的细则文件之一。** 入口/索引见 [AGENTS.md](../../AGENTS.md)。
> **状态**: 强制执行 — 违反任何一条 = 立即停止、回滚、向方豆报告。
> **适用**: 所有在本仓库工作的 AI 助手 (QClaw / Claude Code / Copilot / DeepSeek Harness 等) 与人类开发者。
> **最后修订**: 2026-10-19 (v2.0, 从 AGENTS.md 拆出并按近半年教训补强)

---

## 🧱 0. 产品级不变量 (最高优先级 — 高于任何实现偏好)

这几条不是"建议", 是产品承诺。改变它们 = 改变产品定义, 必须先问方豆。

| # | 不变量 | 含义 | 违反的后果 |
|---|---|---|---|
| I1 | **不修改用户的 RTL / 工程文件** | sv_query 是**只读分析工具**。任何写入能力只能放在 `tools/` 下的独立脚本里，且默认 `--apply`/`--write` 关闭 | 用户源码被污染，工具失去可信度 |
| I2 | **`core` 层只读 + JSON + 稳定 schema** | `core` 的消费者是 **agent**；输出契约可以加字段，不能改语义 | 下游 agent 静默出错 |
| I3 | **单一实现原则** | 同一个语义只允许有一份实现；发现第二份 → 合并或删除，**不要两份都留着"对齐"** | 两份必然分叉 (见 §5 的两个真实案例) |
| I4 | **降级必须显式** | 实验性能力放进 `exp/` 并在 `capabilities` 里降级；不得伪装成稳定能力 | 用户以为能用，实际给错答案 |
| I5 | **登记缺陷必须写清可观察后果** | 写"某个 API 不支持 X" 不够，要写"什么输入 → 什么错误输出" | 后人按错误描述去修，漏掉真正的缺陷 (案例见 §5) |

不变量 I2/I4 的落地细节见 [CLI_SURFACE.md](../CLI_SURFACE.md) 与 [EXP_NAMESPACE.md](../EXP_NAMESPACE.md)；
能力边界见 [KNOWN_LIMITATIONS.md](../KNOWN_LIMITATIONS.md)。

---

## 🚫 1. 禁止 `--no-strict`

**绝对禁止**在 `run_cli.py` / 测试 / 脚本中使用 `--no-strict` 标志。

**理由**: 它是早期为了对不完整 RTL/elaboration 报错做 graceful degradation 留下的逃生口，
会掩盖真实的质量问题 (空 graph、节点缺失、expr tree 拿不到)，让 debug 变得不可能。

**命令在 strict 模式下失败时**，不要加开关让它"能跑"，按 §4 的顺序诊断根因：

- 测试源码 (fixture) 有语法/语义错误 → 修 fixture
- 功能代码有 bug → 修 src
- filelist 不完整 → 补 filelist
- 环境不匹配 (pyslang / Python 版本) → 修环境

**禁止**"为了测试通过而加 `--no-strict`"。

---

## 🚫 2. 禁止 silent fallback

**绝对禁止**实现"AST 拿不到就 string parse"、"primary 失败就 secondary path"这类静默降级。

**理由**: silent fallback = 隐藏 bug。任何 fallback 必须满足三条之一：

- **显式报错** (`raise` / `logger.error`)
- **返回 sentinel** (`NO_TREE_MARKER` / `None` / `[]`) 并且调用方能区分"空数据"与"失败"
- **不静默继续** (绝不返回假数据)

**例外 (不算 fallback)**：

- `sv_preprocessor.py` 的 source content preprocessing (代码里有注释说明它**不是** fallback)
- 用户**显式 opt-in** 的可选路径 (如将来若需要 `--allow-incomplete`)

**正面参考**: `coverage_generator.py` 提取失败时返回 `NO_TREE_MARKER` + WARNING，而不是悄悄走字符串解析。

---

## 🚫 3. 禁止 `except ...: pass`

**绝对禁止** `except ...: pass` —— 异常被吞掉后，"失败"与"正常"不可区分。

**必须改成三选一**：

| 形态 | 写法 | 适用 |
|---|---|---|
| 捕获 + 记录 | `except X as e: logger.warning/debug(...)` | 失败可容忍但必须可见 |
| 捕获 + 返回 | `except X: return <sentinel>` | 契约明确 (查表失败 = 查不到) |
| 不处理 | `except X: raise` | 调用方该知道 |

**唯一允许的 `pass` 形态**：异常类型**已收窄** + 失败语义**明确** + **有注释**说明为什么跳过合理
(检查器此时给警告级而非失败)。

**机械保障** (提交前必跑):

```bash
python3 tools/check_except_pass.py     # 必须 ✅ (计数 = 0)
```

**这条规则本身就是教训**: 曾经在文档里声称"已全仓清零"，实测 `src/` 仍有 52 处
(其中 25 处 `except Exception: pass`) —— **没有机械检查的声明会重新长回来**。
回归测试 `sim/tests/unit/test_discipline_except_pass.py` 含"检查器能检出违规"的自检。

---

## 🚫 4. 禁止用 `-f` / `--file` 传 filelist

**`-f` / `--file` 只接受 SystemVerilog 源码；filelist 一律用 `--filelist`。**

**理由**: 本项目 `-f` = `--file` (单文件)，而很多工具 `-f` 是 filelist，习惯迁移过来必然写错。
写错的后果不是普通报错：

```bash
sv_query visualize module -f project.f     # ← 禁止
```

filelist 内容 (`/path/to/mod.sv`) 被当源码解析 → slang 走 script 模式 →
根节点成了**表达式** (`DivideExpression`，因为路径里有 `/`) →
`Compilation.addSyntaxTree()` **原生 SIGTRAP** (exit 133，无输出，Python 层不可捕获，
`faulthandler` 也拿不到栈)。

**机械保障**:

- `SVCompiler._reject_non_design_unit()` 在 `addSyntaxTree` 之前拒绝表达式根，抛可行动的 `CompilationError`
- 回归测试 `sim/tests/unit/test_compiler_non_design_unit_guard.py`
  (守卫失效时 pytest 会以 exit 133 崩 —— 最原始的报警方式)

**方豆决定 (2026-09-09)**: **不向上游 pyslang 报 issue** —— 判定为用法不一致，
正确做法是记录清楚并避免这样使用。详见 [KNOWN_LIMITATIONS.md](../KNOWN_LIMITATIONS.md) §3.1。

**正确写法**:

```bash
svq stats --filelist project.f                              # ✅ filelist
svq stats -f design.sv                                      # ✅ 单文件源码
svq visualize module --filelist project.f --target top      # ✅
```

---

## 🔎 5. 失败时正确归因

遇到任何 test / command / analyze 失败，**必须按顺序排查**，不要跳到第 5 步：

| 顺序 | 检查项 | 工具 |
|---|---|---|
| 1 | 测试 fixture 源码 (`sim/tests/fixtures/...`) | 读文件 / 单独 parse |
| 2 | 功能代码 (`src/trace/...`) | `git log -p` / `git blame` / 最小单测 |
| 3 | filelist (`sim/filelists/`, `*.f`) | 对比可用的 filelist |
| 4 | 环境 (pyslang / Python / 依赖) | `pip show pyslang` / `python --version` |
| 5 | (最后) 工具/CLI 自身的 bug | 复现 + 隔离测试 |

**禁止**在第 5 步之前用 `--no-strict` / 加 `try/except` 兜底 / 改 return type 让它"能跑"。

---

## 🧾 6. 例外条款 (何时可以暂时违反)

必须**同时**满足三条：

1. 方豆**明确指示** ("临时跳过这个" / "先用 --no-strict")
2. `CURRENT_TODO.md` 或 `docs/KNOWN_LIMITATIONS.md` 已记录这次临时跳过 + 后续要修
3. commit message 写明 `TEMPORARY: <违反项> due to <原因>, see <记录位置>`

**禁止**"没方豆指示就自己开口子" —— 那是纪律破坏，不是工程判断。

---

## 📚 7. 这些规则从哪来的 (历史背景 — 每条都付过代价)

| 时间 | 事件 | 教训 → 规则 |
|---|---|---|
| 2026-08-15 | 推行 strict pyslang API | "pure semantic API" → 规则 2 |
| 2026-08-26 | D5 cleanup 删除 v10/v11 compat，触发回归 | silent fallback 让旧路径隐藏了 → 规则 2 |
| 2026-08-27 | Plan G2 发现 case27 测试用 `--no-strict`，掩盖 expr tree 缺失 | `--no-strict` 是 debug 杀手 → 规则 1 |
| 2026-08-29 | 全仓 `except: pass` 清理，**后又被实测证伪** (52 处) | 无声吞异常 → 规则 3 + 机械检查 |
| 2026-09-09 | 误用 `-f` 传 filelist → pyslang 原生 SIGTRAP | 工具用法不一致 → 规则 4 |
| 2026-09-09 | `snapshot.py` 里 `def list()` 遮蔽 builtin，stdout 被污染 55,577 行 | 命名会咬人 → 规则 3 的检查器扩展 (R7) |
| 2026-09-09 | `loads` 跨模块"兜底补丁"只在零结果时触发 | 副本实现必然分叉 → 不变量 I3 |
| 2026-10-19 | `LoadTracer` 自带第二份遍历，`module=None` 时拼出 `"None.sig"` 假 id | 同上；且**登记缺陷低估了真实缺陷** → 不变量 I5 |
| 2026-10-19 | `docs/INDEX.md` 的 canonical 计数连续 4 个迭代未同步 | 声明没有机械保障会漂移 → [WORKFLOW.md](WORKFLOW.md) 文档卫生 |

---

## ✅ 8. 违规处置

1. **立刻停止**当前工作，不要在违规前提下继续产出
2. **回滚**违规改动 (`git checkout` / `git revert`)
3. **向方豆报告**: 违反哪条、影响范围、已回滚到什么状态
4. 如果是规则本身不合理 → 先讨论规则，**不要默默违反**
