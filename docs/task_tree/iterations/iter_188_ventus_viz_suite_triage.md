# Iteration 188: Ventus viz 验证套件分诊 — 常红转有信号 (0 failed / 13 明确 skip)

**Metadata**:
- **Iteration #**: 188
- **Task Tree Level**: L2 (测试设施正确性)
- **Parent Task**: iter_187 顺带发现立项 (方豆 "继续")
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ 14 failed → 0 failed (15 passed / 13 明确 skip); 另发现 1 个**原生崩溃** bug

## 🎯 本次目标

`sim/tests/usage/test_ventus_all_viz_validation.py` 是 `opensource` 集里**唯一常红**
的文件 (14 failed), 而 canonical gate (`-m "not opensource"`) 看不到它 →
"永久红灯"等于没有信号, 真回归会被淹没。本次: 诊断根因 → 该修的修 → 该决策的
明确标出来, 不再靠静默掩盖。

## 📊 当前状态 / 预期结果

预期: 只是 `--dot` 改名导致的断言过时, 改几个 flag 就好。
实际: **四类不同根因**, 其中一个是 CLI 原生崩溃 (与测试无关的真 bug)。

## 🔬 实际结果

### 根因 1: V100 起 `--dot` = `--svg` (输出 SVG) — 断言基于旧 DOT 语义

`src/cli/commands/visualize.py:192/262/...`: `--svg` / `--dot` / `-d` 是**同一个
选项**, help 写明 "Output SVG file (was DOT before V100; --dot kept as deprecated
alias)"。而测试断言 DOT 文本 (`digraph` / `rankdir=LR` / `subgraph cluster_stage*`
/ `shape=diamond`)。实测 SVG 里 **不存在** `rankdir` / `digraph` / `cluster` 任何一项。

处理: artifact 读取统一走 `_read_dot()` — 内容其实是 SVG 时 **skip 并写明原因**
(按 SVG 语义重写断言 = 可视化语义决策, 待方豆拍板), 而不是让断言以
`'Segment' not found in '<?xml ...<svg'` 这种形式失败。

### 根因 2: 各子命令 flag 语义不一致 (无统一 "输出 DOT" 入口)

| 子命令 | 当前输出 DOT 的方式 | 旧测试用的 |
|---|---|---|
| `visualize pipeline` / `chain` | `--svg`/`--dot` → **SVG** | `--dot` 期望 DOT ❌ |
| `visualize module` | `--dot` → DOT ✅ | `--dot` ✅ (但见根因 4) |
| `trace fanin` / `fanout` | `--format dot --output <file>` | `--dot <file>` ❌ (无此选项) |

处理: trace 类生成改用当前正确 flag; pipeline/chain 类交由 `_read_dot` skip。

### 根因 3: artifact 生成器静默 (且违反 AGENTS 纪律 1)

`_ensure_sched_dots()` 原实现: ① 全程用 **`--no-strict`** (AGENTS 核心纪律 1 明令
禁止); ② **忽略子进程 returncode**; ③ 只生成一部分 artifact (测试还读
`sched_d1.dot` / `r15*.dot` / `*.png`)。于是失败表现为 14 个 `FileNotFoundError` /
莫名断言错, 根因不可见。

