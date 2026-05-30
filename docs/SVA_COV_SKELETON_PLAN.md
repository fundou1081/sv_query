# SVA / Covergroup Skeleton 代码生成方案

> 更新日期: 2026-05-30
> 目标: 生成可直接编译的 SVA/Covergroup 骨架代码
> 原则: 降低工程师 review 难度，渐进式补充

---

## 1. 背景与目标

### 1.1 现状
- sv_query 能识别高风险无覆盖路径
- 当前只输出文本建议（"建议对 stage1_valid → stage2_valid 添加 SVA"）
- 工程师需要手动编写 SVA/Covergroup 代码

### 1.2 目标
- 根据缺口自动生成**可编译**的 SVA/Covergroup 骨架
- 生成代码应该**简洁、可读、可修改**
- 关键部分用 `// TODO: 工程师补充` 标注，不代替工程师思考

### 1.3 设计原则

| 原则 | 说明 |
|------|------|
| **最小化骨架** | 只生成必要结构，不填充业务逻辑 |
| **渐进式补充** | 生成后工程师逐步完善，而非一步到位 |
| **易于 review** | 每个断言独立成块，注释清晰，一眼看出意图 |
| **模板化** | 握手/FIFO/CDC/数据路径 分别对应不同模板 |

---

## 2. SVA Skeleton 生成

### 2.1 输入输出

```bash
# 命令行
python run_cli.py sva skeleton -f top.sv --gap --output /tmp/sva/

# 输出
/tmp/sva/
├── sva_0_handshake_protocol.sv      # 握手协议断言
├── sva_1_data_path_pipeline.sv       # 数据路径断言
├── sva_2_cdc_path.sv                 # CDC 路径断言
└── summary.md                        # 汇总说明（便于 review）
```

### 2.2 覆盖的场景模板

#### 模板 A: 握手协议 (Valid-Ready)

**适用场景**: `din_valid → din_ready` 握手类信号

```systemverilog
// sva_0_handshake_protocol.sv
// ============================================================
// 握手协议断言骨架
// 目标: 验证 valid-ready 握手机制的正确性
// 生成日期: 2026-05-30
// ============================================================

`timescale 1ns/1ps

module sva_handshake_protocol断言;
    // ------------------------------------------------------------
    // 接口定义 - 需要工程师根据实际接口填充
    // ------------------------------------------------------------
    // TODO: 替换为实际信号
    // input logic clk;
    // input logic rst_n;
    // input logic valid;
    // input logic ready;
    // input logic [31:0] data;

    // ------------------------------------------------------------
    // 握手基本规则
    // ------------------------------------------------------------

    // 规则 1: valid 和 ready 同时为高时，数据传输发生
    // TODO: 根据实际协议决定是否需要此断言
    property handshake_transfer;
        @(posedge clk) disable iff (!rst_n)
        valid && ready |-> ##1 valid throughout (ready[->1]);
    endproperty

    // 规则 2: valid 不能在 ready 为低时撤消（除非 reset）
    // TODO: 根据实际协议调整
    property valid_no_drop_without_ready;
        @(posedge clk) disable iff (!rst_n)
        valid && !ready |-> valid until_with ready;
    endproperty

    // 规则 3: ready 可以在任何时候撤消/建立
    // 此规则通常不需要断言，仅作说明

    // ------------------------------------------------------------
    // 断言实例化
    // ------------------------------------------------------------
    // a_handshake_transfer: assert property (handshake_transfer);
    // a_valid_no_drop: assert property (valid_no_drop_without_ready);

endmodule
```

**Review 要点：**
```
工程师只需关注：
1. 接口定义（TODO 部分）是否符合实际信号
2. 断言规则是否符合协议规范
3. 需要删除/修改哪些规则
```

---

#### 模板 B: 数据路径流水线 (Pipeline)

**适用场景**: `stage1_data → stage2_data → result` 多级流水线

```systemverilog
// sva_1_data_path_pipeline.sv
// ============================================================
// 数据路径流水线断言骨架
// 目标: 验证流水线数据传递的正确性
// 生成日期: 2026-05-30
// ============================================================

