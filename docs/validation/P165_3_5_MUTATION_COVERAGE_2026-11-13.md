# P165.3.5 mutation coverage: 20 tasks

**日期**: 2026-11-13
**状态**: ✅ 完成
**前置**: P165.3.4 (14 mutations)

## 1. 扩展

新增 6 个：

```text
multi_driver_literal
generate_bit_select
wrapper_passthrough_swap2
wrapper_passthrough_path2
mux_case_default_driver
simple_path_driver_removed
```

当前 20 个任务覆盖：

```text
drivers       9
loads         1
paths         5
controlflow   4
dataflow      1
```

## 2. 结果

```text
20 passed / 0 failed / 0 invalid
detection_rate = 20 / 20 = 1.0
```

关键新增：

| task | mutation | 验证 |
|---|---|---|
| `multi_driver_literal` | 给 `p2_0` 增加第二驱动 `1'b1` | driver 集合新增 `1'b1` |
| `generate_bit_select` | `din[i]` → `din[0]` | `top.din[1]` → `top.din[0]` |
| `wrapper_passthrough_swap2` | `rvalid=bready` → `wvalid` | driver 切换 |
| `wrapper_passthrough_path2` | 同上 | `paths.found: true → false` |
| `mux_case_default_driver` | case default `f→g` | driver `f` → `g` |
| `simple_path_driver_removed` | `data=din` → `data=0` | path 消失 |

## 3. 边界

- 仍是 mutation fault injection，不是历史 bug benchmark；
- 20 个任务仍不足以做统计结论；
- `detection_rate=1.0` 只表示查询事实跟随 mutation；
- multi-driver mutant 只验证集合变化，不验证多驱动冲突严重度；
- pico 任务依赖本机外部 `picorv32.v`。

## 4. 运行

```bash
python3 tools/agent/mutation_faults.py \
  --tasks tools/agent/task_corpora/mutation_faults_pilot.json --json
```

## 5. 测试

```text
sim/tests/unit/test_mutation_faults.py
  5 passed
```

新增 multi-driver + generate 的 CI 覆盖。
