# Iteration 197: 文本结构化输出审计 (pipeline / timing) — 方豆新验收标准

**Metadata**:
- **Iteration #**: 197
- **Task Tree Level**: L2 (输出契约)
- **Parent Task**: 方豆决策 "pipeline timing 现在所有输出都以**文本结构化输出为检查标准**"
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ 审计完成 (差距定位 + 实现路径明确); 本轮**未改代码**

## 🎯 本次目标

按方豆新决策, 摸清 `pipeline` / `timing` 现有结构化输出覆盖度, 定位差距与实现路径
(可视化暂冻结, 断言应建立在结构化文本上)。

## 🔬 审计结果

| 命令 | 现状 | 差距 |
|---|---|---|
| `sv_query timing analyze` | ✅ **已有 `--json`**; 输出信封 `{ok, command, result}` (实测) | 需审计 result 字段稳定性 + 把测试建立在字段上 (现测试多在断言可视化产物) |
| `sv_query visualize pipeline` | ❌ **完全没有结构化输出** — 只有 stderr 的人类可读行:<br>`Pipeline regs: 21` / `Control regs: 0` / `State regs: 5` / `Stages: 20` | **主要缺口**: 需要 `--json` |

### 实现路径 (已定位, 不需新分析逻辑)

`src/trace/core/graph/analyzer/pipeline_viz.py` 已有现成数据结构:

```python
@dataclass
class PipelineStage:  name, registers, combinational_nodes, control_inputs,
                      data_inputs, data_outputs, latency
@dataclass
class PipelineInfo:   module_name, stages[list], total_latency,
                      pipeline_regs, control_regs, state_regs

def detect_pipeline(graph, classification=None) -> PipelineInfo
```

→ `visualize pipeline --json` 只需: 调 `detect_pipeline()` → `dataclasses.asdict()` →
套与 `timing analyze` **相同信封** `{ok, command, result}` → 打 stdout
(诊断/告警仍走 stderr, 保证 stdout 是纯 JSON; 与既有 `--quiet` 机制一致)。

### 风险/注意

- stdout 必须纯 JSON (现有实现已把 warning 走 stderr);
- `total_latency` / `stages[].latency` 的语义需在文档里写死 (cycle 数? 寄存器级数?),
  否则字段"稳定"只是形式;
- 现有 7~8 条 pipeline 可视化断言按决策**冻结**; 新断言建立在 JSON 字段上
  (stage 数 / 每 stage 寄存器集合 / 控制信号集合 / 总延迟)。

## 💡 关键发现

1. **验收标准切换要先确认"结构化输出是否存在"**: 审计发现 `timing` 已有 `--json`,
   而 `pipeline` **一个结构化输出都没有** —— 如果不先审计就按新标准写测试, 会直接卡住。
2. **数据层是现成的**: `PipelineInfo`/`PipelineStage` 已存在 → `--json` 是"导出"而非
   "重写分析", 成本低、风险小 (不动分析逻辑)。
3. **信封统一**: 与 `timing analyze --json` 的 `{ok, command, result}` 对齐, 便于
   统一消费/断言 (而不是各命令自定义 shape)。

## 📢 下一步 (建议顺序)

1. **给 `visualize pipeline` 加 `--json`** (导出 `PipelineInfo`; 信封对齐 timing) +
   测试建立在字段上 → 这是新验收标准的落地;
2. 审计 `timing analyze --json` 的 `result` 字段并补字段级测试;
3. 其余待办: push (26 commit) / `check_regression.py` 阈值 / 受影响测试的
   `--no-strict` 清理 / 上游 pyslang trap issue。

## 📎 关联

- `src/trace/core/graph/analyzer/pipeline_viz.py` (`PipelineInfo` / `detect_pipeline`)
- `src/cli/commands/visualize.py::pipeline`、`src/cli/commands/timing.py`
- 决策: `docs/architecture/ventus_viz_assertion_migration.md` (方豆决策节)
