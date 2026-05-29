# SVA 分析

SystemVerilog Assertions (SVA) 结构化提取、覆盖分析、时序比对。

## 功能概述

| 命令 | 说明 |
|------|------|
| `sva extract` | 提取所有 SVA 结构（sequence、property、assertion） |
| `sva coverage` | 分析哪些信号有 assertion 覆盖，哪些没有 |
| `sva timing` | 比对 SVA 时序声明与信号图推断的时序深度 |

## 核心概念

### SVA 术语

| 术语 | 说明 |
|------|------|
| Sequence | 时序序列，描述信号在时钟边沿的关系 |
| Property | 时序属性，描述序列之间的蕴含关系 |
| Assertion | assert/assume/cover 声明，对 property 的实例化 |
| `\|->` | 同周期蕴含（SVA 声明 → RTL 行为在同一周期） |
| `\|=>` | 下一周期蕴含（SVA 声明 → RTL 行为在下一周期） |
| `disable iff` | 禁用条件，通常用于异步复位 |

### 时序深度

从信号图推断的时序深度 = 从输入端口到目标寄存器经过的**寄存器级数**

```
SVA 语法     时序深度    说明
──────────────────────────────────────────────
a |-> b         0       同周期（组合逻辑）
a |=> b         1       下一周期（1 级寄存器）
a ##2 b         2       两周期后（2 级寄存器）
```

## CLI 用法

### 提取 SVA 结构

```bash
python run_cli.py sva extract -f top.sv
python run_cli.py sva extract -f top.sv --json
```

输出：
```
================================================================================
SVA 提取: top.sv
================================================================================

  序列 (Sequences): 0
  属性 (Properties): 3
    top.p_aw_w:
      信号: ['awvalid', 'awready', 'wvalid', 'wready']
      操作符: ['|->']
      时钟: clk
    top.p_w_b:
      信号: ['wvalid', 'wready', 'bvalid']
      操作符: ['|=>']
      时钟: clk
      disable iff: disable iff (!rst_n)

  断言 (Assertions): 3
    top.assert_0 [assert]:
      引用: top.p_aw_w
      信号: ['awvalid', 'awready']

  信号关联索引:
    awvalid: ['top.p_aw_w', 'top.assert_0']
    ...
```

### 分析覆盖缺口

```bash
python run_cli.py sva coverage -f top.sv
python run_cli.py sva coverage -f top.sv --json
```

输出：
```
================================================================================
SVA 覆盖分析: top.sv
================================================================================

  覆盖率: 5/16 (31.2%)

  ⚠ 未覆盖信号 (11):
    - result
    - stage1_data
    ...

  已覆盖信号 (5):
    ✓ din_valid
    ✓ din_ready
    ✓ mode
```

### 时序关系比对

```bash
python run_cli.py sva timing -f top.sv
python run_cli.py sva timing -f top.sv --json
```

输出：
```
================================================================================
SVA 时序比对: top.sv
================================================================================

  ┌──────────────────────────────┬────────────┬────────────┬───────────────────────┐
  │ Property                    │ SVA声明   │ 推断深度   │ 信号实际深度          │
  ├──────────────────────────────┼────────────┼────────────┼───────────────────────┤
  │ top.p_w_b                  │ |=>        │          1 │ {'bvalid': 1}        │
  └──────────────────────────────┴────────────┴────────────┴───────────────────────┘
```

## 应用场景

1. **验证完整性检查**：哪些关键信号缺少 assertion？
2. **时序一致性验证**：SVA 声明的周期与 RTL 实际行为是否一致？
3. **覆盖缺口报告**：生成未覆盖信号列表，指导测试用例补充
4. **故障定位**：发现 assertion 失败时，快速定位涉及的信号路径

## 数据模型

```
SVAGraph
├── sequences: Dict[str, SVASequenceNode]
│       ├── signals: List[str]
│       ├── timing_ops: List[str]   # ##1, ##[1:3], [*3]
│       └── clock: str
├── properties: Dict[str, SVAPropertyNode]
│       ├── signals: List[str]
│       ├── operators: List[str]  # |->, |=>
│       ├── clock: str
│       └── disable_iff: str
├── assertions: List[SVAAssertionNode]
│       ├── kind: str             # assert/assume/cover
│       ├── property_ref: str
│       └── signals: List[str]
└── signal_refs: Dict[str, List[str]]  # 信号 → SVA 节点映射
```
