# Iteration 235: CLI 分层 P3 — `exp` 降级区收进 `svq exp ...` 前缀 (老路径全保留为别名)

**Metadata**:
- **Iteration #**: 235
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_cli_layering.md`
- **Created**: 2026-09-09 GMT+8
- **Author**: 方豆 / AI 助手 (方豆: "做 p2 p3")
- **Outcome**: ✅ 成功 (agent 默认可见命令 65 → **38**; 全量 3336 passed / 0 failed)

## 🎯 本次目标

P3 = 把降级区 (总线域 + 验证域 + 待定算法) 从**顶层平铺**收进 `svq exp ...` 前缀,
让"顶层可见面"与"承诺等级"一致; 老路径**全部保留为兼容别名**(alias 先行, 不破坏任何现有脚本/测试)。

## 📦 改动

### 1. 新顶层组 `svq exp` (规范入口)

```
svq exp
├── protocol      detect show list semantics
├── handshake     scan analyze pair
├── backpressure  analyze deadlock
├── sva           extract coverage timing
├── coverage      suggest gap generate analyze
├── verify        gap
├── risk          analyze
├── randomize     list extract trace reachability
├── cdc           analyze
└── timing        analyze
```

组帮助统一标 **`[UNSTABLE]`** + 指向 `docs/EXP_NAMESPACE.md` (降级五条硬约束 + 晋升门槛)。

### 2. 老路径 = 兼容别名 (10 个顶层组原样保留)

`svq protocol detect` / `svq sva extract` / `svq cdc analyze` … 全部仍可用 ——
它们是**同一个 Typer 子应用**挂在两个位置, 零实现重复。
(这与 `drivers`/`loads`、`diagnose`/`fix` 采用同一套别名机制。)

### 3. 注册表与能力清单

- 24 条 exp 条目的**规范名**改为 `exp <组> <子>`; `ALIASES` 增加 24 条 (老路径 → exp 路径)
- `svq capabilities --json` 默认输出:**38 条命令**(core 25 + view 13) —— 比 P2 时的 65 少了 27
  (exp 24 + dev 3 本就不在默认面; 这次 exp 的**规范名**也统一收进前缀)
- `--include-exp` 才列出, 且显示 `exp protocol detect` + `aliases: ['protocol detect']`

### 4. 顶层可见面变化

| | P2 结束 | P3 结束 |
|---|---|---|
| 顶层命令组 | 21 + diagnose | 21 + diagnose + **exp** (10 个 exp 组降为别名但仍在 help 可见, 见下) |
| 规范命令 | 65 | 65 |
| 兼容别名 | 6 | **30** |
| agent 默认可见 (`capabilities`) | 65 | **38** |

**关于别名是否隐藏**: 本轮**刻意不隐藏**老组 (`hidden=True`) —— 项目纪律是 "alias 先行,
跨一个版本再移除"; 现在就隐藏会让老用户/老脚本找不到入口。**P6 复审时**再决定隐藏或移除
(届时 `docs/EXP_NAMESPACE.md` 的复审条目一并处理)。

## 📊 验证

| 项 | 结果 |
|---|---|
| `check_cli_layers.py` | rc=0 (R1~R8; **R1 接受别名**: 95 个叶子 = 65 规范 + 30 别名, 0 违规) |
| `svq exp <组> <子>` | rc=0 (例 `exp sva extract --help`); 老路径同样 rc=0 |
| `capabilities` | 默认 38 条; `--include-exp` 显示 `exp ...` 规范名 + 别名 |
| 定向测试 (protocol/handshake/backpressure/cli_layering/fix_report) | **49 passed** |
| CLI_SURFACE.md | 已重生成 (65 命令 + 30 别名) |
| 全量 canonical | **3336 passed / 0 failed** (0 退化) |

## 💡 关键发现 / 决策

1. **"降级"要落到"默认不可见 + 路径带前缀", 而不是只写文档**: P3 之前 exp 与正式命令在
   顶层并列 (靠 `--include-exp` 区分); 现在规范名带 `exp` 前缀, agent 从**命令名**就能看出承诺等级。
2. **别名机制被复用了三次** (drivers/loads → diagnose/fix → exp/*), 说明 P1a 选"同一函数对象双注册"
   是对的: 三轮改名/移动, 零实现重复、零行为漂移、老路径从不失效。
3. **不隐藏别名是刻意的**: 兼容期内"老路径仍可发现"比"help 更干净"重要; 隐藏/移除是 P6 的复审动作,
   有明确期限 (下个 minor), 避免"待定变永久"。

## 📎 产物

- 代码: `src/cli/main.py` (exp 组 + 10 个老组别名) / `src/cli/_registry.py` (24 规范名 + 24 别名)
- 生成物: `docs/CLI_SURFACE.md` (重生成)
- 文档: 本记录 + `L1_cli_layering.md` (P3 ✅) + `CURRENT_TODO.md` + `overview.md` + `INDEX.md`
- 剩余: P2 剩余 (snapshot 目录迁缓存 + 只读证明测试) / P1b-3 (拆 trace.py、visualize.py) / P6 (exp 复审 + 别名隐藏)
