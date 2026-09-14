# Iteration 203: 对抗性测试第三轮 — 分析层 + 发现 F6

**Metadata**:
- **Iteration #**: 203
- **Task Tree Level**: L2 (CLI 契约 / 分析层)
- **Parent Task**: 方豆 "继续" (对抗主线第三轮, 换面到分析层)
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ 分析层健壮 (10 用例仅 1 项疑似) + 发现并修复 F6

## 🎯 本次目标

换面打**分析层**: generate 嵌套 (双 genvar) / 参数化 class extends / interface modport /
宏生成实例 / 重复 module 定义 / filelist 混合, 共 10 组用例。

## 🔬 实际结果

### 分析层: 健壮 (无崩溃 / 无 traceback / 无假成功)

| 用例 | 结果 |
|---|---|
| generate 双 genvar 嵌套 (graph) | ✅ |
| 参数化 class extends + interface modport (graph) | ✅ |
| 宏生成实例 (`define` 拼接名 `name``_q`) | ✅ |
| 重复 module 定义 (两文件 / filelist) | ✅ 干净报错 (无 traceback) |
| stats 多语言料 filelist | ✅ |
| 各信号 trace fanin/fanout | ✅ (输出端口负载为空 = 正确语义) |

**唯一异常是 F6**, 由一个"输出极短"的启发式触发, 深挖后是真 bug。

### F6 ❌ `trace ... --format json` 输出**被 JSON 转义的字符串**, 不是 JSON 对象

实测 (修复前):

```
$ sv_query trace fanin macro_top.a_q_q -f x.sv --format json
"Fanin of 'macro_top.a_q_q':\n  (no drivers)\n"     ← 一个 JSON 字符串
$ sv_query trace fanin macro_top.a_q_q -f x.sv --json
{"ok": true, "command": "trace_fanin", "params": {...}, ...}   ← 正确
```

根因: 两个入口都在, 但**只有 `--json` 走结构化路径**; `--format json` 落到
`else: output_text(...)` 分支, 而该分支在 `--format` 为 json 时又把文本 `json.dumps`
成字符串 → 消费者拿到"看着像 JSON 的字符串", 无法取字段。

修复: 在 `trace.py` 三处 dispatch (`fanin` / `fanout` / 第三处) 的 `elif format == "dot"`
之后补 `elif format == "json": output_json(data)` → **`--format json` 与 `--json`
走同一实现** (单一路径, 不会再漂移)。

实测修复后: `--format json` → `{ok, command, params, result, errors}` ✅;
`fanout` 同样 ✅。

### 回归测试 (追加 3 条, 该文件共 14 条)

- `--format json` (fanin/fanout) 必须是 **JSON 对象** (不是字符串);
- `--format json` 与 `--json` 顶层键必须一致 (锁"单一实现");
- fixture `macro_inst.sv` 归档到 `sim/tests/fixtures/hostile_input/`。

## 💡 关键发现 / 关键技术 / 决策

1. **"另一个入口"最容易坏**: `--json` 与 `--format json` 两条路只维护了一条 ——
   典型的"别名未收敛"。修复方式不是补文档, 而是**让别名走同一实现**。
2. **"看着像 JSON" 比"不是 JSON" 更危险**: `json.dumps(文本)` 的输出**能**被
   `json.loads` 解析, 但类型是 str —— 静默的契约违背, 消费者要到取字段才炸。
   测试必须断言 **类型** (dict), 不只是"能否解析"。
3. **对抗测试的启发式也会触发真发现**: 最初只是"输出极短"的可疑标记, 深挖成了
   真 bug —— 启发式提示值得追, 不要直接丢弃。
4. **分析层本身这轮没找到问题**: generate 嵌套/参数化 class/宏/重复定义/多语言料
   组合都健壮, 说明前几轮的分析能力工作扎实。

## 📢 后续

push (32 commit) / `check_regression.py` 阈值 / 受影响测试的 `--no-strict` 清理 /
上游 pyslang trap issue / 可视化契约 (等文本输出稳定后)。

## 📎 关联

- 修复: `src/cli/commands/trace.py` (三处 dispatch)
- 测试: `sim/tests/cli/test_json_contract_adversarial.py` (F6 × 3)
- 前序: `iter_200_adversarial_json_contract.md`、`iter_202_adversarial_quiet_contract.md`
