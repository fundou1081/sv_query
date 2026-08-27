# AGENTS.md - sv_query 项目纪律 (Project Discipline)

> 创建时间: 2026-08-27
> 维护人: 方豆 + AI 助手
> 状态: **强制执行** — 所有 AI 助手 (包括 QClaw, Claude Code, GitHub Copilot 等) 在本项目工作时必须遵守

---

## 🎯 项目一句话

**sv_query** = SystemVerilog 静态分析工具 (基于 pyslang + 自研 4 维分析: L1 module 抽取 / L2 端口连接 / L3 内部信号 / L4 可视化)。

目标: 让验证工程师直接问 "这个信号谁驱动的？" 而不是读代码。

---

## 🚫 核心纪律 (Hard Rules — 违反任何一条 = 立即停止并报告方豆)

### 1. 禁止 `--no-strict`

**绝对禁止**在 `run_cli.py` / 测试 / 脚本中使用 `--no-strict` 标志。

**理由**: `--no-strict` 是 sv_query 早期为了应对不完整 RTL/elaboration 报错时做的 graceful degradation,
但它掩盖了真实的代码质量问题 (空 graph、节点缺失、expr tree 拿不到), 让 debug 变得不可能。

**如果命令在 strict 模式下失败**, 不要加 `--no-strict` 让它"能跑" — **应该诊断根因**:
- 测试源码 (test fixture) 有语法/语义错误 → 修 fixture
- 功能 (src/) 有 bug → 修 src
- filelist 不完整 → 补 filelist
- 环境配置 (pyslang 版本、Python 版本) 不匹配 → 修环境

**禁止**"为了测试通过而加 --no-strict"。

### 2. 禁止 `fallback` 模式

**绝对禁止**实现"AST 拿不到就 string parse fallback"、"primary 失败就 secondary path"这类 silent fallback。

**理由**: Silent fallback = 隐藏 bug。所有 fallback 必须:
- **显式报错** (raise / log ERROR)
- **返回 sentinel** (如 `NO_TREE_MARKER`, `None`, `[]`)
- **不静默继续** (不返回假数据)

**例外 (不算 fallback)**:
- `sv_preprocessor.py` 的 source content preprocessing (有明确注释说 NOT fallback)
- 用户**显式 opt-in** 的可选路径 (e.g., `--allow-incomplete` 如果将来需要)

**正面参考**: `coverage_generator.py` 已经贯彻 "no string fallback" 原则,
提取失败时返回 `NO_TREE_MARKER` + WARNING, 而不是悄悄走 string 解析。
**新代码必须遵守同样的严格性**。

### 3. 失败时正确归因

遇到任何 test / command / analyze 失败, **必须按下面顺序排查**:

| 顺序 | 检查项 | 工具 |
|---|---|---|
| 1 | 测试 fixture 源码 (sim/tests/fixtures/...) | `cat` / `vim` / `pyslang` parse |
| 2 | 功能代码 (src/trace/...) | `git log -p` / `git blame` / 单测 |
| 3 | filelist (sim/filelists/..., *.f) | `cat` / 对比 working filelist |
| 4 | 环境配置 (pyslang 版本、Python 版本、依赖) | `pip show pyslang` / `python --version` |
| 5 | (最后) 工具/CLI 本身的 bug | reproduce + 隔离 test |

**禁止**在第 5 步之前用 `--no-strict` / 加 `try/except` 兜底 / 改 return type 让它"能跑"。

---

## 📐 工作流规范

### 代码改动前
1. 读相关模块的 AGENTS.md / docs/ (有就遵守)
2. 看最近 10 个 commit, 理解最近 5 个 plan/cycle 在做什么
3. **写 G2/G3 计划**: 明确 1-N 个 sub-task, 每个有可验证输出

### 代码改动后
1. `python -m pytest sim/tests/unit sim/tests/cli -q` — 必须全绿
2. `python -m pytest sim/tests/test_case27_1to1_truth.py -q` — 1to1 truth 必须全绿
3. `git diff` 复查: 没有未预期的 fall-through / 死代码
4. `git commit -m "feat(...): ..."` 引用 plan/cycle 名 (e.g., `Plan G2 2026-08-27`)

### 调试时
1. **不要用 `--no-strict` 让 test 跳过** — 那等于不测
2. **不要 silent `except Exception: pass`** — 至少 `logger.warning()`
3. **不要 "为通过而改 assertion"** — assertion 是 spec, 不是障碍

---

## 🔍 自我审视清单 (每完成一个 sub-task)

- [ ] 我有没有用 `--no-strict`? → 如果有, 立刻删除, 改诊断根因
- [ ] 我有没有 silent fallback? → 如果有, 改成显式错误 + sentinel
- [ ] 我有没有为通过测试改 assertion / fixture 而不修功能? → 如果有, revert
- [ ] 我有没有改 src/ 让一个本来失败的 case "意外通过"? → 如果有, 仔细 review

---

## 🆘 例外: 何时可以暂时违反

只有当**所有**下面条件都满足:
1. **方豆明确指示** "临时跳过这个" / "先用 --no-strict"
2. **issue tracker / TODO** 已记录这个临时跳过 + 后续要修
3. **commit message** 明确说明 "TEMPORARY: --no-strict due to issue #N, see TODO"

**禁止** "没方豆指示就自己加 --no-strict" — 这是 discipline breach。

---

## 📚 历史背景

| 日期 | 事件 | 教训 |
|---|---|---|
| 2026-08-27 | Plan G2 发现 case27 test 用 `--no-strict`, 掩盖了 expr tree 缺失 | `--no-strict` 是 debug 杀手, 必须禁用 |
| 2026-08-26 | D5 cleanup 删除 v10/v11 compat, 触发回归 | silent fallback 让旧路径隐藏了 |
| 2026-08-15 | PR1+PR2+PR3 推行 strict pyslang API | "pure semantic API" = 不允许 fallback 到 string |

---

## 📝 版本

- v1.0 (2026-08-27 12:02 GMT+8) — 初版, 方豆指示 "禁止 no strict, 禁止 fallback"

