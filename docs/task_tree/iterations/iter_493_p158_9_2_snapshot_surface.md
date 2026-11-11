# iter_493 — P158.9.2 快照保真与能力面矩阵

- **日期**: 2026-11-11 深夜
- **任务**: [PLAN] P158.9.2 snapshot surface 矩阵（current item）
- **触发**: arch_eval P0.2 评审采纳（方豆确认）："缺失字段要么补齐要么显式声明不保证，
  不许中间态"
- **结果**: ✅ 完成（10 测试 + 8 门禁全绿）

## 1. 实测损失面（先测量后动手，不照抄 review 字段清单）

用 `dataclasses.fields` 与 live 图逐字段对比（minimal_3module 31n/72e、
dataflow_budget 19n/33e）：

| 字段 | 补齐前实测损失 | arch_eval 描述 | 结论 |
|---|---|---|---|
| condition_chain | 32/32 非空全丢 | 提及 | 实锤；dataflow.py:238 回退消费 → 查询可见分叉 |
| source | 44/44 非空全丢 | 提及 | 实锤 |
| function_return / is_function_call | 0（fixture 无覆盖） | 提及 | 仍补齐（1 行成本） |
| node.extra | 16 条（direction/width） | 未提及 | review 漏了 |
| effective_condition | 0（add_edge 重算 72/72） | 说"会丢" | review **偏差**：实际无损，无需序列化 |
| condition_ast | 15 非空（运行期 AST） | 提及 | 显式不保证（不可 JSON） |

## 2. 改动

- `graph/models.py`:
  - `to_dict`：edge 增 condition_chain / function_return / is_function_call /
    source(asdict) / extra；node 增 extra（`_filter_json_safe` 只留 JSON-safe 值）
  - `from_dict`：对称恢复；旧快照（无新键）→ 默认值，向后兼容
  - `_SIGNAL_SOURCE_FIELDS` 过滤未知键（前向兼容）
- `docs/dev/SNAPSHOT_SURFACE.md`（新，已登记 INDEX）：
  字段级 + 命令级快照能力面权威矩阵；`trace evidence` 快照路径实测为
  location-only 降级（无 snippets）
- 契约 §3 增快照保真段；§11 表 P158.9 → ✅

## 3. 机械 gate

- 新增 `sim/tests/unit/test_p158_9_2_snapshot_surface.py`：10 passed
  （字段往返 / condition_ast 锁定 None / source 派生 property / extra direction /
  effective_condition 重算 / 旧格式兼容 / CLI live-vs-snapshot parity）
- 受影响子集：json_contract + include_control + trace_schemas +
  dataflow budget + data_edge + golden → **107 passed**（含中途一次
  NameError 假失败：后台测试恰逢 models.py 编辑破窗导入，重跑即绿）
- 8 个门禁 exit 0（check_plan 583 项 / check_docs strict / check_crap：
  from_dict CC 20→26 存量超阈值不拦截）

## 4. 边界与诚实声明

- 快照体积 +33%（fixture 实测 31698B → 42235B）；默认 64MB 上限不变
- unit 全量未在本轮重跑（上轮 860 passed 后 models.py 序列化路径有改动，
  影响面=快照路径，live 路径不经过 to_dict/from_dict；parity 测试覆盖 CLI 链路）
- `condition_ast` / class/covergroup 状态 / 非 JSON-safe extra：显式不保证
  （矩阵 §1），不是遗漏
- 另一 agent 的"经验回放"提交 `3530f163` 按方豆指示保留在旁路分支
  `replay/agent-3530f163`，main 恢复到 `b0958ff5` 基线后开工本任务

## 5. 交接

- current item → **P158.12 P2 清理**（26 硬编码路径 / no:randomly no-op /
  空 expression self-loop）
- 快照矩阵维护规则见 SNAPSHOT_SURFACE.md §4
