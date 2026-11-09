# 待做事项盘点 + 优先级（2026-11-09）

**范围**: PLAN / CURRENT_TODO / docs TODO / architecture backlog / src+tools TODO 扫描 / OpenTitan DV intake
**目的**: 把“文档里的旧债”和“真实下一步”分开，给出一张可执行优先级表。

---

## 1. 代码里的 TODO

扫描：

```text
src/cli, src/trace, tools/agent, tools/benchmark
```

结果：

```text
TODO / FIXME / XXX / HACK: 0
```

结论：

> 当前代码没有显式 TODO/FIXME 债。  
> 真实缺口来自验证任务，不来自代码注释。

## 2. 文档里的待做

| 来源 | 内容 | 状态判断 |
|---|---|---|
| `PLAN.md` P62.2 | 交互式 debug gate | 仍是 gate，未开发；当前计划 current item |
| `PLAN.md` P69.7 | 12×3 硬隔离全矩阵 | 环境限制，长期挂起 |
| `PLAN.md` P88 | 外部 VeriBug | 已放弃 |
| `PLAN.md` P124 | independent task intake | worker 已完成 3 个任务；待执行 |
| `CURRENT_TODO.md` | 仍写 P62.2 + 旧“下一步（审计结论）” | **过期**，与 P98–P124 脱节 |
| `docs/TODO.md` | V6.8/V6.9/V7.0 | **历史/过期**；V7.0 已完成 |
| `docs/ARCHITECTURE_TODOLIST.md` | #1 Step4b、#4 清理、#5/#6 测试 | 旧架构债，已完成主体；剩余低优先级 |
| `docs/TESTING.md` | 测试计数/流程 | 旧计数，需刷新 |
| `docs/EXTRACTION_COVERAGE.md` | 语法覆盖 | 旧日期，需刷新 |
| `docs/KNOWN_LIMITATIONS.md` | 已知限制 | 未纳入 P71/P72/edge evidence |
| `docs/PROJECT_PLAN.md` | 其他 RTL 项目 | 不是 sv_query 核心待办 |

结论：

```text
文档债主要是“过期/重复登记”；
不是新的核心开发工作。
```

## 3. Worker 的 independent intake

Worker 从 OpenTitan DV 产物提取了 3 个任务（不是从我们已有 task JSON 改写）：

| id | source | 类型 | 关键 caveat |
|---|---|---|---|
| `DV-UART-NOISEFILTER-DISCOVERY` | UART testplan `rx_noise_filter` | discovery | direct-driver claim 是 contradicted；必须用 path |
| `DV-I2C-CONTROLLER-HALT-VERIFY` | I2C testplan 3 个 halt testpoint | verify/abstain | tx_pending 是 `unknown`，不是 contradicted |
| `DV-UART-SYSLOOPBACK-PATH` | UART testplan `sys_loopback` | path | 必须 pin `--canonical`，否则 2 vs 3 hops |

这 3 个任务比现有 corpus 更接近真实 verification intent，但只有 3 个，且仍是同一套 RTL。

## 4. 优先级

| 优先级 | 事项 | 为什么 | 成本 | 决策 |
|---|---|---|---|---|
| **P0** | 执行 3 个 independent intake 任务 | 唯一能回答“discovery 是否真实需求 / verify 是否闭环”的证据 | 低 | 先做 |
| **P0.5** | 修 intake 任务的 schema/caveat | direct-driver、unknown、canonical 三个陷阱会污染结果 | 低 | 执行前 |
| **P1** | 刷新 CURRENT_TODO / TESTING / EXTRACTION_COVERAGE / KNOWN_LIMITATIONS | 防止后续基于过期信息决策 | 低 | 可并行 worker |
| **P2** | 第二个真实 block 扩到第三 block | 只有 2 个 block，real-project 8/38；但 intake 还没证明需要更多 | 中 | 等 P0 |
| **P3** | P69.7 硬隔离全矩阵 | 环境成本高，产品问题未定 | 高 | 不做 |
| **P4** | P62.2 interactive debug gate | 不是核心 query/verify；仍是 gate | 中 | 保持 gate |
| **P5** | fault localization / patch | 当前 corpus 0 个 symptom→cause；先看 intake | 高 | 不做 |
| **P6** | discovery/search 功能 | 只有 2 个 discovery 任务，不足以证明需求 | 中 | 等 P0 |
| **P7** | T1 查询成本优化 | 成本主要是模型 search，不是 query latency | 中 | 不做 |
| **P8** | 旧架构 TODO / 文档清理 | 无当前产品影响 | 低 | 有余力再做 |

## 5. 下一步

```text
P125: 执行 3 个 independent intake 任务
  - 先修正 schema/caveat
  - 2 模型
  - 记录 exact / false-confident / false-found
  - 按结果决定：search / more verify / stop
```

不做：

```text
不先加 search
不先做 fault localization
不先优化 I2C T1 成本
不为文档债停工
```
