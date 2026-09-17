# Iteration 233: CLI 分层 P1b-2 — `core/` `view/` `dev/` 三层目录落地 + 稳定指纹

**Metadata**:
- **Iteration #**: 233
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_cli_layering.md`
- **Created**: 2026-09-09 GMT+8
- **Author**: 方豆 / AI 助手 (方豆: "继续")
- **Outcome**: ✅ 成功 (CLI 表面未变; 全量 3334 passed / 0 failed)

## 🎯 本次目标

延续 P1b 的保险节奏 (一次一层 / 表面零变化 / 每层全量门禁), 把 `core` `view` `dev` 三层目录落地。
**搬前先跑**上一轮新装的 `tools/find_module_refs.py` —— 结果引用清单很短 (3 处代码 + 3 处注释 + 1 处脚本/文档),
说明上一轮的"引用扫描单 + R8"确实把风险前置了。

## 📦 搬迁内容 (13 文件, 全部 `git mv`)

```
src/cli/
├── core/
│   ├── locate/    capabilities.py  search.py  stats.py  graph.py
│   ├── state/     snapshot.py  diff.py
│   └── semantic/  trace.py  dataflow.py  controlflow.py
├── view/          visualize.py  arch.py  design.py
└── dev/           expression.py
```

- 每层 `__init__.py` 声明 `LAYER` + 指向 `docs/CLI_SURFACE.md` / `docs/EXP_NAMESPACE.md`
- **`trace.py` 暂整文件放 `core/semantic/`** (它含 `overview` 这个 view 命令):
  先整文件搬、再拆分 —— 不让"分层"与"拆 1819 行文件"耦合在一个 commit 里 (拆分为 P1b-3)
- `commands/` 只剩 `fix.py` / `fix_imports.py` / `fix_widths.py` (P2 要拆成"只读诊断 → core/diagnose" + "会写文件的 → tools/")

## 🔧 引用更新 (扫描单给出的完整清单)

| 类型 | 位置 | 处理 |
|---|---|---|
| 代码 import | `main.py` 12 处 | 路径更新 |
| 代码 import | `src/cli/_evidence_helpers.py:46` (`_load_tracer_from_snapshot`) | `cli.core.semantic.trace` |
| 代码 import | `sim/tests/usage/test_coverage_generator.py:3057` | 同上 |
| 代码 import | `sim/tests/cli/test_arch.py` 5 处 (`_hash_color` 等内部函数) | `cli.view.arch` |
| **脚本** | `sim/tests/manual_ventus_chunk.sh:23` | `cli.view.arch` (上一轮漏的 `.sh` 类) |
| 注释 | `driver_extractor.py` / `_dot_common.py` / `test_ventus_all_viz_validation.py` | 路径同步 (保持注释准确) |
| 文档 | `docs/EVIDENCE_FEATURE.md` / `docs/architecture/*` 2 份 | 路径同步 |

## 🔬 新增: 稳定指纹 (`--fingerprint`)

上一轮用 `gen_cli_surface.py --json` 的 md5 证明纯搬迁, 本轮**它假警报了**:
md5 从 `8df6276e…` 变成 `6754d4e6…`, 但 `--check` 却是 ✅ —— 原因: `--json` 输出里含
`generated_at` **日期**, 而检查期间跨天了 (2026-09-17 → 09-18)。

修法: 新增 `--fingerprint`, 只对**命令面**取 sha256 (排除日期等易变字段):

```bash
python3 tools/gen_cli_surface.py --fingerprint
# 045f029ede3ada43686d5bf3055360452b1f1e459da1459fb4fff5b63352a1fb
```

**这才是"纯搬迁"该用的证据**: 搬迁前后指纹相同 = 命令面一个字节没变。
(与上一轮修的 `--check` 易变字段问题是同一类: **检查器必须只比稳定内容**, 否则报红/报绿都不可信。)

## 📊 验证

| 项 | 结果 |
|---|---|
| 稳定指纹 (搬后) | `045f029ede3ada43686d5bf3055360452b1f1e459da1459fb4fff5b63352a1fb` |
| `gen_cli_surface.py --check` | ✅ 与提交版一致 (= 表面未变) |
| `check_cli_layers.py` | rc=0 (R1~R8 全过; R2 对 core/view/exp 生效) |
| 全 CLI 模块导入 (walk_packages) | 0 失败 |
| 定向测试 (test_arch / coverage_generator / layering) | **214 passed** |
| 冒烟 10 条 | 8 条 rc=0; `diff compare` / `expression build` rc=2 是**缺必填参数**的正常用法错误 (带 `--help` 均 rc=0) |
| 全量 canonical | **3334 passed / 0 failed** (0 退化) |

## 💡 关键发现 / 决策

1. **"搬前扫描单"把风险前置了**: 上一轮踩的 3 类盲点 (from-import / 按路径读源码 / `__file__` 深度运算)
   这次一次扫清, 且额外发现 `.sh` 脚本里的引用 (上一轮我只看 `.py`)。
   → 说明"把踩过的坑固化成工具"确实有效, 比"下次小心"可靠。
2. **验证手段本身也会骗人**: md5 假警报提醒我 —— 用一个含易变字段的指纹做等价性证明,
   等于每天都在赌运气。**先让证据稳定, 再用它下结论**。
3. **分层与拆分解耦**: `trace.py` (1819 行, 跨 core/view) 与 `visualize.py` (2380 行, 10 命令)
   本轮只搬不拆。目录先对、结构后优 —— 每步都可单独回退。

## 📋 P1b 剩余

| 子步 | 内容 |
|---|---|
| P1b-3 | 拆 `trace.py` (signal → core/semantic, overview → view) + `visualize.py` (10 命令各自成文件) |
| P2 | `fix*` 三文件拆分: 只读 → `core/diagnose`, 会写文件 → `tools/`; snapshot 目录迁 `$SVQ_CACHE_DIR` |
| P3 | `svq exp ...` 前缀 + 别名过渡 (命令路径最后一次变更) |

## 📎 产物

- 目录: `src/cli/{core/{locate,state,semantic},view,dev}/` (13 文件 `git mv` + 7 个 `__init__.py`)
- 工具: `gen_cli_surface.py --fingerprint` (稳定指纹)
- 引用更新: 见上表 (代码/脚本/注释/文档)
- 文档: 本记录 + `L1_cli_layering.md` + `CURRENT_TODO.md` + `overview.md` + `INDEX.md`
