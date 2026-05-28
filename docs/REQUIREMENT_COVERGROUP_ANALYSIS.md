# Covergroup 分析需求

> 创建时间: 2026-05-28
> 状态: 已实现
> 关联: sv_query Class OOP + 约束追踪

---

## 背景

Coverage 是验证收敛的核心指标，但当前存在两个长期痛点：

1. **covergroup 与 constraint 的一致性**：covergroup 定义的 bin 是否覆盖了 constraint 约束的所有合法/非法空间？是否存在漏定义 illegal bin 的情况？
2. **RTL 信号 coverage 的合理性**：从 RTL 收集的 coverage，其 sample 条件是否合适？bin 定义是否能反映信号的内在特性？

---

## 痛点 1：Covergroup 与 Constraint 一致性

### 问题描述

```systemverilog
class packet;
    rand bit [7:0] addr;
    rand bit [1:0] mode;

    constraint c_addr {
        if (mode == 0) { addr inside {[0:63]}; }
        else { addr inside {[64:255]}; }
    }

    covergroup cg;
        coverpoint addr {
            bins low  = {[0:63]};
            bins high = {[64:255]};
        }
        // ❌ 缺少: mode 的 coverpoint
        // ❌ 缺少: addr x mode 的 cross
        // ❌ 缺少: illegal bin for mode==0 && addr in [64:255]
    endgroup
endclass
```

### 需要解决的问题

| # | 问题 | 期望能力 |
|---|------|---------|
| 1 | constraint 约束了合法空间，covergroup 是否完整覆盖？ | 自动比对 constraint 空间 vs bin 覆盖空间，报告未覆盖区域 |
| 2 | constraint 定义了非法组合，covergroup 是否定义了 illegal bin？ | 检测 constraint 禁止但 bin 未标记 illegal 的情况 |
| 3 | 条件约束 (if/else) 产生的分支，covergroup 是否有 cross 覆盖？ | 检测条件变量是否参与 cross |
| 4 | 约束变量之间存在依赖关系，covergroup 是否反映？ | 检测约束中引用的变量对是否出现在 cross 中 |

### 依赖的图能力

- **变量 → 约束映射** (Q1)：知道哪些变量被哪些约束引用
- **约束详情** (condition chain)：知道条件约束的分支结构
- **约束空间描述**：能表达 "mode==0 时 addr ∈ [0,63]" 这样的约束空间

---

## 痛点 2：RTL 信号 Coverage 合理性

### 问题描述

```systemverilog
// RTL 中定义的 covergroup
covergroup rtl_cov @(posedge clk);
    coverpoint data_bus {
        // ❌ data 信号应该关注数值范围、极值
        bins all = {[0:255]};  // 太粗，没有细分
    }
    coverpoint ctrl_valid {
        // ❌ control 信号应该关注 cross、特殊值
        bins hit  = {1};
        bins miss = {0};
        // 缺少: 与 data_bus 的 cross
    }
endgroup
```

### 需要解决的问题

| # | 问题 | 期望能力 |
|---|------|---------|
| 1 | sample 条件是否合适？ | 分析 covergroup 的采样时钟/使能条件，与信号的时钟域、使能逻辑对比 |
| 2 | data 类信号 bin 是否合理？ | 检查是否覆盖：数值范围、极值 (0, max)、边界值 |
| 3 | control 类信号 bin 是否合理？ | 检查是否覆盖：特殊值、与相关信号的 cross、大小关系 |
| 4 | 涉及的相关信号是否完整？ | 通过信号图追踪 coverpoint 信号的 driver/load，建议需要 cross 的信号 |

### 信号分类建议

| 信号类型 | 特征 | coverage 重点 |
|---------|------|--------------|
| **data** | 多位宽、算术运算 | 数值范围分区、极值、边界、与使能的 cross |
| **control** | 1-4 位、条件判断 | 特殊值 (0, max)、状态转换、与 data 的 cross |
| **addr** | 地址映射 | 地址空间分区、对齐边界、与读写信号的 cross |
| **status** | 状态寄存器 | 状态值覆盖、状态转换、与中断的 cross |

### 依赖的图能力

- **信号驱动/负载追踪**：知道信号的来源和去向
- **数据流路径**：知道信号经过哪些逻辑
- **时钟域分析**：知道 sample 条件是否匹配
- **约束信息**：知道信号的合法取值范围

---

## 实现路径建议

### Phase 1: Covergroup 解析
- 完整提取 covergroup/coverpoint/bins/illegal_bins/cross 结构
- 当前状态：有基础解析（`signal_expression_visitor.py` 中的 `extract_coverage_*` 方法），但标注 `[NOT TESTED]`

### Phase 2: Covergroup ↔ Constraint 比对
- 输入：class 的约束图 + covergroup 结构
- 输出：一致性报告（缺失 bin、缺失 illegal bin、缺失 cross）

### Phase 3: RTL Coverage 合理性分析
- 输入：RTL covergroup + 信号图
- 输出：合理性报告（sample 条件、bin 建议、cross 建议）

---

## 相关文件

- `src/trace/core/visitors/signal_expression_visitor.py` — 已有 coverage 解析桩代码
- `sim/tests/regression/test_covergroup.py` — 已有 covergroup 基础测试
- `sim/tests/regression/test_covergroup_enhanced.py` — 已有 cross coverage 测试
