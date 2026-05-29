# sv_query 设计工程师版开发计划

> 更新日期: 2026-05-29
> 来源: 设计工程师需求评审
> 状态: 规划中

---

## 背景

根据对 sv_query 的设计工程师视角评审，核心需求归纳为 5 类：

| # | 需求类别 | 优先级 | sv_query 现状 |
|---|----------|--------|---------------|
| 1 | 可信度（BUG 修复） | 🔴 P0 | 🟡 有已知问题 |
| 2 | 重构 / ECO 影响分析 | 🔴 P0 | 🟠 半可用 |
| 3 | CDC / 时序 / 面积量化 | 🟠 P1 | 🟡 基础有，深度无 |
| 4 | SVA / Coverage 代码生成 | 🟡 P2 | 🟡 文本建议 |
| 5 | 可视化 & 文档自动化 | 🟡 P2 | 🟢 有基础 |

---

## P0：可信度修复 + 重构/ECO 影响分析

### 1.1 可信度：已知 BUG 修复

**目标**：修复所有已知的"结果不可信"问题

| BUG ID | 描述 | 状态 |
|--------|------|------|
| P3-1 | 拼接表达式产生重复驱动边 | 🟡 待修复 |
| P3-2 | 字面量 4'b0 被当成驱动源，和信号混在一起 | 🟡 待修复 |
| P3-5 | 边信息缺失、驱动语句组装不完整 | 🟡 待修复 |
| P3-6 | 边信息缺失、驱动语句组装不完整 | 🟡 待修复 |

**验收标准**：
- [ ] test_data_path 无重复驱动边
- [ ] 字面量不混入驱动源列表
- [ ] 每条边都有完整驱动语句信息

---

### 1.2 重构/ECO 影响分析（核心场景）

**目标**：让设计工程师在改 RTL 前，能一目了然看到影响范围

#### 1.2.1 跨模块追踪完善

**现状**：ModuleInstanceGraph + PathResolver 设计已完成，但 graph_builder.py 跨模块信号节点缺失

**待完成**：
- [ ] graph_builder.py 支持跨模块信号节点
- [ ] 跨模块路径用不同颜色/层级区分
- [ ] 跨模块路径的边界标注（模块端口）

#### 1.2.2 新增 `trace impact` 命令

**目标**：一键生成"改这个信号的影响摘要"

```bash
# 理想输出
python run_cli.py trace impact -f top.sv --signal MY_CHANGED_SIGNAL

=== 影响范围摘要 ===
信号: top.pipeline.stage1_valid
影响路径: 3 条
  路径 1: stage1_valid → stage2_valid → result_valid
  路径 2: stage1_valid → stall_req
  路径 3: stage1_valid → axi.awvalid

涉及模块: top, pipeline, axi_slave

⚠️ 高风险: stage2_valid 被 3 个下游使用，无 SVA 覆盖
💡 建议: 在改 stage1_valid 前，检查 stall_req 逻辑
```

**待开发**：
- [ ] `trace impact` 命令
- [ ] 影响路径自动聚类（按模块、按风险）
- [ ] 高风险路径自动标注（SVA/Coverage 缺口）

#### 1.2.3 条件驱动增强

**现状**：`--show-conditions` 能显示驱动条件

**增强**：
- [ ] 条件路径单独高亮/分类
- [ ] "条件 A 满足才有效" vs "无条件驱动"的区分
- [ ] 生成改动检查清单（改了条件 A，哪些路径受影响）

---

## P1：CDC / 时序 / 面积量化

### 2.1 CDC 路径量化表

**现状**：能识别跨时钟域路径，但只给拓扑图

**目标**：增加量化摘要

```bash
# 理想输出
python run_cli.py cdc analyze -f top.sv

=== CDC 检测报告 ===
时钟域: 3 个
  clk_a (100MHz), clk_b (50MHz), clk_c (sys_clk)

跨时钟域路径: 12 条
  高风险（无同步器）: 3 条
    - path_A: reg1.clk → reg2.clk (直接跨时钟)
    - path_B: data_in.clk_a → mem.clk_b (组合逻辑跨时钟)
  低风险（有二级同步器）: 9 条

量化统计:
  平均路径深度: 4.2 级
  最长路径: 8 级 (reg_a → ... → reg_b via clk_a→clk_b)
  跨时钟域负载排行: TOP 3
    1. clk_en: 扇出 23
    2. valid: 扇出 18
    3. data: 扇出 12
```

**待开发**：
- [ ] CDC 量化统计表
- [ ] 同步器类型自动识别（一级/两级/握手）
- [ ] 高风险 CDC 路径自动标注

---

### 2.2 Timing 路径周期估算

**现状**：能找关键路径（寄存器深度），但没有时钟周期估算

