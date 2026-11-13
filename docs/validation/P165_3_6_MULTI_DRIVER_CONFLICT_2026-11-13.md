# P165.3.6 multi-driver conflict mutation

**日期**: 2026-11-13
**状态**: ✅ 完成
**前置**: P165.3.5 (20 mutations)

## 1. 目标

不是只检查“driver 集合多了一个元素”，而是验证
`drivers` 的冲突事实随真实多驱动 mutation 改变：

```text
driver_count
multi_driver
driver_conflict
```

## 2. 新任务

`multi_driver_conflict_simple`：

```verilog
// before
assign data = din;

// after
assign data = din;
assign data = en;
```

查询：

```bash
sv_query drivers top.data -f <mutant> --json -q
```

期望：

| 字段 | before | after |
|---|---|---|
| `driver_count` | 1 | 2 |
| `multi_driver` | false | true |
| `driver_conflict` | `none` | `possible` |

## 3. 实现

`tools/agent/mutation_faults.py` 的 driver facts 增加：

```text
driver_count
multi_driver
driver_conflict
conditional_drivers
```

`multi_driver_conflict_simple` 由 Verilator `--lint-only -Wno-fatal`
验证 mutant 可 elaborate（多驱动会出 lint warning，但不是 fatal）。

## 4. 结果

```text
21 passed / 0 failed / 0 invalid
detection_rate = 21 / 21 = 1.0
by_query: drivers 10 / loads 1 / paths 5 / controlflow 4 / dataflow 1
```

## 5. 这证明了什么 / 没证明什么

证明：

- `multi_driver=false` 的单驱动基线，在加入第二个无条件源后变成 `true`；
- `driver_conflict` 从 `none` 变成 `possible`；
- mutation runner 能区分“源集合增加”和“冲突状态变化”。

没证明：

- 不是对 OpenTitan/真实 RTL 多驱动问题的复现；
- `driver_conflict=possible` 不是完整的冲突证明；它只是当前
  `driver_stats` 的状态；
- 没有覆盖位级/端口多驱动的全部边界。

## 6. 测试

```text
sim/tests/unit/test_mutation_faults.py
  6 passed
```
