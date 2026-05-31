# sv_query 设计工程师版开发计划

> 更新日期: 2026-05-29
> 来源: 设计工程师需求评审
> 状态: 规划中

---

## 背景

根据对 sv_query 的设计工程师视角评审,核心需求归纳为 5 类:

| # | 需求类别 | 优先级 | sv_query 现状 |
|---|----------|--------|---------------|
| 1 | 可信度(BUG 修复) | 🔴 P0 | 🟡 有已知问题 |
| 2 | 重构 / ECO 影响分析 | 🔴 P0 | 🟠 半可用 |
| 3 | CDC / 时序 / 面积量化 | 🟠 P1 | 🟡 基础有,深度无 |
| 4 | SVA / Coverage 代码生成 | 🟡 P2 | 🟡 文本建议 |
| 5 | 可视化 & 文档自动化 | 🟡 P2 | 🟢 有基础 |

---

## P0:可信度修复 + 重构/ECO 影响分析

### 1.1 可信度：已知问题

| 项目 | 描述 | 状态 |
|------|------|------|
| P3-1 | Part-Select 驱动边 | ✅ 设计决策（位精确性） |
| P3-2 | 字面量作为驱动边 | ✅ 设计决策（值驱动建模） |
| P3-5 | 边信息缺失 | ✅ 已修复 |
| P3-6 | 驱动语句组装 | ✅ 已修复 |

**结论**：可信度方面没有已知问题 ✅

---

### 1.2 重构/ECO 影响分析(核心场景)

**目标**:让设计工程师在改 RTL 前,能一目了然看到影响范围

#### 1.2.1 跨模块追踪完善

**状态**: ✅ 已完成 (2026-05-30)

**已实现功能**:
- [x] `trace_fanout/fanin` 支持递归深度控制（depth=1/direct, depth=None/穿透）
- [x] 模块实例连接跨模块信号追踪（test_instance_connection.py 3/3 passed）
- [x] `ModuleInstanceGraph` + `PathResolver` 设计完成
- [x] graph_builder.py 跨模块信号节点支持

**剩余增强项**（移至 4.1 可视化增强）:
- [ ] 跨模块路径用不同颜色/层级区分
- [ ] 跨模块路径的边界标注（模块端口）

#### 1.2.2 新增 `trace impact` 命令

**目标**:一键生成"改这个信号的影响摘要"

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

⚠️ 高风险: stage2_valid 被 3 个下游使用,无 SVA 覆盖
💡 建议: 在改 stage1_valid 前,检查 stall_req 逻辑
```

**状态**: ✅ 已完成 (2026-05-30)

- [x] `trace impact` 命令
- [x] 影响路径自动聚类(按模块、按风险)
- [x] 高风险路径自动标注(SVA/Coverage 缺口)

#### 1.2.3 条件驱动增强

**现状**:`--show-conditions` 能显示驱动条件

**增强**:
- [ ] 条件路径单独高亮/分类
- [ ] "条件 A 满足才有效" vs "无条件驱动"的区分
- [ ] 生成改动检查清单(改了条件 A,哪些路径受影响)

---

## P1:CDC / 时序 / 面积量化

### 2.1 CDC 路径量化表

**状态**: ✅ 已完成 (2026-05-30)

**已实现功能**:
- [x] 域传播 BFS 逻辑修复（CLOCK 边应传播域给目标节点）
- [x] 同步器类型自动识别 (NONE / 2-FLOP / 3-FLOP)
- [x] 同步器链长度计算（寄存器链深度）
- [x] 同步器类型分布统计
- [x] 跨时钟域路径统计（按 src_clk → dst_clk 分组）
- [x] 高风险/低风险分类

**报告新增字段**:
- `sync_type`: 同步器类型 (NONE, 2-FLOP, 3-FLOP 等)
- `sync_flops`: 寄存器链长度
- `sync_type_stats`: 各类型路径数量统计
- `domain_pairs`: 跨时钟域路径分组统计
- `high_risk_paths`: 高风险 CDC 路径列表

**待实现**:
- [ ] 时钟频率信息提取
- [ ] 握手协议同步器识别

---
### 2.2 Timing 路径周期估算

**状态**: ✅ 已完成 (2026-05-30)

**已实现功能**:
- [x] cycle_estimate: 预估时钟周期数（基于寄存器深度）
- [x] combo_delay_estimate: 组合逻辑延迟估计
- [x] risk_level: 超长路径风险 (CRITICAL/HIGH/MEDIUM/LOW)
- [x] violation_risk: 时序违例风险
- [x] timing_report(): 量化报告（最大周期数、平均周期数、风险分布）

**报告新增字段**:
- `cycle_estimate`: 预估周期数
- `combo_delay_estimate`: 组合逻辑延迟（级数）
- `combo_nodes`: 组合逻辑节点列表
- `risk_level`: 时序风险等级
- `violation_risk`: 违例风险

**待实现**:
- [ ] 基于时钟频率的实际延迟估算（需 cell library 数据）

### 2.3 扇出/负载量化报告

**现状**:信号图能看到扇出,但没有量化表

**目标**:生成扇出排行榜 + 负载分布图

```bash
# 理想输出
python run_cli.py stats -f top.sv --fanout-rank

