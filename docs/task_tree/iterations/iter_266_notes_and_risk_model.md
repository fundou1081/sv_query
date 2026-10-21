# Iteration 266: 修 registry 过期 note + `trace impact` 风险分显式标注

**Metadata**:
- **Iteration #**: 266
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-21 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "可以，你先处理一下"）
- **Outcome**: ✅ 成功（4 条过期 note 修正；风险分口径显式化；全量 2291 passed）

## ⚠️ 先更正一个错误判断

上一轮我说「`trace impact` 的风险分级没有数据支撑，依赖被退役的 exp 逻辑」——**这是错的**。
读代码后的事实：

| 项 | 事实 |
|---|---|
| 风险分算法 | `src/cli/core/semantic/trace.py::_calculate_risk`，**完全在 core 内**，自包含 |
| 依赖的数据 | `SVAExtractor` / `CovergroupExtractor` —— **仍在用**（`UnifiedTracer` 的 covergroup 查询也走它们） |
| 是否依赖已退役模块 | **否**（退役的是 `applications/*` 与 `coverage_generator` 等，不是这两个 extractor） |

真实的问题不是"没有数据"，而是**权重是手工魔数、从未标定**：

```
分数 = 路径长度 × 5
     + 扇出 × 2
     + 无 SVA/无覆盖 + 20          ← 真实数据
     + 扇出 >10 ? +15 : >5 ? +10
     + 信号名含 clk|clock + 20
     + 信号名含 rst|reset + 20
     + 有条件驱动 + 10
等级: ≥ min_risk(30) → HIGH; ≥ 18 → MEDIUM; 否则 LOW
```

实测 `trace impact calc_chain.a -f calc_chain.sv`：8 条路径**全部 HIGH（32~34 分）**
——因为"无覆盖 +20"这一项几乎对所有未加断言的设计都成立，于是等级退化成"全都 HIGH"。

## 🔧 改动

### 1. 四条过期 registry note

| 命令 | 旧 note | 新 note |
|---|---|---|
| `design show` | 「[缺口] 仅 3 测试文件」 | 「IP 级设计理解; 仅 **1** 个测试文件 (覆盖缺口)」 |
| `arch show` | 「[计划] 迁 VizData 统一渲染」 | 「项目架构总览 (L1 模块 + L2 端口)」 |
| `trace overview` | 「[计划] 归入 view/overview」 | 「两个信号之间的综合叙述 (dataflow + controlflow + evidence)」 |
| `visualize datapath` | 「[缺口] 0 测试」 | 「定点计算架构图; 0 个测试文件 (只有 fixture 名引用, 覆盖缺口)」 |

前两条「[计划]」在仓库里**没有任何 task 文件或文档承接**（grep 全仓只出现在 registry 与生成的
CLI_SURFACE），属于孤儿计划 —— 留着会让 agent 以为这两件事在推进。

### 2. 风险分口径显式化（不删功能，标注限制）

- `impact` 的 docstring 写清公式、阈值、以及"这是相对排序不是绝对风险"
- JSON 输出增加 `result.risk_model = "heuristic_v1 (未标定; 仅用于相对排序)"`
  （**向后兼容**：只加字段，不改既有字段）
- [`docs/KNOWN_LIMITATIONS.md §3.4`](../../KNOWN_LIMITATIONS.md) 新增条目，用可观察后果描述：
  同一设计里等级退化成全 HIGH、跨设计不可比、要标定必须拿真实 bug 位置做验证

## 📊 量化

| 指标 | 前 | 后 |
|---|---|---|
| 命令数 | 34 | 34（本迭代不删命令） |
| 过期 note | 4 | **0** |
| 全量门禁 | 2291 passed | **2291 passed / 0 failed** |

## 💡 决策

1. **不删 `trace impact`**：它的"影响传播"部分是实打实的图遍历，只有风险分是启发式。
   删掉整个命令等于把有用的一半一起扔掉。
2. **不删风险分**：它至少在**同一张图内**能排序（先看哪条路径），比没有强。
   但必须显式标注，否则 agent 会把它当标定过的度量去做决策。
3. **修计划类 note 而不是保留**：没有 task 承接的"计划"就是假承诺，registry 是 agent 的
   真相源，不能带假承诺。

## 🔗 相关

- 限制登记: [KNOWN_LIMITATIONS §3.4](../../KNOWN_LIMITATIONS.md)
- 前序: [iter_265 删 view 3 命令](iter_265_view_trim.md)
