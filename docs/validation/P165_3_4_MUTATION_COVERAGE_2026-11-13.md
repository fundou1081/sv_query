# P165.3.4 mutation coverage expansion

**日期**: 2026-11-13
**状态**: ✅ 完成
**前置**: P165.3.3 (10 mutations)

## 1. 扩展

从 10 个扩到 **14 个**，新增：

```text
ternary condition invert
case selector invert
wrapper passthrough driver swap
wrapper path removed
```

最终覆盖：

```text
driver      5
load        1
paths       3
controlflow 4
dataflow    1
```

## 2. 结果

```text
14 passed / 0 failed / 0 invalid
detection_rate = 14 / 14 = 1.0
```

runner 新增 summary：

```json
{
  "valid": 14,
  "detection_rate": 1.0,
  "by_query": {"drivers": 5, "loads": 1, "paths": 3, "controlflow": 4, "dataflow": 1}
}
```

这比只看 passed 更明确：invalid mutant 不进入 detection 分母。

## 3. 关键新任务

| task | mutation | 验证事实 |
|---|---|---|
| `ternary_condition_invert` | `sel_a ?` → `!sel_a ?` | controlflow 条件 |
| `case_selector_invert` | `case(sel_b)` → `case(!sel_b)` | controlflow case 条件 |
| `wrapper_passthrough_swap` | `rlast=arvalid` → `rlast=awvalid` | driver |
| `wrapper_path_removed` | 同上 | `paths.found: true → false` |

## 4. 边界

- mutation 仍是注入故障，不是历史 bug benchmark；
- 14 个任务不足以做统计结论；
- `detection_rate=1.0` 只表示这套任务上查询事实都跟随 mutation，
  不代表 agent 在真实 debug 中不会 false-confident；
- pico 任务依赖外部 `picorv32.v`；缺失时显式 prepare error。

## 5. 运行

```bash
python3 tools/agent/mutation_faults.py \
  --tasks tools/agent/task_corpora/mutation_faults_pilot.json --json
```
