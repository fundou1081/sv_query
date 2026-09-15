# Iteration 214: `strict` 降级扫描 — 完整地图 (不违反纪律的"默认值/调用点"清单)

**Metadata**:
- **Iteration #**: 214
- **Task Tree Level**: L1 (纪律强制 · 诊断)
- **Parent Task**: 方豆 "好，先扫" (iter_213 下一桶的诊断步)
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ 清单完成 (**未改代码**)

## 🎯 本次目标

iter_211 清掉的是"**用法**" (`--no-strict` 字符串), 但降级还藏在**默认值**与
**代码内调用点**里。本轮把它们全量扫出来, 形成可执行清单。

## 🔬 扫描结果 (全仓 `src` / `tools` / `sim/tests`)

### A. CLI 选项默认非严格 — **4 处** (用户不传 flag 时就是降级模式!)

| 位置 | 命令 |
|---|---|
| `src/cli/commands/arch.py:897` | `arch` |
| `src/cli/commands/backpressure.py:351` | `backpressure` (help 明写 "default non-strict") |
| `src/cli/commands/coverage.py:232` | `coverage generate` (help 明写 "default: --no-strict") |
| `src/cli/commands/design.py:372` | `design` |

→ 这 4 个命令**默认就在优雅降级**, 与 AGENTS "strict 是默认" 直接冲突。

### B. Python API 默认 `strict=False` — **2 处**

| 位置 | 说明 |
|---|---|
| `src/cli/_evidence_helpers.py:28` | `build_resolver(..., strict=False)` — 证据/DB 路径的公共入口 |
| `tools/coverage_gen_demo.py:831` | `generate_covergroup(..., strict=False)` |

### C. 生产代码/脚本里主动传 `strict=False` — **9 处** (降级用法)

`src/cli/commands/`: `fix_imports.py:249` / `arch.py:75` / `arch.py:87` / `fix.py:121` /
`fix.py:274` / `fix_widths.py:195` / `snapshot.py:23` / `snapshot.py:58`
`tools/fix_timescale.py:54`

### D. 测试里的 API 级降级调用 — **29 处** (`sim/tests/**` 的 `strict=False`)

iter_211 只清了**命令行字符串**, 这些是**直接调 Python API** 时传 `strict=False`
(意图与被禁 flag 相同) → 同属违规, 需一并处理。

### E. 误报 (不是违规, 仅注释/无关函数)

`src/cli/commands/protocol.py:131` (注释) / `src/trace/core/uvm_testbench_extractor.py:69`
(docstring) / `src/trace/core/compiler.py:468` (注释) / `tools/check_docs.py:82`
(无关函数的 `strict` 参数)。

**真实待清合计**: 4 + 2 + 9 + 29 = **44 处**。

## 💡 关键发现

1. **"默认值"比"用法"更危险**: 用户**不传任何 flag** 时就在降级 (4 个命令),
   连纪律文本都写进 help ("default non-strict") —— 用法违规至少是显式选择。
2. **违规四处藏身**: 命令行字符串 ✅(已清) / CLI 默认值 / API 默认值 / 代码内调用点
   (含测试) —— 只按"字符串搜索"清理必然漏。
3. **测试里的 API 级降级 (29 处) 是最大一块**: 它们和 iter_210/211 清掉的是同一种意图,
   只是不经过命令行 → 需要同一批处理。
4. **诊断先行的价值**: 本轮没改一行代码, 却把"下一桶"从模糊的 15 个测试变成
   44 处可定位的点 (含 4 个默认值 + 2 个 API 签名)。

## 📢 建议的清理顺序 (待方豆拍板)

