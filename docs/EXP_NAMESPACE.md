# exp layer status (2026-11-15)

> **状态**: `svq exp ...` 统一命名空间已退役；但 **exp 层仍有 6 个直接 hidden 命令**。
> 它们没有 canonical group entrypoint，不是 core，也没有 schema/claim 承诺。
> 历史 exp 资产在 [docs/archive/2026-10-20-exp-attic/](archive/2026-10-20-exp-attic/)。
> 想法记录在 [EXP_IDEAS.md](EXP_IDEAS.md)。

---

## 1. 当前 exp 命令（6）

| 命令 | 说明 |
|---|---|
| `audit` | 启发式 audit/risk/verification gaps；低成熟度 |
| `diagnose` | 编译/依赖问题诊断 |
| `trace impact` | 下游影响面 + **未标定**启发式风险排序 |
| `trace overview` | trace 的概览/摘要 |
| `review render` | finding 局部 SVG/HTML artifact |
| `architecture graph` | 架构图（非全设计图） |

这些命令：

- 默认 **不出现在 help**（`hidden=True`）；
- 默认 **不进 `capabilities`**；需要 `--include-exp`；
- 没有 schema/claim 承诺，只修 bug；
- 不能被写成 core 的“规范入口”。

## 2. 为什么不再有 `svq exp`

2026-10-20 曾整体退役旧的 `svq exp` 命名空间：它没有真实项目验证、没有稳定语义，
却让 agent 以为有 24 个可用工具。

现在保留了少量 **直接 hidden 命令** 做内部/实验用途，但不重新建立统一入口，
避免再次出现“看起来是一层产品能力”的误导。

## 3. 层模型

| 层 | 消费者 | 稳定性 | 默认 capabilities | 说明 |
|---|---|---|---|---|
| `core` | agent | stable | ✅ | 只读事实与语义查询，JSON/schema v1 |
| `view` | human | stable | ✅ | 人眼图/叙述 |
| `exp` | none | unstable | ❌ | 6 个 hidden 直接命令；无 schema |
| `dev` | dev | none | ❌ | 当前无命令 |
| `out` | none | none | ❌ | 会写文件的能力，已移出 CLI → `tools/` |

## 4. 机械规则

- `check_cli_layers.py` R5/R6：exp 名不得出现在 core/view help，也不得进默认 capabilities；
- `gen_cli_surface.py --check`：CLI surface 必须与注册表一致；
- 新增 exp 命令必须显式 `hidden=True`，不得新增 `svq exp` 组。

## 5. 真实入口

命令面的唯一真相源是：

```bash
sv_query capabilities --json
sv_query capabilities --json --include-exp
```

不是本文，也不是旧的 `svq exp --help`。
