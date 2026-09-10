# SVA (SystemVerilog Assertions) 分析需求

> 创建时间: 2026-05-29
> 状态: 需求评估
> 关联: sv_query 信号图 + 时序关系

---

## 背景

验证工程师需要知道：**信号图上，两个或多个信号在时序行为上的关系是什么？**

例如：
- `req` 拉高后，`ack` 必须在 3 个周期内拉高
- `valid` 拉高时，`data` 必须稳定
- `grant` 拉高前，`req` 必须先拉高

这些关系可以用 SVA (SystemVerilog Assertions) 表达，也可以从 RTL 信号图中推断。

**最终目标**：检查信号图推断的时序关系是否与 SVA 定义一致，发现遗漏的 assertion。

---

## 核心问题

### Q1: 信号之间有哪些时序关系？

从信号图 + RTL 行为推断：
- **因果关系**：A 驱动 B（A 是 B 的 driver）
- **时序依赖**：A 变化后 B 必须在 N 个周期内变化
- **条件关系**：当 C 为真时，A 和 B 有特定关系
- **互斥关系**：A 和 B 不能同时为真

### Q2: SVA 定义了哪些时序关系？

从 SVA 语法提取：
- **sequence**：时序序列定义
- **property**：时序属性（蕴含、重复、延迟）
- **assert/assume**：检查点

### Q3: SVA 是否覆盖了信号图中的所有关键关系？

比对：
- 信号图中有因果关系的信号对 → 是否有对应的 assertion？
- SVA 中的 assertion → 是否覆盖了所有关键信号对？

---

## SVA 语法结构

### Sequence（序列）

```systemverilog
sequence s1;
    @(posedge clk) a ##1 b;          // a 后一个周期 b
endsequence

sequence s2;
    @(posedge clk) a ##[1:3] b;      // a 后 1-3 个周期 b
endsequence

sequence s3;
    @(posedge clk) a ##0 b;          // a 和 b 同一周期
endsequence
```

### Property（属性）

```systemverilog
property p1;
    @(posedge clk) a |-> b;          // a 蕴含 b
endproperty

property p2;
    @(posedge clk) a |=> b;          // a 蕴含下一个周期 b
endproperty

property p3;
    @(posedge clk) disable iff (!rst_n) a |-> b;
endproperty

property p4;
    @(posedge clk) a[*3] |-> b;      // a 连续 3 个周期后 b
endproperty
```

### Assert/Assume/Cover

```systemverilog
assert property (p1) else $error("fail");
assume property (p1);  // 形式验证假设
cover property (p1);   // 覆盖率
```

---

## 实现方案评估

### 方案 A: SVA 提取器 + 信号图比对

**思路**：
1. 提取 SVA 中的信号引用和时序关系
2. 从信号图中提取信号间的因果关系
3. 比对两者，发现不一致

**优点**：
- 直接利用现有信号图
- 可以发现"信号图有关系但 SVA 没覆盖"的情况

**缺点**：
- SVA 时序关系（##1, |->）难以从信号图推断
- 需要额外的时序分析能力

### 方案 B: SVA 结构化提取 + 覆盖分析

**思路**：
1. 提取 SVA 的 sequence/property/assert 结构
2. 分析每个 assertion 覆盖了哪些信号
3. 检查关键信号是否被 assertion 覆盖

**优点**：
- 实现相对简单
- 可以回答"哪些信号有 assertion 保护"

**缺点**：
- 不分析时序关系的具体内容
- 只做覆盖检查，不做一致性检查

### 方案 C: 混合方案（推荐）

**Phase 1**: SVA 结构化提取
- 提取 sequence/property/assert 的完整结构
- 提取涉及的信号及时序操作符（##1, |->, [*3] 等）
- 输出结构化数据

**Phase 2**: SVA 信号关联
- 将 SVA 中引用的信号映射到信号图节点
- 建立 assertion → 信号 的关联关系

**Phase 3**: 覆盖分析
- 检查关键信号对是否有 assertion 保护
- 检查 assertion 是否覆盖了所有时序关系类型

**Phase 4**: 时序关系比对（远期）
- 从信号图推断时序关系
- 与 SVA 定义比对

---

## 数据模型建议

```python
@dataclass
class SVASequence:
    """SVA sequence 结构"""
    name: str
    signals: List[str]          # 涉及的信号
    timing_ops: List[str]       # 时序操作符 (##1, ##[1:3], etc.)
    clock: str                  # 时钟
    source_file: str = ""

@dataclass
class SVAProperty:
    """SVA property 结构"""
    name: str
    sequences: List[str]        # 引用的 sequence
    signals: List[str]          # 涉及的信号
    operators: List[str]        # 操作符 (|->, |=>, [*n], etc.)
    disable_iff: str = ""       # disable iff 条件
    clock: str = ""

@dataclass
class SVAAssertion:
    """SVA assertion 结构"""
    kind: str                   # "assert" | "assume" | "cover"
    property_name: str          # 引用的 property
    message: str = ""           # 错误消息
    signals: List[str] = field(default_factory=list)

@dataclass
class SVAReport:
    """SVA 完整报告"""
    sequences: List[SVASequence]
    properties: List[SVAProperty]
    assertions: List[SVAAssertion]
    signal_assertion_map: Dict[str, List[str]]  # signal → assertion 列表
```

---

## 与现有架构的关系

```
SVAExtractor (新增)
       ↓
SVAReport (独立数据模型)
       ↓
UnifiedTracer.get_sva_report() → 查询入口
       ↓
SVAAnalyzer (后续)
       ↓
信号图 ↔ SVA 比对报告
```

---

## 相关文件

- `src/trace/core/visitors/signal_expression_visitor.py` — 已有 SVA 桩代码
- `sim/tests/regression/test_sva.py` — 已有 5 个基础测试
