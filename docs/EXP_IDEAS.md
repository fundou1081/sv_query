# exp 创意清单（已落地为 `svq audit`）

> **性质**: 原 exp 区的 10 条创意 backlog。
> **现状 (iter_288, PLAN P3.3)**: 已**重新设计并落地**为 `svq audit` 的检查项
> （`src/trace/core/analysis/audit.py`）。不是搬回旧代码，而是按"证据 + 候选 + 置信度"
> 重写，每条检查都有回归测试，输出显式标注 `confidence`（pattern / measured / heuristic）。
> **旧实现**仍归档在 `docs/archive/2026-10-20-exp-attic/`（仅作历史参考）。

| # | 想法 | 解决什么问题 | 落地 |
|---|---|---|
| 1 | **自动识别总线协议**（AXI4 / AXI4-Stream / APB / AHB / Wishbone / TileLink-UL），并给出协议的结构语义 | 拿到别人的 RTL，先要知道"这根总线是什么协议、有几个通道、字段怎么摆"，才能问对问题 | `audit` → protocols |
| 2 | **识别 valid/ready 握手对**，判定每对是哪种握手语义（ready 先给 / valid 先给 / 同时 / 依赖型） | 握手协议错是最常见的接口 bug；人工要沿连线逐个核对，容易漏 | `audit` → handshakes |
| 3 | **反压拓扑与死锁候选检测** | 多级流水/总线的反压环路会造成"全部停住"；静态找出可能的环，比跑仿真撞死锁便宜 | `audit` → backpressure_cycles |
| 4 | **SVA 断言抽取与断言覆盖评估** | 想知道"哪些关键信号其实没有任何断言保护"，以及断言写的时序深度与设计是否匹配 | `audit` → assertions |
| 5 | **覆盖率缺口分析 + 自动生成 covergroup** | 手写 covergroup 枯燥且容易漏 bin；希望从 RTL 结构反推应该覆盖什么 | `audit` → coverage（含建议片段） |
| 6 | **验证缺口报告**（高风险但无 SVA / 无覆盖的信号） | 验证资源有限时，需要一个"先验哪里"的优先级列表 | `audit` → verification_gaps |
| 7 | **改动风险分级**（按信号在时钟/复位/数据路径上的位置打分） | 改一行 RTL 时，想快速知道"这次改动会牵连多大范围、风险多高" | `audit` → risk |
| 8 | **约束与随机化可达性**（rand 变量、inline constraint、randomize 调用图，找永远随机不到的分支） | 约束写死会制造"仿真永远走不到"的角落，靠覆盖率掉了才发现太晚 | `audit` → constraints（仅 rand/约束覆盖；**不含可达性求解**） |
| 9 | **跨时钟域检查**（CDC） | 漏两级同步器是经典隐患；静态扫描能在设计早期发现 | `audit` → cdc |
| 10 | **时序关键路径的静态推断** | 没有综合/时序报告时，想从结构上估"哪条组合链最长" | `audit` → timing（结构估计，非综合时序） |

---

**为什么当初一起砍掉**：停在"能跑通 demo"的程度——没有真实项目验证、没有锁定的判定语义、
也没说清失效场景。留在 CLI 里会让使用者误以为可用（输出可能是错的），这比没有命令更糟。

**现在的晋升方式（iter_288）**：全部收进 `svq audit` 一个只读命令，分节输出，
每条带 `confidence`（pattern / measured / heuristic），启发式结果用 candidates 措辞；
`#8` 只做约束覆盖统计，**明确不做可达性求解**（静态不可判定）。
