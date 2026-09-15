# 归档: `--no-strict` 相关测试 (2026-09-09, iter_210/211)

**归档原因**: 方豆指示 "使用 no strict 明确违反开发纪律, 不可接受, 必须更改"。
AGENTS 核心纪律 1 禁止在 `run_cli.py` / **测试** / 脚本中使用 `--no-strict`。

这三个文件的**存在目的就是测试该 flag 的行为**(断言 `--no-strict` 出现在 `--help` 里、
断言优雅降级后仍能出 partial 结果), 无法通过"删掉 flag"来合规 → 整体移出测试集。

| 文件 | 原位置 | 说明 |
|---|---|---|
| `test_stats_non_strict.py` | `sim/tests/unit/` | 非严格模式下 stats 行为 (13 处 flag) |
| `test_strict_default.py` | `sim/tests/unit/` | 20 个命令的 `--strict/--no-strict` 文档化断言 |
| `test_snapshot_non_strict_mode.py` | `sim/tests/unit/` | snapshot 在非严格模式下的行为 |

**处置方式**: 移出 (不是删除) — 需要时可按本文档路径恢复。
**标签**: 若将来要重新覆盖"用户逃生舱"行为, 应改写为**只测 strict 默认** + 单独的
"逃生舱可用性"用例, 且不得在测试里实际使用该 flag 跑分析 (只断言选项存在)。
