# Worker-assisted svq_query tool hardening（P99）

**日期**: 2026-11-08
**方式**: OpenCode worker，隔离 worktree，1 turn
**范围**: `tools/agent` only；不改 core/RTL

---

## 1. Worker 使用

```text
new svq-tool-dev --source .../sv_query --mode worktree
chat start --worker svq-tool-dev --max-turns 4 --approved-by user
chat send --expect ... --expect-within 600
chat status
# 完成后审查 diff / 复制改动
chat close
```

结果：1 turn 完成，exit 0，约 3m43s。

---

## 2. Worker 交付

- `compact.js`：纯函数，无 I/O，无第三方依赖；
- `index.js`：只负责校验参数、调用 `sv_query`、委托 compact；
- `test/compact.test.js`：12 个 Node 测试；
- `test/index.js`：目录测试入口；
- `package.json`：`npm test`；
- `tools/agent/README.md`：安装、测试、patch、边界。

行为变化：

- 之前 malformed payload 返回空列表；
- 现在显式 throw，避免“空列表被当成正确答案”。

---

## 3. 验证

```text
node --test tools/agent/svq-query-tool/test/
12 tests, 12 pass, 0 fail
```

真实 3-cell smoke（重装 tool 后）：

| cell | MiniMax | DeepSeek |
|---|---:|---:|
| AXI araddr | 7.6s ✅ | 3.7s ✅ |
| SERV clk path | 4.8s ✅ | 3.8s ✅ |
| Pico adapter fanout | 10.3s ✅ | 3.7s ✅ |

6/6 exact，工具仍可用。

---

## 4. 审查结论

- 未修改 `src/` / `examples/` / RTL；
- 工具名、参数 schema、compact 成功输出不变；
- `ok:false` / 缺 `result` / 缺 signals 现在显式失败；
- `neighbors` 改为并行 fetch drivers/loads；
- 仍需 live integration test 才能覆盖真实 payload drift。

## 5. 后续

- Worker 可以承担独立、可验证的代码/文档任务；
- 复杂任务应拆成 >1 turn，并用 `chat status` 跟踪；
- 主 agent 负责审查 diff、跑回归、合并。
