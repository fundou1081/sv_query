# 项目审计：目标、计划、缺口与下一步

**日期**: 2026-11-06
**范围**: 产品方向 / PLAN / 当前代码 / 测试 / 文档
**结论摘要**: 核心查询与校验已基本完成；下一步的瓶颈是**外部有效性**和**agent 使用成本**，不是继续加功能。

---

## 1. 项目原本目标

来自 [product_direction_2026-10-31](product_direction_2026-10-31.md)：

> sv_query 是 agent 的 RTL 查询 + 客观校验层；让源码阅读的结论可被机器验证或反驳。

三层：

| 层 | 目标 | 当前状态 |
|---|---|---|
| Scope / Inventory | canonical ID、层级、端口、参数 | ✅ 已冻结，够用 |
| Trace / Causality | driver/load、path、condition、profile、evidence | ✅ 主力能力完整 |
| Verify | consistency、claim、structural findings | ✅ 已落地 |

硬约束：

- canonical identity + explicit not_found/ambiguous/unknown；
- 双向一致性 + evidence；
- 动态值由外部波形工具负责；
- 不 inline 函数、不展开 class 内部细节、不做全设计可视化；
- core 只读 + 稳定 JSON；exp 不承诺契约。

---

## 2. 当前实现状态

- 2538 passed / 0 failed（7 skipped / 119 deselected）；
- 39 命令 = core 35 + exp 4；
- 真实项目 smoke：strict_uart / verilog-axi / picorv32 / SERV；
- 查询性能：build 1.8–26 s；warm query 2–15 ms（本机三设计）；
- 12 题双模型对照：T2 两个 seed 都 12/12；source 6–10/12；
- 硬隔离 PoC：sandbox-exec 已验证 repo/CLI deny；只有单题 4 cells；
- HWE-Bench / VeriBugBench：**未跑**；
- 全设计图：已退役；局部 review artifact 仍 exp。

---

## 3. PLAN 状态

| 项 | 状态 | 说明 |
|---|---|---|
| P0–P61 | ✅ | 建图层、bit 精度、路径、校验、可视化清理、局部 review |
| P62.1 | ✅ | finding 局部 SVG/HTML |
| P62.2 | ⏸ | 交互式 debug gate，未开发 |
| P63–P68 | ✅ | class/constraint/covergroup/UVM 静态、regex 纪律、验证包、README |
| P69 | ⏳ | 12 题 + token + seed2 + 硬隔离 PoC；P69.7 全矩阵未做 |
| P71 | ✅ | --top/top_modules、driver_count、bit_fallback |
| P72 | ✅ | filelist 编译错误分类 |

**计划层面的问题**：

- `CURRENT_TODO` 仍保留旧的 P59 清理清单和 P50~P57 表，已过期；
- `TESTING.md` 最后更新 2026-07-29，仍写旧测试计数 / 旧 skip 列表；
- `EXTRACTION_COVERAGE.md` 最后更新 2026-08-27，覆盖率和测试计数过期；
- `KNOWN_LIMITATIONS.md` 最后更新 2026-08-26，未纳入 P71/P72/验证结论。

---

## 4. 未完成开发

### 4.1 战略缺口（最优先）

| 缺口 | 影响 | 状态 |
|---|---|---|
| HWE-Bench / VeriBugBench 外部故障集 | 不能证明真实 debug 有效 | 未跑；无远程 Linux/Docker |
| 12×3 硬隔离矩阵 | 不能量化 source/T2 硬隔离稳定性 | PoC only |
| HWE/VeriBug 修复任务 | 不能证明根因命中率/false-confident | 未做 |

### 4.2 产品/工程缺口

| 缺口 | 影响 | 建议 |
|---|---|---|
| cold build 1.8–26 s | 多轮 agent 查询成本高 | warm query service / 一次构图多查询 |
| 无 agent service/MCP | 只能 shell 调 CLI，易选错命令 | 可在外部 benchmark 后做 |
| 交互式 debug | 未验证是否真是需求 | 保持 gate |
| class 方法 receiver 类型 | `p.set()` 的 target_class 仍可能为空 | 低优先，等真实 UVM |
| UVM 宏/运行时时序 | 仅 syntactic，不能证明 factory override | 明确不承诺 |
| `diagnose timescale` 触发条件 | 命令对输入可能永远“无需修复” | exp/低优先 |

### 4.3 抽取/语义未支持项

来自 `EXTRACTION_COVERAGE.md`（需刷新）：

- `initial` 块不抽取；
- `always_latch` 无 latch 语义；
- 数组整体赋值不生成 driver 边；
- `unique` / `priority case` modifier 丢失；
- `casez` / `casex` 当普通 case，`?` 语义缺失；
- `{W{...}}` 作为 LHS 不识别；
- `always_comb` 的 blocking/nonblocking 元数据恒为 nonblocking；
- 嵌套 ternary >5 层；
- constraint `not inside` / soft / dist 建模受限（部分 pyslang 限制）；
- covergroup 参数化 / `expect` 等 pyslang 限制；
- 动态数组索引按设计不建节点（不是缺陷）。

**这些不是下一步的首要目标**：除非外部 benchmark 证明某类语法是高频根因。

---

## 5. 测试缺口

| 缺口 | 类型 | 说明 |
|---|---|---|
| HWE/VeriBug 端到端 | 外部有效性 | 没有真实故障集 |
| 硬隔离 12×3 | 稳定性 | 只有单题 PoC |
| `verify_long_range.py` 进 CI | 复验 | 目前手动运行 |
| 真实 UVM package | 语义 | 只有 stub fixture；UVM 关系是 syntactic |
| class receiver/polymorphism | 语义 | 方法调用 target_class 不完整 |
| `diagnose timescale` | CLI | 端到端测试仍注释 |
| 不支持语法 | 边界 | `test_spec_unsupported_syntax` 记录预期，不是完整行为测试 |
| 文档计数 | 卫生 | TESTING/EXTRACTION_COVERAGE 过期 |

---

## 6. 下一步建议

### 推荐顺序

1. **先做可复现的外部小样本**
   - 没有远程 Linux/Docker，退一步：安装 iverilog，取 **VeriBugBench Icarus 兼容子集 10–15 例**；
   - 或者只做静态 HWE case 的 query/локализация（不能验证 fail-to-pass，证明力弱）。
   - 目标不是跑分，而是回答：“真实 bug 上，source vs T2 的 false-confident 是否下降？”

2. **再做 warm query service**
   - 只在 benchmark 显示 agent 多轮查询后进行；
   - 目标：一次构图，多次 driver/load/path/profile；
   - 需要 token/time 对比，而不是只看 warm query ms。

3. **最后补文档/测试债**
   - 刷新 TESTING / EXTRACTION_COVERAGE / KNOWN_LIMITATIONS；
   - 更新 CURRENT_TODO；
   - 补 verify_long_range 的 CI 入口；
   - 不要为了覆盖率补不支持语法的测试。

### 不建议现在做

- 继续加 class/UVM/covergroup 功能；
- 全量 12×3 硬隔离；
- 全设计可视化；
- 用内部 hand-made case 继续扩大样本；
- 跑 HWE 全量 417。

---

## 7. 一句话

> 功能层已经够用；现在缺的是**真实故障集上的证据**。
> 没有外部 benchmark，下一步做 warm service 只是优化一个尚未被证明的工作流。
