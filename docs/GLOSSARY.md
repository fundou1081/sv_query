# 术语表 (Glossary)

> **领域术语的唯一命名处。** 同名异义 / 一词多义会让 agent 和人各说各话 ——
> 发现新术语先在这里定名, 再在代码与文档里使用。
> 纪律依据: ub-mode "Model the Domain — Maintain a glossary of domain terms"。
> **最后更新**: 2026-11-02 (P57 纪律合并时建立)

---

## 🔠 分层与能力

| 术语 | 含义 | 本仓库的具体所指 |
|---|---|---|
| **core 层** | 只读的分析内核 | `src/trace/core/`。消费者是 agent, 输出契约只可加字段不可改语义 (不变量 I2) |
| **CLI 层** | 命令行入口 | `src/cli/`。禁止任何文件写操作 (R3) |
| **exp 层** | 实验性能力 | `src/trace/exp/`, 退役后归档到 `archive/2026-10-20-exp-atic`。在 `capabilities` 里显式降级, 不伪装成稳定能力 (I4) |
| **capabilities** | 能力声明 | CLI 输出的能力清单。降级的能力在这里显式标记 (不变量 I4) |
| **单文件 / filelist** | 两种源码输入形态 | `-f/--file` 只接受**单文件**; `--filelist` 接受 `.f` 文件列表。二者混用会触发原生 SIGTRAP (纪律 4) |
| **strict 模式** | 恒定严格 | 不完整 RTL / elaboration 报错直接失败, 不做 graceful degradation。禁 `--no-strict` |

## 🔍 查询与分析

| 术语 | 含义 |
|---|---|
| **fanin / fanout** | 某信号的驱动侧 / 负载侧查询 |
| **drive / load** | 驱动 (谁写这个信号) / 负载 (谁读这个信号) |
| **MIG** | ModuleInstanceGraph —— 实例图, 端口到内部信号的映射 |
| **evidence** | 边级证据: 每条 driver/load 边带 file/line/condition/expression, 可定位到源码 |
| **truth** | 真值层测试 —— 从语义上验证提取结果正确, 而非只比对快照 |
| **snapshot / diff** | 图快照与增量比对, 用于回归定位 |
| **sentinel** | 明确表示"查不到"的返回值 (如 `NO_TREE_MARKER`), 与"出错"用**不同**返回值区分 |

## 🚦 流程与门禁

| 术语 | 含义 | 本仓库的具体所指 |
|---|---|---|
| **三件套** | 完成判定 | 代码 ✅ + 测试 ✅ + 文档 ✅, 缺一即未完成 |
| **计划树** | 全局唯一计划源 | `PLAN.md`, 所有代码修改计划先登记; `CURRENT_TODO.md` 只记"此刻在做什么" |
| **迭代记录** | 只增不减的历史 | `docs/task_tree/iterations/iter_NNN_*.md`, 失败也如实写 |
| **门禁** | 提交前必跑的机械检查 | 见 [dev/WORKFLOW.md](dev/WORKFLOW.md) §5 的检查器表; 全部 0 退出码才算过 |
| **棘轮 (ratchet)** | 复杂度门禁的形态 | 只拦**新增**的、以及从阈值下方**涨过**阈值的复杂度; 存量超阈值的只报告不拦截, 否则历史债会永久阻塞提交 |
| **CRAP** | 复杂度×覆盖率的复合指标 | `CRAP = CC² × (1 − coverage)³ + CC`; 每函数 < 10 是 ub-mode 的目标 |
| **CC** | 圈复杂度 (cyclomatic complexity) | 分支点计数; 无覆盖率时的**复杂度下界** |
| **重复度 (dry score)** | 结构相似度 | Jaccard 相似度; ≥ 0.8 判为重复候选 |
| **变异体 (mutant)** | 被人为改坏的代码 | killed = 测试抓到了; survived = 测试没抓到 (质量缺口); uncovered = 覆盖率没命中, 未执行 |
| **攻击前提** | Attack the Premise | 两个修复共享同一前提却在同一道门失败时, 先写下那个前提、点清谁持有失衡、移除分配, **然后才**开下一个修复 |
| **可撤销** | 允许中途断开的条件 | 手段包括: 未 push 的本地 commit / 独立分支 / 有 revert 记录 |
| **术语表** | 本文件 | 领域术语的唯一命名处 |

## 🔧 工具与依赖

| 术语 | 含义 |
|---|---|
| **pyslang** | SystemVerilog 前端 (Python 绑定), sv_query 的解析/语义来源 |
| **slang** | pyslang 的上游 C++ 实现 |
| **uv** | Python 包管理器 (项目依赖用) |
| **LCOV** | 覆盖率报告格式 (crapper / mutator 读它) |
| **.metrics/** | 工具产物目录 (crapper 的 `crap.edn` / mutator 的 `mutate/`) —— **不入库** |

---

## 维护约定

- 新术语按"分层与能力 / 查询与分析 / 流程与门禁 / 工具与依赖"四组归位;
- 已有术语的含义**只能澄清, 不能改写** —— 改写会让历史文档与代码全部对不上;
- 若某术语在别处 (README / CLI 文档 / 代码 docstring) 有第二种说法, **以本表为准**,
  并把那一处改掉 (而不是在这里加"也可能是")。
