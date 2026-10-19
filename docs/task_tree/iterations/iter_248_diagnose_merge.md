# Iteration 248: T2-b — `diagnose` 4 项检查合并为 1 个入口 (4 → 1)

**Metadata**:
- **Iteration #**: 248
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-19 GMT+8
- **Author**: 方豆 / AI 助手（长期 goal: 清掉减法清单）
- **Outcome**: ✅ 成功（规范命令 73→70，别名 26→22，叶子 103→96；全量 3422 passed）

## 🎯 目标

默认可见面里 `diagnose` 占了 4 个位置（`imports` / `report` / `timescale` / `widths`），
外加 4 个 `fix` 兼容别名。四者的**输入完全相同**（`--filelist` + 日志级别），
区别只是"查什么" —— agent 得先猜该调哪个。

## 🔬 实际结果

### 改法

新增 `src/cli/core/diagnose/dispatch.py`：一个命令 `diagnose <check>`，
`check ∈ {imports, report, timescale, widths}`，内部转发到原四个实现（原逻辑零改动）。

- 参数取并集：`--filelist`（必填）、`--project-root`（imports/widths 用）、
  `--timescale` / `--include-headers`（timescale 用）、`--top`（imports/widths 用）、
  `--log-level` / `--json` / `--pretty`
- 未知 `check` → 明确报错并列出可选值（rc=2），不静默
- **payload 不合并**：四类检查输出形状不同，各自保持原形状（`command` 字段仍写
  `diagnose <check>`）。只并入口，不并 schema —— 这是评审里那条合并判据的边界。

### `fix` 老路径已删除（4 个别名）

诊断本来就是只读的，"fix" 是历史误称；写文件能力早在 iter_234 搬到
`tools/fix_imports.py` / `tools/fix_timescale.py`。保留 `fix` 别名会让"只读"这个
承诺在命令名上继续自相矛盾。

### 测试适配（19 处调用 + 3 处断言）

- 15 处 `_run("fix", "x", ...)` → `_run("diagnose", "x", ...)`
- 3 处断言从"子命令 help"改为"顶层 help"（合并后只有一个帮助）：
  - `--filelist` / `--project-root` / `--json` 仍在
  - `--write` / `--apply` **必须不在** help 里（只读硬约束）
  - `tools/fix_imports.py` / `tools/fix_timescale.py` 必须出现在 help 里（指向写入路径）
- 顺手把 timescale 的"运行时拒绝 `--apply`"补成真实断言（原来只查 help 文本）

> 文档适配：`CLI_COMMAND_CHEATSHEET` / `EXPERIMENTAL_FEATURES` / `NAPLESPU_HOWTO` /
> `SIGNAL_TRACING_EXAMPLES` 里 6 处 `fix` 老用法改为 `diagnose` 或 tools 脚本。

## 📊 量化

| 指标 | 前 | 后 |
|---|---|---|
| 规范命令 | 73 | **70** |
| `core` 层 | 33 | **30** |
| `diagnose` 组 | 4 | **1** |
| 别名 | 26 | **22** |
| 叶子（含别名） | 103 | **96** |
| 全量测试 | 3422 | **3422**（无增减，无回归） |

## 💡 关键决策

1. **只并入口，不并 schema。** 四类检查的载荷不同（缺依赖 / 错误分类 / 缺 timescale /
   typedef 位宽），硬合成同一个 schema 会让每类检查都带一堆 `null` 字段。
   评审里那条判据（"输入可由枚举参数表达 + 输出同构"）在这里只满足前一半，
   所以**只合并命令入口**，并在 docstring 里写清各自形状。

2. **help 不能只写"只读"，要写"去哪写"。** 删掉 `--write/--apply` 后，用户会问
   "那我要改文件怎么办"。dispatch 的 docstring 明确指向两个 tools 脚本，
   并由测试锁定这两个路径必须出现在 help 里。

3. **删别名要一次删干净。** 只删 4 个规范命令却留 4 个别名，叶子数只减 3 而不是 8；
   且"fix"与"只读"的语义冲突会继续存在。

## 🔗 相关

- 评审: [2026-10-19_core_smell_review.md §5.2](../../refactoring/2026-10-19_core_smell_review.md)
- 前置: [iter_247 class 合并](iter_247_class_merge.md)
- 新增: `src/cli/core/diagnose/dispatch.py`