=== 扇出统计 ===
高扇出信号 (TOP 10):
  1. clk: fanout=156 🟠 (时钟网络,考虑用 clock gating)
  2. rst_n: fanout=89 🔴 (复位网络,考虑分时复位)
  3. stall_req: fanout=34 🟡
  ...

时钟/复位网络:
  clk: 156 个负载(建议检查 clock tree 负担)
  rst_n: 89 个负载(建议分模块复位)
```

**状态**: ✅ 已完成 (2026-05-30)
- [x] `stats --fanout-rank` 参数
- [x] 扇出 > 50 自动建议
- [x] 时钟/复位网络统计

---

## P2:SVA / Coverage 代码生成

### ⚠️ 已暂停 - 移至 Future Roadmap (2026-05-31)

**决策**: 暂停 SVA/Covergroup skeleton 生成开发
**原因**: 优先级调整，当前聚焦核心功能

### 3.1 SVA 骨架代码生成

**现状**:能提取 SVA 结构,能指出缺口,但只能给文本建议

**目标**:生成可编译的 SVA 模板代码

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

**状态**: ⏸️ Future Roadmap

**待开发** (将来):
- [ ] `sva skeleton` 命令
- [ ] 基于缺口自动生成 SVA 骨架
- [ ] 协议类断言模板(握手、FIFO、AXI)

---

### 3.2 Covergroup 骨架代码生成

**现状**:能分析覆盖缺口,能从约束建议 cross coverage,但生成的是注释

**目标**:生成可编译的 covergroup 骨架

**状态**: ⏸️ Future Roadmap

**待开发** (将来):
- [ ] `covergroup skeleton` 命令
- [ ] 约束 → cross coverage 代码生成
- [ ] 缺 bins 的自动建议

---

## P2:可视化 & 文档自动化

### 4.1 大模块布局优化

**状态**: ✅ 已完成 (2026-05-30)

**已实现功能**:
- [x] 模块聚类 (`cluster_modules`)
- [x] 跨模块边用虚线区分 (`style=dashed`)
- [x] rank 约束智能处理（聚类时自动禁用）
- [x] 完整节点路径作为节点名（避免同名冲突）
- [x] 新增 CLI 参数: `--cluster-modules`, `--layout-engine`

**使用示例**:
```bash
python run_cli.py visualize graph -f top.sv \
  --dot /tmp/graph.dot \
  --cluster-modules
```

**后续增强方向** (单独迭代):
- [ ] neato 力导向布局（适合中等规模图）
- [ ] 跨模块路径用不同颜色/层级区分
- [ ] 跨模块路径的边界标注（模块端口）
- [ ] 高风险区域聚焦模式 (`--focus-risk-threshold`)
- [ ] 分层切图（大模块按子模块拆分输出多图）
- [ ] SVG/HTML 交互式缩放
- [ ] 与波形查看器联动（点击节点显示时序）

**方案**:
- [ ] 分层切图(大模块按模块拆分)
- [ ] 使用 neato 替代 dot(适合中等规模图)
- [ ] 高风险区域自动放大/聚焦

---

### 4.2 CI 集成模板

**现状**:没有 CI 集成

**目标**:提供 GitHub Actions 模板

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

**待开发**:
- [ ] GitHub Actions 模板
- [ ] GitLab CI 模板
- [ ] 报告自动发布到 PR 评论

---

### 4.3 设计工程师文档

**目标**:增加"设计工程师自检清单"

**待开发**:
- [ ] docs/DESIGNER_CHECKLIST.md
- [ ] 常见场景的"设计习惯建议"
- [ ] 与 SpyGlass/DC/PT 的配合指南

---

## 开发顺序建议

```
Phase 1(P0,可信度优先):
  1.1 修 P3-1/P3-2/P3-5/P3-6 BUG
  1.2 完善跨模块追踪
  1.3 新增 trace impact 命令

Phase 2(P1,CDC/timing 量化):
  2.1 CDC 量化统计表
  2.2 Timing 周期估算
  2.3 扇出排行榜

Phase 3(P2,代码生成 + 可视化):
  3.1 SVA skeleton 生成
  3.2 Covergroup skeleton 生成
  3.3 大模块布局优化
  3.4 CI 集成模板
```

---

## 验收标准

每个 Phase 完成后:

1. **测试通过**:pytest 1071 + 新增测试全部通过
2. **在真实项目上验证**:在 OpenTitan/verilog-axi 上跑通
3. **文档更新**:README + 相关文档同步更新
4. **Git 提交**:每个 Phase 独立 commit + tag