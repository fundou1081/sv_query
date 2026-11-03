# Primary Features (主要功能)

**Status**: Stable, actively maintained.

**Audience**: 需要查询 RTL 信号因果、条件、位精确来源与结构一致性的工程师/agent。

**Last updated**: 2026-11-03（可视化退役；核心查询/校验为准）

---

## 🎯 核心能力

| 命令 | 价值 |
|---|---|
| `drivers` / `loads` | 谁驱动/使用这个信号；跨模块、位精确 |
| `trace fanin/fanout` | 带 depth/condition/evidence 的追踪 |
| `paths` / `dataflow analyze` | A→B 路径、latency、跨模块 |
| `controlflow analyze` | if/case 条件树 |
| `trace evidence` | 源码 + enclosing always/if |
| `trace profile` / `manifest` | 波形 path → canonical + 类型/时序元数据 |
| `verify consistency` / `claim` / `structural` | 结构一致性 + 可反驳 claim + 对称性 findings |
| `scope` / `instances` / `hierarchy` / `ports` / `params` | 设计入口与上下文 |
| `class` / `trace constraints` / `trace covergroup*` | class 关系、constraint 约束、covergroup 采样/rand |

---

## 🚫 已退役

以下全设计图能力已于 2026-11-03 退役：

- `visualize graph/dataflow/pipeline/chain/module/teach/datapath`
- `arch show`
- `design show`

原因与后续方向见 [structural_review_plan_2026-11-02](architecture/structural_review_plan_2026-11-02.md)。  
动态子图 / 局部 review artifact 将作为新的 core/view 能力重新设计。

---

## 工作流

```bash
# 1. 看谁驱动
sv_query drivers top.y -f top.sv --json

# 2. 看条件
sv_query controlflow analyze top.y -f top.sv --json

# 3. 看源码证据
sv_query trace evidence top.y -f top.sv --json

# 4. 验证 claim
sv_query verify claim --claim '{"kind":"driver","signal":"top.y","driver":"top.a"}' -f top.sv --json
```

---

## 深度文档

- [DATAFLOW.md](DATAFLOW.md)
- [CONTROL_FLOW.md](CONTROL_FLOW.md)
- [EVIDENCE_FEATURE.md](EVIDENCE_FEATURE.md)
- [architecture/json_contract_2026-10-31.md](architecture/json_contract_2026-10-31.md)
