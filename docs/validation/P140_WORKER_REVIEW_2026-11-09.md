# P140 worker independent review

**Worker**: `svq-p140-review`（DeepSeek，独立 worktree）
**HEAD**: `34fa78c2`
**Verdict**: **APPROVE WITH NITS**

---

## 结论

P140 的正常路径和负例成立：

- I2C S1 显式 boundary 链可复核；
- 空 map 停在 frontier；
- 缺 evidence 明确失败；
- core 不自动跨 FIFO；
- 不改图。

## Nits 已修

| # | 问题 | 修复 |
|---|---|---|
| M1 | 语法合法但语义不可信的 map 被 `status=traced` 过度宣称 | 增加 `proven:false`、`asserted_relation`、`boundary_hops` |
| M2 | CLI 非零退出时丢掉 stdout 结构化错误 | 先解析 stdout，再报 error/unknown |
| M3 | 多个 boundary 静默选第一个 | 增加 `status=ambiguous` + candidates |
| M4 | 缺 positive/ambiguity 测试 | 新增 6 个测试 |
| M5 | 文档命令 cwd 不可复现 | 补 `cd` + 绝对 map 路径 |
| M6 | malformed boundaries 崩溃 | 显式 JSON error |
| M7 | map 校验不完整 | 非空 src/dst/kind、重复、src==dst |
| M8 | evidence 只指 wrapper wiring | 标明 explicit assertion + 真实行号 |
| M10 | 核心 docstring 含 OpenTitan 示例 | 改为通用 `packed_bus[12]` |
| M11 | 退出码未文档化 | 文档补 0/2/1 |

## M9

全量 pytest 受外部 fixture/benchmark 环境限制，不把“全绿”当作 P140 证据；
P140 以 targeted regression + 真实 I2C 回放为准。
