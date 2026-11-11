# P157 skip cleanup

**日期**: 2026-11-11
**状态**: ✅

## 1. 清理内容

### obsolete deadlock tests（7 skips）

删除：

```text
sim/tests/usage/test_deadlock_cli.py
```

原因：`exp backpressure deadlock` 命令已退休，测试没有继续执行的对象。
Git 历史保留。

### long-range tests（2 skips）

`test_run_long_range_runner.py` 标记：

```python
pytestmark = pytest.mark.opensource
```

依赖 `/tmp/lr_pilot/{axi,serv}`，不再混入 canonical。

### benchmark PR5（3 skips）

`test_benchmark_pr5.py` 标记：

```python
pytestmark = pytest.mark.opensource
```

依赖外部 AXI closure/300s benchmark，不再混入 canonical。

## 2. 结果

```text
before: canonical had 12 skips and 119 deselected
after:  canonical has 0 skips and 139 deselected
```

canonical 不再有未解释 skip。

## 3. 边界

这不代表外部测试通过；它们被明确移出 canonical：

```text
opensource: /tmp fixtures + external AXI
```

仍然可以显式运行：

```bash
pytest -m opensource
```

其中的环境 skip 仍保留，且是显式的。