| 步 | 内容 | 预估影响 |
|---|---|---|
| 1 | 4 个 CLI 默认值 → `strict=True` (保留选项本身) | 4 个命令的行为变化 → 会暴露其 fixture/用例的真实错误 (预计一批测试转红, 同批修) |
| 2 | 2 个 API 默认值 → `strict=True`; `strict=False` 调用点改为报错/移除 | 牵动 `_evidence_helpers` 的所有调用方 |
| 3 | 9 处生产/脚本调用点: 改为 `strict=True` (若其项目真的不完整 → 修源或显式 opt-in 命名) | 需逐点确认语义 |
| 4 | 29 处测试调用点: 去掉 `strict=False` | 预计暴露更多"假绿" fixture (与 iter_213 同类) |
| 5 | 可视化 16 个失败 (按方豆指示暂缓) | — |

**建议**: 从 **步 1 (CLI 默认值)** 开始 —— 面最小、最"用户可见"、最符合纪律本意
("strict 是默认"), 且能顺带把它们背后的真 fixture 问题挖出来。

## ⚠️ 追加发现 (同一轮, 更严重): 生产代码仍在**主动追加 `--no-strict`**

准备"彻底移除 strict"的第一批时发现: `src/cli/commands/design.py` 有 **7 处**
`args.append("--no-strict")` (在 `_run_cdc` / `_run_protocol` / `_run_handshake` /
`_run_backpressure` ... 这些辅助函数里, 按 `strict` 参数决定是否追加)。

**修正我此前的说法**: iter_211 宣称"sim/tests 与 tools 的用法归零"—— 那是**限定范围**
的结论; **`src/` 里仍有 7 处 flag 用法** (生产代码内部拼接命令行并传给子进程)。
纪律 1 禁止的是"在 `run_cli.py` / 测试 / 脚本中使用", 生产代码**替用户**追加同样
属于把降级当默认行为 → 必须一并移除。

**总计待处理 (rerun 后的准确版)**:
| 类别 | 数量 |
|---|---|
| `src/` 内 `--no-strict` **flag 用法** (design.py) | **7** |
| CLI 选项默认非严格 (A) | 4 |
| API 默认 `strict=False` (B) | 2 |
| 生产/脚本 `strict=False` 调用点 (C) | 9 (含 design.py 的 7 处相关辅助) |
| 测试 API 级降级 (D) | 29 |
| **合计** | **≈ 51 处** |

## 🧭 "彻底移除 strict" 的执行方案 (方豆已定方向)

**目标**: 删除 `strict` 参数与 `--strict/--no-strict` 选项, 工具**恒定严格**,
不存在任何降级通道。

| 批次 | 内容 | 风险/影响 |
|---|---|---|
| **1** | `src/cli/commands/design.py`: 删 7 处 `args.append("--no-strict")` + 相关 `strict` 参数/分支 | 中 (design 的 5 个子分析会走严格模式) |
| **2** | 4 个 CLI 默认值命令 (arch/backpressure/coverage/design): 删除 `strict` 选项 + 内部传参 | 高 (用户可见的 CLI 变化; 会暴露真 fixture 错误) |
| **3** | API 层: `_evidence_helpers.build_resolver` / `tools/coverage_gen_demo.generate_covergroup` 去掉 `strict` 形参 | 中 (牵动全部调用方) |
| **4** | 9 处生产/脚本 `strict=False` 调用点 | 低 |
| **5** | 29 处测试 API 级降级 + 随批次 2/4 暴露的 fixture 修复 | 高 (预计再暴露一批"假绿") |
| **6** | 可视化 16 个失败 (暂缓) | — |

**每批纪律**: 删参数 → `ast.parse` 校验 → 跑该批相关测试 → 记录新暴露的 fixture 问题
(按方豆"失败先保留, 之后一起修"的原则, 允许批次内红, 但必须**如实记录红在哪**)。
**收口**: 全仓 `grep -rn "strict" src tools sim/tests` 应只剩**无降级语义**的用法
(如 pydantic/其它库的 strict 关键字), 且全量门禁恢复到只剩可视化 16 个。

## 📎 关联

- 前序: `iter_211_no_strict_all_removed.md` (用法清零) /
  `iter_213_fixture_fixed_dependent_defaults_recorded.md` (默认值桶的发现)
