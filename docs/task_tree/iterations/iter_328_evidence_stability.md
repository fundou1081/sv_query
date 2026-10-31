# Iteration 328: trace evidence 稳定性（PLAN P32.1）

**Metadata**:
- **Iteration #**: 328
- **Task Tree Level**: L2（PLAN `P32.1`）
- **Created**: 2026-10-31 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "主功能 focus trace，稳定 evidence"）
- **Outcome**: ✅ 完成（赋值行/always 回退；2635 passed）

## 🎯 问题（实测）

`trace evidence` 对 always_ff 驱动：
- `enclosing_always` 缺失（condition_ast 存在时 parent chain 不含 always）
- `source_text` 为空，或指向 `if` 条件行而不是 LHS 赋值行
- `source_location` 行号有 ±1 偏差

## 🔧 实现

| 修复 | 说明 |
|---|---|
| always 回退 | 即使 condition_ast 存在，`assign_type` 是 always 且缺 enclosing_always → 用 semantic 找 always 块 |
| 赋值行定位 | 从源文件按 LHS 找 `<=`/`=` 行，取离 edge hint 最近的一条 |
| snippet 关键字 | pyslang sourceRange 常从关键字之后开始；补回 `always`/`always_ff`/`always_comb`/`assign` 前缀 |
| source_text | 优先真正的 LHS 赋值行；无文件时再退化到 snippet 首行 |

## 📊 效果（sync_fifo）

| 信号 | 修复前 | 修复后 |
|---|---|---|
| `data_out` | source_text 空/条件行，always 缺失，cred 0.4 | `data_out <= 8'd0;`，always+if，cred 1.0 |
| `reg_stage1` | 同上 | `reg_stage1 <= 8'd0;`，always+if，cred 1.0 |
| `full`（continuous） | line 偏移 | `assign full = 1'b0;`，line 23，enclosing_assign |
| 输入端口无 driver | — | 字段稳定为空，cred 0.0（不伪造） |

## 🧪 测试

新增 `test_evidence_stability.py`（3）：
always 赋值行、continuous assign 行、无 driver 端口空证据。
更新 `test_pyslang_v11_cli_smoke` 对 source_text 的旧期望（现在包含 `assign` 关键字）。

## ✅ 验证

- 全量：**2635 passed / 0 failed**
- 契约字段未变（evidence payload 已在 P29 登记）

## 📌 边界

- 同块内同一 LHS 多次赋值时，取离 edge hint 最近的一条；不保证与具体多驱动语义一一对应
- 源文件不可读时回退 snippet 首行，行号可能不精确
- exp 的 `view` 不在此稳定性范围

## 🔗 相关

- 计划: [PLAN.md P32.1](../../../PLAN.md)
- 前序: [iter_327 exp 降级](iter_327_exp_demotion.md)
