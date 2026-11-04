# 长程结构查询对照基准（设计）

**日期**: 2026-11-05
**PLAN**: P69
**核心场景**: 源代码位置上很远，连接/数据流结构上很近。

---

## 1. 要回答的问题

不是“sv_query 有多少命令”，而是：

> 对同一类跨文件、跨层次、名字还可能变化的连接问题，
> 源码阅读、词法搜索和结构查询分别要付出多少成本，才能得到正确答案？

---

## 2. 可对比的对象

| 代号 | 对照 | 代表什么 | 首轮是否做 |
|---|---|---|---|
| **B0** | 强模型 source-only agent（read/grep） | 当前最常见的 debug 方式 | ✅ 主对照 |
| **B1** | 纯词法搜索（rg + 简单启发式） | “grep 能不能找到”下界 | ✅ 便宜 |
| **B2** | ctags/tree-sitter 符号索引 | 语法感知但没有数据流 | 可选 |
| **B3** | 直接写 pyslang 脚本 | 有 semantic，但没有查询层/契约 | 可选 |
| **T1** | sv_query 直接查询（确定性） | 工具本身正确性 | ✅ |
| **T2** | 同一 agent + sv_query | 产品形态 | ✅ 主对照 |
| B4 | 全仓库长上下文一次性阅读 | 检索是否是瓶颈 | 仅小规模 |
| B5 | Verdi/nTrace 等商业调试 | 工业 gold standard | ❌ 无环境 |

**主比较**：`B0 vs T2`。  
**辅助比较**：`T1 vs B1`（工具正确性/成本），`T2 vs T1`（agent 是否会用工具）。

---

## 3. 任务域

任务必须满足至少一条：

1. 答案的源文件与提问文件相距 ≥2 个文件或 ≥200 行；
2. 结构距离 ≤2 跳（连接/数据流）；
3. 跨层次名字发生变化（端口重命名、wrapper、generate、class 成员）；
4. 位级映射/切片，词法上无法直接看出。

### 任务族

| 族 | 例子 | 结构事实 |
|---|---|---|
| A 驱动/负载 | “`rd_inst.m_axi_araddr[0]` 的直接驱动是谁？” | fanin/fanout |
| B 端口↔内部 | “顶层 `s_axi_awvalid` 连到哪个子模块端口？” | connection/path |
| C 跨模块路径 | “`src` 能否到 `dst`，经过哪些实例？” | paths/dataflow |
| D 位级映射 | “`din[7:4]` 映射到哪个内部 bit？” | bit parent/range |
| E class 成员 | “`top.e.p.addr` 对应哪个类型成员/约束？” | class instance/member |

首选本地真实设计：picorv32、verilog-axi、SERV。  
每个任务记录：文件/行范围、结构距离、是否重命名、允许工具、标准答案。

---

## 4. Ground truth 冻结协议

禁止用被测工具的输出直接当唯一 ground truth。

1. **人工源码追踪**：标注文件/行/端口/实例，写出证据链；
2. **独立语义脚本**：用 pyslang/UnifiedTracer 直接枚举，不由候选 agent 调用；
3. 两者一致 → 冻结；不一致 → 剔除或标记争议；
4. 冻结后对 agent 隐藏答案文件；
5. 任务作者与解题 agent 角色分离（当前由我构造时，至少保留双来源记录）。

---

## 5. 指标

### 准确度

- **Exact**：答案节点/路径/端口集合完全匹配；
- **Set F1**：多答案任务的部分匹配；
- **Path exact**：路径节点序列匹配（允许等价的并行路径时单列）；
- **Abstention correctness**：该说 unknown/ambiguous 时是否正确；
- **False-confident rate**：答案错误但 agent 明确自信的比例（主指标）。

### 成本

- input/output tokens；
- tool calls 数；
- wall time；
- 读入源码字节/行数；
- sv_query cold build 与 warm query 分开计；
- cache 命中/复用；
- `cost_per_correct = 总成本 / 正确任务数`。

### 稳定性

- 同任务 3 次运行；报告 pass@1 / 一致率；
- 超时/崩溃/空答案单独计数，不当作错误答案混入。

---

## 6. 首轮实验

- 12–15 个任务，三设计；
- B0 / B1 / T1 / T2 四臂；
- 同一模型、同一 system prompt、同一预算、web disabled；
- T2 只多一个 `sv_query` 工具说明，不加额外提示；
- 先 pilot，确认任务不含泄漏、评分可复现，再扩到 30–50。

---

## 7. 预期与反预期

**预期**：T1 在结构事实上接近 100%（按定义），T2 比 B0 的 false-confident 更低，
但 cold build 会使单任务成本不一定更低。

**反预期**：在小设计/强模型/答案可从命名直接猜到时，B0 可能同样准确；
此时应报告“没有优势”，而不是挑任务。

**必须报告**：

- 任务选择偏差；
- ground truth 的构造者偏差；
- sv_query 失败/歧义案例；
- 成本口径（token 估算 vs 实测）。
