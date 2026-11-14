# Experimental Features (exp layer)

**Status**: Experimental, hidden by default. No schema/claim commitment.
**Audience**: 内部调试/探索；不要作为 production 依赖。
**Last updated**: 2026-11-15

---

## 当前 exp 命令（6 个）

这些命令默认不出现在 help，也不进默认 capabilities：

| 命令 | 说明 |
|---|---|
| `audit` | 启发式 audit/risk/verification gaps |
| `diagnose` | 编译/依赖问题诊断 |
| `trace impact` | 下游影响面 + **未标定**风险排序 |
| `trace overview` | trace 概览 |
| `review render` | finding 局部 SVG/HTML artifact |
| `architecture graph` | 架构图（非全设计图） |

列出方式：

```bash
sv_query capabilities --json --include-exp
```

## 约束

- 没有 `svq exp` 统一命名空间入口；
- 不承诺 JSON schema、稳定性、准确性；
- 只修 bug，不扩契约；
- `trace impact` 的 `risk_score` 只能做同图相对排序，不是绝对风险；
- 真实命令清单以 `capabilities --include-exp` 和 [CLI_SURFACE](CLI_SURFACE.md) 为准。
