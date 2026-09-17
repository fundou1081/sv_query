# Iteration 232: CLI 分层 P1b-1 — `exp/` 层目录落地 (表面零变化的纯搬迁)

**Metadata**:
- **Iteration #**: 232
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_cli_layering.md`
- **Created**: 2026-09-09 GMT+8
- **Author**: 方豆 / AI 助手
- **Outcome**: ✅ 成功 (CLI 表面 md5 完全不变; 全量 3334 passed / 0 failed)

## 🎯 本次目标

方豆: **"开始吧，保险一些的做法。"** —— 执行 P1b (目录分层, 让目录结构体现分层),
采用**一次搬一层 + 表面零变化 + 每层全量门禁**的保守节奏。

先搬 **`exp/`**: 它最独立 (9 个文件之间零交叉), 且已由 iter_230/231 的检查器 + 政策文档
(`docs/EXP_NAMESPACE.md`) 定义清楚。

## 🔬 做法: 用"表面黄金快照"证明这是纯搬迁

搬目录最大的风险是**悄悄改变 CLI 表面** (命令丢失/改名/选项错乱)。因此本轮先拍快照, 再比对:

```bash
python3 tools/gen_cli_surface.py --json > /tmp/surface_before.json   # 搬之前
# ... git mv + 改 import ...
python3 tools/gen_cli_surface.py --json > /tmp/surface_after.json    # 搬之后
```

| 比对项 | 结果 |
|---|---|
| 文件 md5 | before `8df6276e83887ba9b620f069565145b8` = after **完全一致** |
| 命令数 | 65 = 65 |
| `rows` (每个命令的 layer/group/json/filelist/options 等) | **完全相等** |
| 别名表 | 一致 |

`gen_cli_surface.py` 的数据来自 **typer introspection** (真实 CLI) + 注册表,
所以 md5 一致 = "命令面一个字节都没变" 的强证明。

## 📦 搬迁内容

```
src/cli/exp/
├── __init__.py          # 层声明 (LAYER = LAYERS["exp"]) + 指向 docs/EXP_NAMESPACE.md
├── bus/    protocol.py  handshake.py  backpressure.py
├── verif/  sva.py  coverage.py  verify.py  risk.py  randomize.py
└── struct/ cdc.py  timing.py
```

- 全部用 `git mv` (保留历史)
- 依赖扫描确认 **9 个文件之间零交叉 import**, 只依赖 `cli/_common`、`cli/_evidence_helpers` (共享层)
- `main.py` 10 处 import 路径更新 (`cli.commands.X` → `cli.exp.<域>.X`)
- 5 个直接 import 命令模块的测试同步更新 (用 `re.sub` 精确替换模块路径)
- **命令路径不变**: 仍是 `svq protocol detect` / `svq sva extract` / `svq cdc analyze` …
  (把命令挪到 `svq exp ...` 前缀是 P3 的事, 需要 alias 过渡, 不在本轮)

## ❌ 全量门禁抓到 3 类"搬迁盲点" (如实记录)

第一次跑全量门禁: **17 failed, 5 秒内报错** —— 我搬前的 `grep` 只查了 `import cli.commands.X`
这一种形式, 漏掉另外三类 (全部是真实引用):

| # | 盲点 | 后果 | 修法 |
|---|---|---|---|
| 1 | `from src.cli.commands import coverage` (**`from X import Y` 形式**, 不是我 grep 的 `X.Y`) | `test_coverage_generator.py::test_cli_module_imports` ImportError | 改成 `from src.cli.exp.verif import coverage` |
| 2 | 测试**按路径直接读源码**做断言 (`open(src/cli/commands/handshake.py)`) | `test_handshake_mwc_mrc.py` 收集期 `FileNotFoundError` → 整个套件 1 error | 路径改 `exp/bus/handshake.py` |
| 3 | 文件内 `Path(__file__)` **路径深度运算** (搬一层即错位) | `coverage.py:243` 的 `parents[3] / "tools"` 从 `<repo>/tools` 变成 `src/tools` → `import coverage_gen_demo` 失败 → **16 个测试红** | 见下方"根因修复" |

**根因修复 (不是逐个打补丁)**: 新增 `src/cli/_paths.py` 作为**路径锚点单一真相源**
(`CLI_DIR` / `SRC_DIR` / `PROJECT_ROOT` / `TOOLS_DIR` + `ensure_on_path()`),
把 `src/cli/**` 里所有 `__file__` 深度运算替换成锚点引用 (含 `main.py` / `_entry.py`)。
理由: P1b-2 还要搬 core/view, 不修的话同类事故必然重演。

**顺带修正我自己的一次误改**: 脚本把 `main.py` 的 `PROJECT_ROOT` 误换成 `SRC_DIR`
(控制台脚本 `sv_query` 需要 repo root 在 sys.path 才能 `from src.cli... import`) —— 已恢复并冒烟验证。
又一次印证: **多行正则替换必须逐条复核结果**, 不能只看脚本"成功"输出。

## 🔧 机械保障 (新增 2 件)

1. **R8**: `src/cli/**` 禁止 `__file__` 路径深度运算 (只允许 `_paths.py` 自己) —— 由 `check_cli_layers.py` 强制
2. **`tools/find_module_refs.py`**: 搬模块前的**引用扫描单**, 一次列出三类易漏引用
   + 文档路径引用:
   ```
   python3 tools/find_module_refs.py cli.commands.coverage      # 搬前检查
   python3 tools/find_module_refs.py cli.exp.verif.coverage -q  # 搬后复核
   ```
   实测: 搬后旧路径只剩"解释性文字"(我自己的 docstring), 无真实引用

## 📊 验证

| 项 | 结果 |
|---|---|
| CLI 表面 md5 | **完全一致** (`8df6276e…`) — 强证明纯搬迁 |
| `check_cli_layers.py` | rc=0 (R1~R8 全过) |
| 定向测试 (5 个改 import 的文件) | **43 passed** |
| 之前 17 个失败 | `test_coverage_generate.py` + `test_coverage_generator.py` → **196 passed** |
| 全量 CLI 模块导入检查 | 0 失败 (walk_packages 遍历) |
| 两条入口冒烟 | `sv_query`(console) / `run_cli.py` 均 rc=0 |
| 全量 canonical | **3334 passed / 0 failed** (0 退化) |

## 💡 关键发现 / 决策

1. **纯搬迁要用"表面快照"当证据, 不能靠"看起来没变"**: `gen_cli_surface.py --json` 的 md5
   比对把"命令面未变"变成可机械判定的事实 —— 这与 iter_227 的 `ast.dump` 等价闸、
   iter_190 的 `check_except_pass` 是同一种手法 (可验证 > 可声称)。
2. **先搬最独立的层**: `exp` 只依赖共享层, 搬迁面小; 把最难的两块 (`trace.py` 1819 行、
   `visualize.py` 2380 行) 留到最后, 且**先整文件搬、再考虑拆分**, 不让"分层"和"拆巨型文件"
   两件事耦合在一个 commit 里。
3. **保守节奏的成本很低**: 搬一层 + 跑一次全量门禁 ≈ 7 分钟。这个代价换来的是
   "任何一层出问题都能单独回退", 比一次性搬 26 个文件划算。

## 📋 P1b 后续 (按同样的保守节奏)

| 子步 | 内容 | 风险 |
|---|---|---|
| **P1b-2** | `dev/` (expression) + `core/` (locate/semantic/state/diagnose 整文件) + `view/` (visualize/arch/design 整文件) | 中 (文件多, 但仍是整文件搬); **搬前必跑 `tools/find_module_refs.py`** |
| P1b-3 | 拆分 `trace.py` (core signal + view overview) 与 `visualize.py` (10 个 view 命令各自成文件) | 高 (要动函数体, 单独迭代) |
| P2 | `fix timescale --apply` / `fix imports --write` 移出 CLI → `tools/` (含 `out/` 层目录); snapshot 目录迁 `$SVQ_CACHE_DIR` | 中 |

## 📎 产物

- 目录: `src/cli/exp/{bus,verif,struct}/` (9 文件 `git mv` + 4 个 `__init__.py`)
- 代码: `src/cli/main.py` (import 路径), 5 个测试文件 (import 路径)
- 文档: 本记录 + `L1_cli_layering.md` (P1b-1 完成) + `CURRENT_TODO.md` + `overview.md` + `INDEX.md`

## 🔧 追加: 生成器 `--check` 自身的缺陷 (本迭代发现并修)

提交前 `gen_cli_surface.py --check` 报"与代码不一致", 但 diff 只有一行:
**生成日期跨天** (2026-09-17 → 2026-09-18)。也就是说 `--check` **每天都会误报一次** —— 
漂移检查器把**易变字段**也算进了比对。

修法: `_strip_volatile()` 在比对前把 `> **生成日期**: <date>` 归一化, 只比稳定内容。
(与 R3/R7/R8 的教训同源: 检查器本身也要被抽查, 否则"报红/报绿"都不可信。)
