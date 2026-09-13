# Iteration 199: `timing analyze --json` 字段级验收测试

**Metadata**:
- **Iteration #**: 199
- **Task Tree Level**: L2 (输出契约 / 验收标准)
- **Parent Task**: iter_198 后续 (方豆 "按你的推荐，补测吧")
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ 8 条字段级验收测试 (模板与 pipeline 版一致)

## 🎯 本次目标

iter_197 审计发现 `timing analyze` **已有 `--json`** 但缺字段级测试; iter_198 把
"文本结构化输出"标准落到 `pipeline`。本轮用**同一模板**补上 timing 的验收测试
(可视化继续冻结)。

## 🔬 实际结果

实测字段 (cordic pipeline 语料):

```json
{ "ok": true, "command": "timing analyze",
  "result": { "total_nodes": 395, "reg_count": 3,
              "critical_paths": [ { "depth", "score", "registers", "full_path" } ] } }
```

新增 `sim/tests/cli/test_timing_analyze_json.py` (8 条, 全绿):

| # | 验收点 |
|---|---|
| 1 | stdout 是**纯 JSON** (`json.loads` 直接可用) |
| 2 | 信封 `{ok, command, result}` — 与 `visualize pipeline --json` **一致** |
| 3 | `result` 字段固定: `total_nodes` / `reg_count` / `critical_paths` |
| 4 | `critical_paths[i]` 字段固定: `depth` / `score` / `registers` / `full_path` |
| 5 | `reg_count <= total_nodes` 且均为非负整数 |
| 5 | 每条 path: `depth>=1`、`score>=1`、`registers` 非空且 **⊆ `full_path`** |
| 5 | `--max-paths N` 生效 (返回条数 ≤ N) |
| 5 | 语义一致性: `reg_count == 0` 时 `critical_paths` 必须为空 |

**注意**: 第 8 条我**没有**把具体数值写死 (避免把实现细节当契约); 只锁"语料语义 →
结构化输出"的一致性。这是从 iter_195 的教训来的 (`rankdir=LR` 那条断言早已与实际
脱节, 因为把实现细节当成了契约)。

## 💡 关键发现 / 关键技术 / 决策

1. **模板复用见效**: pipeline 版定下的 5 类断言 (纯 stdout / 信封 / result schema /
   嵌套 schema / 语义不变量) 直接套到 timing, 40 分钟内完成 —— 验收标准一旦
   "可执行化", 复制成本很低。
2. **不把数值写死**: 只断言字段存在性与不变量 (⊆ 关系、计数关系、`--max-paths` 生效),
   避免重蹈 `rankdir=LR` 的覆辙。
3. **两个命令的信封现已统一**: `visualize pipeline --json` 与 `timing analyze --json`
   都是 `{ok, command, result}` → LLM/脚本可以统一消费。

## 📢 后续

push (28 commit) / `check_regression.py` 阈值 / 受影响测试的 `--no-strict` 清理 /
上游 pyslang trap issue / 可视化契约 (等文本输出稳定后)。

## 📎 关联

- 测试: `sim/tests/cli/test_timing_analyze_json.py`
- 同模板: `sim/tests/cli/test_visualize_pipeline_json.py` (iter_198)
- 审计: `iter_197_text_output_audit.md`
