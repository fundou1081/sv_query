# Iteration 215: 彻底移除 strict — 批次 1 (`design.py` 的 7 处 flag 追加)

**Metadata**:
- **Iteration #**: 215
- **Task Tree Level**: L1 (纪律强制 · 执行)
- **Parent Task**: 方豆 "去除默认值, 彻底移除 strict"
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ 批次 1 完成 (设计命令链路恒定严格)

## 🎯 本次目标

按方豆指示**彻底移除 `strict`** (删参数 + 删选项, 工具恒定严格, 无降级通道)。
批次 1 = 最严重的一处: `src/cli/commands/design.py` **生产代码主动追加 `--no-strict`**
(7 处, 在 `_run_cdc` / `_run_protocol` / `_run_handshake` / `_run_backpressure` /
`_run_dataflow` / `_run_timing` 等辅助函数里按 `strict` 参数拼接子进程命令行)。

## 🔬 实际结果

改动 (`src/cli/commands/design.py`):
- 删除 7 处 `if not strict: args.append("--no-strict")`;
- 删除 7 个辅助函数的 `strict: bool` 形参 + 所有 `strict=strict` / 位置参数调用;
- 删除顶层 `design show` 的 `strict: bool = typer.Option(False, "--strict/--no-strict")`;
- `print(f"  Strict: ...")` 移除; JSON 输出的 `"strict"` 字段保留但恒为 `True`
  (兼容下游消费者);
- 文档串里 `--no-strict` 示例改写。

验证:
- `sv_query design show -f <fixture>` → **rc=0** (链路正常);
- `sim/tests/cli/test_design.py` → **10 passed**;
- 全仓 `src/**` 的 `--no-strict` **用法 = 0** (此前 7 处全在 design.py)。

## 💡 关键发现 / 关键技术 / 决策

1. **"用法归零"必须限定范围**: iter_211 我宣称"用法归零", 实际只覆盖 `sim/tests` + `tools`;
   **生产代码 `src/cli/commands/design.py` 仍在替用户追加降级 flag** —— 这比测试里用更严重
   (用户根本没得选)。**结论修正**: 全仓扫描必须以 `grep -rn` 全路径为准, 不能只扫测试目录。
2. **删选项要同步删所有引用**: 删掉 `typer.Option` 后, 残留的 `strict=strict` / 位置参数
   会变成 `NameError` (运行时崩) —— 本次靠"改完立即 `grep` + 冒烟跑命令"抓住,
   而不是只信 `ast.parse` (语法正确但名字未定义)。
3. **恒定严格要保留可观测输出**: JSON 里的 `"strict"` 字段保留为 `True`, 避免破坏下游
   消费者 (行为可观测, 语义已无选择)。

## 📢 后续批次 (iter_214 方案)

| 批次 | 内容 | 状态 |
|---|---|---|
| 1 | `design.py` 7 处 flag 追加 | ✅ 本次 |
| 2 | 4 个 CLI 默认值命令 (arch / backpressure / coverage / design 剩余处) 删 `strict` 选项 | 待做 |
| 3 | API 层 (`_evidence_helpers.build_resolver` / `coverage_gen_demo.generate_covergroup`) 去 `strict` 形参 | 待做 |
| 4 | 9 处生产/脚本 `strict=False` 调用点 | 待做 |
| 5 | 29 处测试 API 级降级 + 随批次暴露的 fixture 修复 | 待做 |
| 6 | 可视化 16 个失败 | 按指示暂缓 |

## 📎 关联

- 方案与清单: `iter_214_strict_default_scan.md`
- 代码: `src/cli/commands/design.py`
