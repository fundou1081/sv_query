# Iteration 198: pipeline 结构化输出落地 (`--json`) — 新验收标准生效

**Metadata**:
- **Iteration #**: 198
- **Task Tree Level**: L2 (输出契约 / 验收标准)
- **Parent Task**: iter_197 审计结论 (方豆 "嗯，去做吧")
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ `visualize pipeline --json` 落地 + 7 条字段级验收测试

## 🎯 本次目标

iter_197 审计结论: `timing analyze` 已有 `--json`, 而 `visualize pipeline`
**完全没有结构化输出** (只有 stderr 人类可读行)。方豆决策"文本结构化输出为检查标准"
→ 本轮给 pipeline 加 `--json` 并把验收测试建在字段上 (可视化继续冻结)。

## 🔬 实际结果

### 实现 (只做导出, 不动分析逻辑)

`src/cli/commands/visualize.py::pipeline`:
- 新增 `--json` / `-j`;
- 在 `detect_pipeline(graph, classification)` 之后: `--json` → 序列化并**直接返回**
  (不渲染可视化):

```json
{ "ok": true, "command": "visualize pipeline",
  "result": { "module", "total_latency", "stage_count",
              "pipeline_regs", "control_regs", "state_regs",
              "stages": [ { "stage_id", "reg_nodes", "comb_nodes", "control_inputs",
                            "data_inputs", "data_outputs", "latency" } ] } }
```

- 信封与 `sv_query timing analyze --json` **一致** (`{ok, command, result}`);
- 诊断/告警 (Pipeline regs / Stages 等) 仍走 **stderr** → stdout 保持纯 JSON;
- 实测 (cordic pipeline fixture): `total_latency=1`, `stage_count=1`,
  `pipeline_regs=45`, `stages[0]` 7 字段齐全。

### 验收测试 `sim/tests/cli/test_visualize_pipeline_json.py` (7 条)

| # | 验收点 |
|---|---|
| 1 | **stdout 是纯 JSON** (无 warning 混入, 可直接 `json.loads`) |
| 2 | 信封与 timing 一致 (`{ok, command, result}`) |
| 3 | `result` 字段**固定** (改字段 = 测试红 = 契约变更可见) |
| 4 | `stages[i]` 字段固定 (7 字段) |
| 5 | 寄存器三分类**互斥** (pipeline ∩ control ∩ state = ∅) |
| 5 | `stage_count == len(stages)` 且每 stage `latency >= 1` |
| 5 | 深 register 链的 `total_latency` ≥ 单级链 (语义不变量) |

→ 7 passed。这样"文本结构化输出"从"决策"变成**可执行的验收标准**。

## 💡 关键发现 / 关键技术 / 决策

1. **"导出" ≠ "重写"**: `PipelineInfo`/`PipelineStage` 现成 → `--json` 只是
   `dataclasses.asdict` + 信封统一, 零分析改动 (风险最小化)。
2. **stdout 纯净性是结构化输出的前提**: 既有实现的诊断都在 stderr (历史选择),
   正好满足"stdout 纯 JSON"; 这点在测试里显式锁住 (第 1 条)。
3. **字段固定断言 = 契约锁**: 用 `set(keys) == 期望集合` 而不是 `>=`, 任何字段
   增删都会让测试红 → 逼着改测试 (= 显式契约变更) 而不是静默漂移。
4. **可视化断言冻结但没丢**: 现有 7~8 条 pipeline SVG 断言保持 skip (iter_188),
   等文本输出稳定后再回来 (方豆决策顺序)。

## 📢 后续

1. `timing analyze --json` 的 `result` 字段审计 + 字段级测试 (对齐本轮做法);
2. push (27 commit) / `check_regression.py` 阈值 / 受影响测试的 `--no-strict` 清理 /
   上游 pyslang trap issue。

## 📎 关联

- 代码: `src/cli/commands/visualize.py::pipeline` (`--json`)
- 测试: `sim/tests/cli/test_visualize_pipeline_json.py`
- 审计: `iter_197_text_output_audit.md`; 决策: `docs/architecture/ventus_viz_assertion_migration.md`
