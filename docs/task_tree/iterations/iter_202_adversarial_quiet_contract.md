# Iteration 202: 对抗性测试第二轮 — `--quiet` 契约违背 (F5)

**Metadata**:
- **Iteration #**: 202
- **Task Tree Level**: L2 (CLI 契约 / 对抗验证)
- **Parent Task**: 方豆 "继续" (延续 iter_200/201 对抗主线)
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ 发现并修复 1 个契约违背 (F5) + 3 条回归测试

## 🎯 本次目标

换面对抗: 打 `--quiet` × JSON × stdout 纯净性、短选项 `-j`、跨命令输出/退出码一致性。

## 🔬 实际结果

### 通过的部分 (无问题)

| 用例 | 结果 |
|---|---|
| `--quiet` + `--json` (成功) | rc=0, stdout 纯 JSON ✅ |
| `--quiet` / `SVQ_QUIET=1` + `--json` (错误) | rc=1, **仍给结构化错误信封** ✅ (quiet 不吞契约) |
| `-j` 短选项 (成功/错误) | 与 `--json` 行为一致 ✅ |
| 未知 flag | rc=2 + 明确提示, 无 traceback ✅ |
| `--quiet` + 错误 | stderr 保留错误信息 ✅ (失败可见) |

### F5 ❌ `--quiet` 并没有真的安静 (契约违背)

`sv_query visualize pipeline -f X --quiet` 实测 **stderr 残留 225 字符 / 6 行**:

```
[Phase 4] target='cordic': configured 46 instance paths for DriverExtractor
[Phase 3] target='cordic': filtered 11 out-of-target nodes (kept 482 within target)
  Pipeline regs: 45
  Control regs: 0
  State regs: 0
  Stages: 1
```

`--quiet` 的文档契约是 "抑制所有 stderr 输出 (给 LLM 消费方)" → 这 6 行是直接违背:
LLM/脚本按契约认为 stderr 应干净。根因: 这些输出绕过日志系统, 直接用
`print(..., file=sys.stderr)` / `typer.echo(..., err=True)`, **不查 quiet 状态**。

### 修复

- `compiler.py` 新增 **`is_quiet()`** (此前只有 `set_quiet`, 输出点无法查询状态);
- `graph_builder.py`: `[Phase 3]` / `[Phase 4]` 两处打印加 `if not is_quiet()` 门控;
- `visualize.py::pipeline`: 4 行摘要 (Pipeline regs / Control regs / State regs /
  Stages) 加同样门控。

实测: `--quiet` → stderr **0 字节** (修复前 225); 默认模式 → 877 字节 (诊断照旧);
`--quiet -j` → stderr 0 + stdout 纯 JSON。

### 回归测试 (追加到 `test_json_contract_adversarial.py`, 共 11 条)

- F5: `--quiet` → stderr 必须为空;
- F5 反向: `--quiet` **不能吞掉错误** (失败信息仍要可见);
- F5: `--quiet -j` → stderr 空 + stdout 纯 JSON。

## 💡 关键发现 / 关键技术 / 决策

1. **"安静模式"要靠输出点自查**: 只要有 `print(..., file=sys.stderr)` 绕过日志系统,
   quiet 就一定漏 —— 修复的正确形状是提供 `is_quiet()` 让输出点自门控
   (而不是在入口统一重定向, 那会掩盖真错误)。
2. **quiet 必须"静音不静错"**: 契约是"无诊断噪声", 不是"无错误" → 反向测试锁住
   错误仍可见 (LLM 才能区分"干净成功"与"安静失败")。
3. **对抗测试换面很有效**: 第一轮打 JSON 契约找到 F1~F4; 第二轮打 quiet/短选项/
   纯净性找到 F5; 两轮都只用了十几组用例。

## 📢 后续

push (31 commit) / `check_regression.py` 阈值 / 受影响测试的 `--no-strict` 清理 /
上游 pyslang trap issue / 可视化契约 (等文本输出稳定后)。

## 📎 关联

- 修复: `src/trace/core/compiler.py` (`is_quiet`)、`src/trace/core/graph_builder.py`、
  `src/cli/commands/visualize.py::pipeline`
- 测试: `sim/tests/cli/test_json_contract_adversarial.py` (F5 × 3)
- 前序: `iter_200_adversarial_json_contract.md`、`iter_201_json_contract_fixes.md`
