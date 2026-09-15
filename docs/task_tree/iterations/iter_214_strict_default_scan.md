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

## 📎 关联

- 前序: `iter_211_no_strict_all_removed.md` (用法清零) /
  `iter_213_fixture_fixed_dependent_defaults_recorded.md` (默认值桶的发现)