**目标**：增加"预估时钟周期"字段

**待开发**：
- [ ] 基于时钟频率的路径延迟估算
- [ ] 组合逻辑级数 → 预估延迟（以时钟周期为单位）
- [ ] 超长路径自动标记（> 1 时钟周期）

---

### 2.3 扇出/负载量化报告

**现状**：信号图能看到扇出，但没有量化表

**目标**：生成扇出排行榜 + 负载分布图

```bash
# 理想输出
python run_cli.py stats -f top.sv --fanout-rank

=== 扇出统计 ===
高扇出信号 (TOP 10):
  1. clk: fanout=156 🟠 (时钟网络，考虑用 clock gating)
  2. rst_n: fanout=89 🔴 (复位网络，考虑分时复位)
  3. stall_req: fanout=34 🟡
  ...

时钟/复位网络:
  clk: 156 个负载（建议检查 clock tree 负担）
  rst_n: 89 个负载（建议分模块复位）
```

**待开发**：
- [ ] `stats --fanout-rank` 参数
- [ ] 扇出 > 50 自动建议
- [ ] 负载分布可视化

---

## P2：SVA / Coverage 代码生成

### 3.1 SVA 骨架代码生成

**现状**：能提取 SVA 结构，能指出缺口，但只能给文本建议

**目标**：生成可编译的 SVA 模板代码

```bash
# 理想输出
python run_cli.py sva skeleton -f top.sv --gap

=== SVA 骨架生成 ===
检测到高风险无覆盖路径: 3 条
  1. stage1_valid → stage2_valid (无 SVA)
  2. mem.wr_en → mem.wr_data (无协议 SVA)
  3. axi.awvalid → axi.awready (无握手 SVA)

生成的 SVA 文件: /tmp/top_sva_skeleton.sv
```

**待开发**：
- [ ] `sva skeleton` 命令
- [ ] 基于缺口自动生成 SVA 骨架
- [ ] 协议类断言模板（握手、FIFO、AXI）

---

### 3.2 Covergroup 骨架代码生成

**现状**：能分析覆盖缺口，能从约束建议 cross coverage，但生成的是注释

**目标**：生成可编译的 covergroup 骨架

**待开发**：
- [ ] `covergroup skeleton` 命令
- [ ] 约束 → cross coverage 代码生成
- [ ] 缺 bins 的自动建议

---

## P2：可视化 & 文档自动化

### 4.1 大模块布局优化

**现状**：600+ 节点布局混乱

**目标**：改善大模块可视化效果

**方案**：
- [ ] 分层切图（大模块按模块拆分）
- [ ] 使用 neato 替代 dot（适合中等规模图）
- [ ] 高风险区域自动放大/聚焦

---

### 4.2 CI 集成模板

**现状**：没有 CI 集成

**目标**：提供 GitHub Actions 模板

```yaml
# .github/workflows/sv_query.yml
name: sv_query Analysis
on: [push, pull_request]
jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run sv_query
        run: |
          pip install -e .
          python run_cli.py visualize graph -f rtl/*.sv --dot /tmp/graph.dot
          python run_cli.py verify gap -f rtl/*.sv --json > gap_report.json
      - name: Upload artifacts
        uses: actions/upload-artifact@v2
        with:
          name: sv_query-reports
          path: |
            /tmp/graph.dot
            gap_report.json
```

**待开发**：
- [ ] GitHub Actions 模板
- [ ] GitLab CI 模板
- [ ] 报告自动发布到 PR 评论

---

### 4.3 设计工程师文档

**目标**：增加"设计工程师自检清单"

**待开发**：
- [ ] docs/DESIGNER_CHECKLIST.md
- [ ] 常见场景的"设计习惯建议"
- [ ] 与 SpyGlass/DC/PT 的配合指南

---

## 开发顺序建议

```
Phase 1（P0，可信度优先）:
  1.1 修 P3-1/P3-2/P3-5/P3-6 BUG
  1.2 完善跨模块追踪
  1.3 新增 trace impact 命令

Phase 2（P1，CDC/timing 量化）:
  2.1 CDC 量化统计表
  2.2 Timing 周期估算
  2.3 扇出排行榜

Phase 3（P2，代码生成 + 可视化）:
  3.1 SVA skeleton 生成
  3.2 Covergroup skeleton 生成
  3.3 大模块布局优化
  3.4 CI 集成模板
```

---

## 验收标准

每个 Phase 完成后：

1. **测试通过**：pytest 1071 + 新增测试全部通过
2. **在真实项目上验证**：在 OpenTitan/verilog-axi 上跑通
3. **文档更新**：README + 相关文档同步更新
4. **Git 提交**：每个 Phase 独立 commit + tag