`timescale 1ns/1ps

module sva_data_path_pipeline断言;
    // ------------------------------------------------------------
    // 流水线信号 - 需要工程师根据实际填充
    // ------------------------------------------------------------
    // TODO: 替换为实际信号
    // input logic clk;
    // input logic rst_n;
    // input logic [31:0] stage1_data;
    // input logic [31:0] stage2_data;
    // input logic [31:0] result;
    // input logic stage1_valid;
    // input logic stage2_valid;

    // ------------------------------------------------------------
    // 流水线数据传递规则
    // ------------------------------------------------------------

    // 规则 1: 数据从 stage1 传递到 stage2（1 周期后）
    // TODO: 确认延迟周期数是否符合设计
    property data_stage1_to_stage2;
        @(posedge clk) disable iff (!rst_n)
        stage1_valid && stage1_data == $past(stage1_data)
        |=> stage2_valid && stage2_data == $past(stage1_data);
    endproperty

    // 规则 2: 数据从 stage2 传递到 result（1 周期后）
    // TODO: 确认延迟周期数是否符合设计
    property data_stage2_to_result;
        @(posedge clk) disable iff (!rst_n)
        stage2_valid
        |=> result == $past(stage2_data);
    endproperty

    // 规则 3: 无气泡传递（连续 valid）
    // TODO: 如果允许气泡，删除此规则
    property no_bubble_in_pipeline;
        @(posedge clk) disable iff (!rst_n)
        stage1_valid && stage2_valid && result
        |=> stage1_valid[*1:$] throughout (stage2_valid && result);
    endproperty

    // ------------------------------------------------------------
    // 断言实例化
    // ------------------------------------------------------------
    // a_stage1_to_stage2: assert property (data_stage1_to_stage2);
    // a_stage2_to_result: assert property (data_stage2_to_result);
    // a_no_bubble: assert property (no_bubble_in_pipeline);

endmodule
```

**Review 要点：**
```
工程师只需关注：
1. 信号名称是否正确
2. 周期延迟（|=> 后面）是否符合设计
3. 气泡规则是否允许
```

---

#### 模板 C: CDC 路径 (Cross Clock Domain)

**适用场景**: `clk_a` → `clk_b` 跨时钟域路径

```systemverilog
// sva_2_cdc_path.sv
// ============================================================
// CDC 路径断言骨架
// 目标: 验证跨时钟域数据传递的正确性
// 生成日期: 2026-05-30
// 警告: CDC 断言需要同步器，此骨架假设已有 2-FLOP 同步器
// ============================================================

`timescale 1ns/1ps

module sva_cdc_path断言;
    // ------------------------------------------------------------
    // CDC 信号 - 需要工程师根据实际填充
    // ------------------------------------------------------------
    // TODO: 替换为实际信号
    // input logic clk_a;        // 源时钟
    // input logic clk_b;         // 目标时钟
    // input logic rst_n;
    // input logic [31:0] data_in;    // 源域数据
    // input logic [31:0] data_sync;  // 同步后数据（目标域）

    // ------------------------------------------------------------
    // CDC 基本规则
    // ------------------------------------------------------------

    // 规则 1: 目标域数据稳定后不再变化（已被同步器保护）
    // TODO: 确认数据同步延迟周期数
    // 注意: 此断言假设数据经过 2-FLOP 同步器，延迟 2 周期
    property cdc_data_stable;
        @(posedge clk_b) disable iff (!rst_n)
        $changed(data_in) |=> ##2 data_sync == $past(data_in, 2);
    endproperty

    // 规则 2: 首次上电后数据有确定初始值
    // TODO: 如果没有确定的初始值要求，删除此规则
    property cdc_initial_value;
        @(posedge clk_b) disable iff (!rst_n)
        $rose rst_n |-> ##5 data_sync != 'x;  // 5 周期后数据有效
    endproperty

    // ------------------------------------------------------------
    // 断言实例化
    // ------------------------------------------------------------
    // a_cdc_stable: assert property (cdc_data_stable);
    // a_cdc_init: assert property (cdc_initial_value);

endmodule
```

**Review 要点：**
```
工程师只需关注：
1. 同步器类型（2-FLOP / 3-FLOP）决定了延迟周期数
2. 初始值断言是否符合设计预期
3. 是否需要添加其他 CDC 规则（如多 bit 数据的 Gray 码检查）
```

---

### 2.3 生成逻辑

```
输入: 高风险缺口路径列表
      [
        ('stage1_valid', 'stage2_valid', 'handshake'),
        ('stage1_data', 'stage2_data', 'pipeline'),
        ('data_a', 'data_sync', 'cdc'),
      ]