处理: 去掉全部 `--no-strict`; 生成器**记录**每次 rc≠0 的命令与 stderr 末行;
artifact 缺失时测试 skip 且**打印生成器失败原因**(可行动)。实测生成器还有两处
调用错误一并修正: chain 缺 `--auto` (rc=1: "need --from and --to, OR --auto with
--target")、`--anomaly` 不是有效选项 (rc=2)、`visualize pipeline` **没有 `--png`**。

### 根因 4 (新 bug, 未修): `sv_query visualize module` 原生崩溃 (SIGTRAP)

```
$ sv_query visualize module -f sim/tests/fixtures/scheduler_minimal/filelist.f \
      --target Scheduler_minimal --depth 1 --dot /tmp/x.dot
$ echo $?   →  -5      (SIGTRAP; 无任何输出; 无 artifact)
```

- 三种 target (`Scheduler_minimal` / `no_such_module` / 默认 `top`) **全部 rc=-5**;
- in-process 调用 + `faulthandler.enable()` 同样**无栈输出** (SIGTRAP 不在
  faulthandler 默认捕获集 → 典型 native `abort()`/`__builtin_trap()`, 如 C++ assert);
- **不是我这次改动引入**: 用 `git worktree` 检出 **iter_183 (f639ed6, 早于
  iter_184~187)** 跑同一命令 → **同样 rc=-5**(验证后已移除 worktree);
- 影响: 该子命令 (L1 module 抽取可视化) 完全不可用; 也导致测试无法生成
  `sched_d1.dot`。

**未修** (需要 native 调试: lldb 抓栈; 且涉及 viz/ELK 层) — 建议单独立项, 见下。

### 结果对比

| 指标 | 修复前 | 现在 |
|---|---|---|
| failed | **14** | **0** |
| passed | 110 (含其他文件) | 15 (本文件) |
| skipped | 1 | **13 (全部带可行动原因)** |
| `--no-strict` 出现 | 10 | **0** |
| 生成器静默失败 | 是 | 否 (记录 + 上抛到 skip 原因) |

skip 的 13 个分两类: ① 10 个"断言基于 V100 前 DOT 语义"(待语义决策);
② 2 个 PNG 断言(需 `--png`, 而 pipeline 不提供)+ 1 个 timing PNG 同因。

## 💡 关键发现 / 关键技术 / 决策

1. **常红的测试集 = 零信号**: 14 个失败长期存在 → 真回归混在里面也看不见。
   把"已知语义变化"转成**带原因的 skip**、把"生成器坏"变成**可见记录**, 才算恢复信号。
2. **同一 CLI 内 flag 语义不统一本身就是缺陷**: `--dot` 在 `visualize pipeline`
   是 SVG 别名、在 `visualize module` 是 DOT、在 `trace` 不存在(改 `--format dot`)。
   用户/测试都难以预测 → 建议统一(例如所有 viz 命令同时提供 `--svg` 与
   `--dot`(真 DOT)), 但那要方豆定产品语义, 本次未动。
3. **`--no-strict` 是被禁写法, 却在测试里潜伏 10 处**: 它正是"artifact 生成失败
   却查不出原因"的帮凶之一 —— 与 AGENTS 纪律 1 的立意完全吻合。
4. **验证"是否我引入的"要用 worktree**: `git worktree add /tmp/x <commit>` 能在
   不动工作树的前提下跑旧代码, 是本次确认"崩溃系既有问题"的关键手段。

## 📢 待方豆决定

| # | 事 | 现状 → 建议 | 代价 |
|---|---|---|---|
| 1 | `visualize module` SIGTRAP 崩溃 (子命令全废) | 需 native 调试定位 (lldb); **建议立项专项** | 中 |
| 2 | 13 个 skip 的断言该按 SVG 语义重写吗 | 涉及"pipeline 图该画什么"的产品语义 (原断言含 2026-07-10 方豆反馈: 死代码/X 值标记等) → 建议方豆确认后可重写 | 中 |
| 3 | 是否统一各 viz 子命令的输出 flag (`--svg` + 真 `--dot`) | 现在不一致, 用户/测试难预测 → 建议统一 | 小~中 |
| 4 | PNG 类断言 | `visualize pipeline` 无 `--png` (仅 chain 有) → 要么给 pipeline 加 `--png`, 要么断言改从 SVG 尺寸推断 | 小 |

## 📎 关联

- 测试: `sim/tests/usage/test_ventus_all_viz_validation.py`
- 发现来源: `iter_187_baseline_drift_cleanup.md` (顺带发现一节)
- CLI 语义: `src/cli/commands/visualize.py:192/1569`、`src/cli/commands/trace.py:611`
- 纪律: `AGENTS.md` 核心纪律 1 (禁 `--no-strict`)
