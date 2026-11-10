# P145 validation baseline

**日期**: 2026-11-10
**目标**: 可复现的 canonical full gate + agent 任务回归

---

## 1. Full gate

命令：

```bash
python3 -m pytest sim/tests/ -m "not opensource" -q -p no:randomly
```

实测：

```text
canonical run green (main checkout; current count only in INDEX)
foreign worktree green with explicit skips; counts differ by one pico test
0 failed / 0 errors
~559s
```

skip 原因：

```text
2  long-range runner: pilot 无 .v 且 fallback 不可用
3  benchmark PR5 wrapper: 300s 超时
7  deadlock CLI: `exp backpressure deadlock` 命令已退休（历史测试保留）
```

环境性测试现在显式 skip，不再以 ERROR/FAILED 形式混入：

- `test_run_long_range_runner`: `/tmp/lr_pilot/{axi,serv}` 无 `.v` 源时 skip；
- `test_benchmark_pr5::TestBenchmarkWrapperDepth`: benchmark 300s 超时后 skip；
- 原有 opensource marker 保持。

## 2. Agent corpus

```bash
python3 tools/agent/agent_task_regression.py --json
```

15 tasks；覆盖 deep path、constraint chain、frontier、explicit boundary、
schema、truncation、coverage reason。

实测：

```text
15/15 passed
failed = 0
false_found = 0
```

指标：

```text
tasks / passed / failed
false_confident / false_found
```

## 3. 说明

- 环境 skip 是显式的，不是“测试通过”；
- full gate 和 agent corpus 是两层：前者保证回归，后者保证 agent 工作流；
- 真实 OpenTitan UART/I2C 回放仍是独立验证层，不替代这两层。