处理:
  1. 对每个路径，分析其特征（握手/流水线/CDC）
  2. 根据特征选择对应模板
  3. 填充信号名，保留 TODO
  4. 输出独立文件 + summary.md

输出:
  - 多个 .sv 文件（每个路径一个）
  - summary.md（汇总说明）
```

### 2.4 Summary.md 示例

```markdown
# SVA Skeleton 生成报告

生成日期: 2026-05-30
输入文件: top.sv

## 生成断言列表

| # | 类型 | 源信号 | 目标信号 | 文件 | 风险 |
|---|------|--------|-----------|------|------|
| 1 | 握手 | din_valid | din_ready | sva_0_handshake.sv | HIGH |
| 2 | 流水线 | stage1_data | result | sva_1_pipeline.sv | MEDIUM |
| 3 | CDC | data_a | data_sync | sva_2_cdc.sv | CRITICAL |

## Review 检查清单

- [ ] 确认每个文件中的信号名称与实际一致
- [ ] 确认周期延迟（|=> 后面）是否符合设计
- [ ] 确认哪些 TODO 需要填充，哪些可以删除
- [ ] 检查是否有遗漏的边界条件

## 后续步骤

1. 填充 TODO 部分
2. 运行仿真验证断言正确性
3. 调整边界条件
4. 删除不需要的规则
```

---

## 3. Covergroup Skeleton 生成

### 3.1 输入输出

```bash
# 命令行
python run_cli.py covergroup skeleton -f top.sv --gap --output /tmp/cov/

# 输出
/tmp/cov/
├── cov_0_control_signals.sv       # 控制信号覆盖率
├── cov_1_data_signals.sv          # 数据信号覆盖率
└── summary.md                      # 汇总说明
```

### 3.2 覆盖的场景模板

#### 模板 A: 控制信号 Covergroup

**适用场景**: `valid`, `ready`, `mode` 等控制信号

```systemverilog
// cov_0_control_signals.sv
// ============================================================
// 控制信号覆盖率骨架
// 目标: 验证控制信号的覆盖率完整性
// 生成日期: 2026-05-30
// ============================================================

module cov_control_signals;
    // ------------------------------------------------------------
    // Covergroup 定义
    // ------------------------------------------------------------

    covergroup cg_control @(posedge clk);
        option.per_instance = 1;
        option.comment = "控制信号覆盖率";

        // TODO: 替换为实际信号
        // cp_valid: coverpoint valid {
        //     bins high = {1};
        //     bins low = {0};
        // }

        // TODO: 替换为实际信号
        // cp_mode: coverpoint mode {
        //     bins idle = {0};
        //     bins run = {1};
        //     bins done = {2};
        // }

        // TODO: 根据需要添加 cross coverage
        // cx_valid_mode: cross cp_valid, cp_mode;

    endgroup

    // ------------------------------------------------------------
    // Covergroup 实例化
    // ------------------------------------------------------------
    // cg_control cov_inst = new();

endmodule
```

**Review 要点：**
```
工程师只需关注：
1. coverpoint 是否覆盖了所有合法值
2. 是否需要添加 illegal_bins 或 ignore_bins
3. cross coverage 是否有遗漏
```

---

#### 模板 B: 数据信号 Covergroup

**适用场景**: `data`, `addr` 等数据信号

```systemverilog
// cov_1_data_signals.sv
// ============================================================
// 数据信号覆盖率骨架
// 目标: 验证数据信号的覆盖率完整性
// 生成日期: 2026-05-30
// ============================================================

module cov_data_signals;
    // ------------------------------------------------------------
    // Covergroup 定义
    // ------------------------------------------------------------

    covergroup cg_data @(posedge clk);
        option.per_instance = 1;
        option.comment = "数据信号覆盖率";

        // TODO: 替换为实际信号和期望范围
        // cp_data: coverpoint data {
        //     option.auto_bin_max = 16;  // 自动分成 16 个 bin
        //     
        //     // 边界值
        //     bins zero = {0};
        //     bins max = {'hFF};
        //     
        //     // 典型值（需要工程师根据协议填充）
        //     // bins typical = {...};
        // }

        // TODO: 根据需要添加 cross coverage
        // cp_addr: coverpoint addr;
        // cx_data_addr: cross cp_data, cp_addr;

    endgroup

    // ------------------------------------------------------------
    // Covergroup 实例化
    // ------------------------------------------------------------
    // cg_data cov_inst = new();

