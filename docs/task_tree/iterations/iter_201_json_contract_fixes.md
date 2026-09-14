# Iteration 201: JSON 契约 4 个问题修复 (F1~F4)

**Metadata**:
- **Iteration #**: 201
- **Task Tree Level**: L2 (输出契约)
- **Parent Task**: iter_200 对抗测试发现 (方豆 "先把这几个修了")
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ F1~F4 全部修复 + 8 条对抗回归测试

## 🎯 本次目标

修 iter_200 对抗测试发现的 4 个问题 (方豆: "先把这几个修了")。

## 🔬 实际结果

### F1 错误路径的结构化信封 (契约缺口)

新增 `cli._common.emit_json_error(command, e)`:
`{"ok": false, "command": ..., "error": {"type", "message"}}` → stdout (stderr 保留人读文本)。

挂在**两个层次** (缺一不可):
- 命令内部: `visualize pipeline` / `timing analyze` 的 `except CompilationError` 里
  (json 模式 → 先发信封再走原 handle_compilation_error);
- **CLI 顶层** `main.run()`: 请求了 `--json`/`-j` 时, 逃到顶层的错误
  (FileNotFoundError / UnicodeDecodeError / CompilationError) 也发信封
  (command 从 argv 前两个非 flag token 推断)。

修复前后 (实测):

| 用例 | 修复前 | 修复后 |
|---|---|---|
| `pipeline --json` + 二进制 | rc=1, **stdout 空** | rc=1, `{ok:false, error.type=UnicodeDecodeError}` |
| `timing analyze --json` + 不存在 | rc=1, stdout 空 | rc=1, `{ok:false, error.type=FileNotFoundError}` |
| `pipeline --json` + filelist 缺条目 | rc=1, stdout 空 | rc=1, `{ok:false, error.type=CompilationError}` |

### F2/F3 被 `--json` 忽略的 flag → 显式告警

新增 `warn_flags_ignored_by_json(json_output, flags)`: `--json` 与
`--svg` / `--timing` / `--load-path` / `--unfold` 同时出现 → stderr 一行
`⚠️ --json 已启用: 以下输出/模式选项被忽略 (不产出对应产物): --svg`。
实测: 告警出现且**确实不产出文件** (不再"静默丢弃")。

### F4 `--max-paths` 负值 → 报错

`if max_paths < 0: raise typer.BadParameter("--max-paths 不能为负 (0 = 不输出路径)")`
→ 实测 rc=2 + 明确信息 (过去 rc=0 静默当 0); `0` 仍合法 (反向测试锁住)。

### 回归锁 `sim/tests/cli/test_json_contract_adversarial.py` (8 条)

F1 × 3 (三个错误用例都必须给信封) + F1 反向 (成功信封不变) +
F2/F3 × 2 (告警 + 不产出文件) + F4 正反 (负值报错 / 0 合法)。

## 💡 关键发现 / 关键技术 / 决策

1. **错误信封要挂在两个层次**: 命令内部 catch (编译错误) + **CLI 顶层** (文件/编码
   错误逃逸)。只挂一处会漏 —— 实测 `timing analyze -f 不存在` 就绕过命令内部 catch。
2. **`ok` 字段必须成对出现**: 成功有 `ok:true` 就必须有 `ok:false`, 否则字段本身
   在骗人。这是 iter_200 F1 的本质。
3. **"模式互斥"要显式**: `--json` 改变输出模式后, 其它输出 flag 若不生效就必须告警
   (项目"不静默"原则在 CLI 层的具体化)。
4. **参数校验宁严勿静**: 负值折叠成 0 会让用户无法区分"无结果"与"参数被吞"。

## 📎 关联

- 代码: `src/cli/_common.py` (2 个 helper)、`src/cli/main.py` (`run()`)、
  `src/cli/commands/visualize.py::pipeline`、`src/cli/commands/timing.py::analyze`
- 测试: `sim/tests/cli/test_json_contract_adversarial.py`
- 发现: `iter_200_adversarial_json_contract.md`
