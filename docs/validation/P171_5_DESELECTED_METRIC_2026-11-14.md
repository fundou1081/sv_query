# P171.5 deselected / unexecuted 口径

**日期**: 2026-11-14
**状态**: ✅ 完成

## 1. 123 deselected 是什么

canonical：

```bash
pytest sim/tests/ -m "not opensource"
```

的 `123 deselected` 就是：

```text
114 opensource passed + 9 opensource skipped = 123
```

它们是 **opensource suite**，由：

```bash
pytest sim/tests/ -m opensource
```

实际执行。

所以：

```text
canonical deselected = 本轮未选，不是从未执行
```

## 2. 修复

`report_status.py`：

- `deselected` 不再写进 `unexecuted`；
- 新增独立 `deferred` 计数；
- `render_report` 显示 `deferred=N`；
- `is_fully_green` 要求 `deferred=0`；
- 真实 never-executed = 显式 skipped / external_not_run / unexecuted。

双套件合并示意：

```text
canonical:  passed=2744 ... deferred=123
opensource: passed=114 ... skipped=9
TOTAL:      passed=2855 ... unexecuted=0, deferred=123,
            skipped_with_reason=9
```

`deferred=123` 表示“这 123 个在另一个 suite 执行”，不能和 9 个 skip 相加成 132 unexecuted。

## 3. 测试

```text
sim/tests/unit/test_p158_12_6_report_status.py
  8 passed
```