endmodule
```

---

### 3.3 生成逻辑

```
输入: 
  1. 约束中引用的条件变量（mode, valid 等）
  2. 高风险数据信号
  3. 约束建议的 cross coverage

处理:
  1. 分析约束中的条件变量 → 生成 control covergroup
  2. 分析高风险数据信号 → 生成 data covergroup
  3. 根据约束建议添加 cross coverage
  4. 输出独立文件

输出:
  - 多个 .sv 文件
  - summary.md
```

---

## 4. 实现计划

### Phase 1: SVA Skeleton 生成器

| 步骤 | 任务 | 优先级 |
|------|------|--------|
| 1.1 | 实现模板选择器（握手/流水线/CDC） | 🔴 |
| 1.2 | 实现 SVA 模板 A（握手协议） | 🔴 |
| 1.3 | 实现 SVA 模板 B（数据路径） | 🔴 |
| 1.4 | 实现 SVA 模板 C（CDC 路径） | 🔴 |
| 1.5 | 实现 summary.md 生成 | 🟡 |
| 1.6 | CLI 命令 `sva skeleton` | 🔴 |

### Phase 2: Covergroup Skeleton 生成器

| 步骤 | 任务 | 优先级 |
|------|------|--------|
| 2.1 | 实现约束 → coverpoint 映射 | 🟠 |
| 2.2 | 实现 control covergroup 模板 | 🟠 |
| 2.3 | 实现 data covergroup 模板 | 🟠 |
| 2.4 | 实现 cross coverage 建议 | 🟠 |
| 2.5 | CLI 命令 `covergroup skeleton` | 🟠 |

---

## 5. 验收标准

### SVA Skeleton
- [ ] `sva skeleton -f top.sv --gap` 生成多个可编译的 .sv 文件
- [ ] 每个断言有清晰的 TODO 标注，工程师知道需要补充什么
- [ ] summary.md 汇总所有生成文件，便于 review

### Covergroup Skeleton
- [ ] `covergroup skeleton -f top.sv --gap` 生成多个可编译的 .sv 文件
- [ ] 每个 coverpoint 有默认 bins，工程师可调整
- [ ] cross coverage 建议有说明，工程师可决定是否采用

### 通用
- [ ] 生成代码可通过编译（无语法错误）
- [ ] 代码简洁，一眼能看出意图
- [ ] 工程师 review 时间 ≤ 5 分钟/文件

---

## 6. 附录：代码模板文件结构

```
src/
├── cli/commands/
│   ├── sva.py           # SVA 相关命令
│   └── covergroup.py    # Covergroup 相关命令
├── generator/
│   ├── sva_skeleton_generator.py     # SVA skeleton 生成器
│   ├── covergroup_skeleton_generator.py  # Covergroup skeleton 生成器
│   └── templates/
│       ├── handshake.sva.template       # 握手协议模板
│       ├── pipeline.sva.template         # 数据路径模板
│       ├── cdc.sva.template              # CDC 路径模板
│       ├── control.cov.template         # 控制信号模板
│       └── data.cov.template            # 数据信号模板
```

---

## 7. 附录：Review 流程

```
工程师收到 sv_query 生成的 skeleton 后：

Step 1: 阅读 summary.md
  → 了解生成了哪些文件，每个文件的用途

Step 2: 逐个文件 review
  → 确认信号名称正确
  → 确认周期延迟正确
  → 决定 TODO 部分如何填充
  → 删除不需要的规则

Step 3: 填充 TODO + 运行仿真
  → 验证断言正确性

Step 4: 提交 code review
  → 附上 sv_query 生成的 summary.md 作为上下文
```

---

## 8. 示例：完整 Review 流程

**输入**: sv_query 识别到 `din_valid → din_ready` 无 SVA 覆盖

**生成文件**: `sva_0_handshake_protocol.sv`

**工程师 Review**:

```
1. 阅读文件 → 看到握手协议模板

2. 检查 TODO 部分:
   // TODO: 替换为实际信号
   // input logic valid;
   // input logic ready;

3. 填充:
   input logic din_valid;
   input logic din_ready;

4. 检查断言规则:
   - 规则 1: valid && ready |-> ... // 符合协议
   - 规则 2: valid && !ready |-> valid until_with ready // 需要调整
     // 因为我们设计允许 valid 在 ready 低时撤消

5. 删除规则 2，添加注释说明

6. 运行仿真，验证通过

7. 提交 code review
```

---

*文档版本: 1.0*
*更新日期: 2026-05-30*