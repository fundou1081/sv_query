# CDC 检测

> 更新: 2026-05-31 (反映实际 CDCAnalyzer 实现)

**Clock Domain Crossing (CDC)** 检测：识别跨时钟域的信号路径，发现潜在的亚稳态风险。

---

## 一、实际实现

**类**: `CDCAnalyzer` (位于 `src/trace/core/graph/analyzer/cdc_analyzer.py`)

### 核心方法

```python
class CDCAnalyzer:
    def identify_clock_domains(self) -> Dict[str, Set[str]]
        """识别所有时钟域（按 module 分组）"""
    
    def assign_domains(self) -> Dict[str, str]
        """为每个节点分配时钟域（基于驱动关系传播）"""
    
    def analyze_cdc(self) -> CDCReport
        """分析 CDC 并返回报告"""
    
    def timing_report(self) -> str
        """生成详细时序报告"""
```

### CDCReport 结构

```python
{
    'sync_type': str,           # 同步器类型 (NONE, 2-FLOP, 3-FLOP 等)
    'sync_flops': int,          # 寄存器链长度
    'sync_type_stats': dict,    # 各类型路径数量统计
    'domain_pairs': dict,       # 跨时钟域路径分组统计 {(src_clk, dst_clk): stats}
    'high_risk_paths': list,    # 高风险 CDC 路径列表
    'risk_level': str,          # safe/low/medium/high
}
```

## 问题背景

当数据从一个时钟域传递到另一个时钟域时，如果不经同步器处理，会产生亚稳态问题：

```
时钟域 A (clk_A)              时钟域 B (clk_B)
    │                              ▲
    │      跨域信号              │
    └────────────────────────────┘
         无同步器 → 亚稳态风险
```

## 检测算法

### 1. 时钟域识别

```python
clock_signals = ['clk', 'clock', 'clk_i']
reset_signals = ['rst', 'rst_n', 'reset', 'resetn']
```

每个 module + clock 组合定义一个时钟域。

### 2. 域传播

从时钟信号出发，通过数据流边 BFS 传播，为每个节点分配域归属。

### 3. CDC 路径检测

检测所有**源节点域 ≠ 目标节点域**的边：

```python
if src_domain != dst_domain:
    # 跨时钟域！
```

### 4. 风险评估

| 风险 | 条件 | 说明 |
|------|------|------|
| 🔴 HIGH | 无同步器 | 无 2-flop 同步器 |
| 🟢 LOW | 有同步器 | 路径上有 sync 关键字信号 |

## CLI 用法

```bash
# CDC 检测（文本输出）
python run_cli.py cdc analyze -f top.sv

# JSON 输出
python run_cli.py cdc analyze -f top.sv --json

# 只显示高风险路径
python run_cli.py cdc analyze -f top.sv --high-only
```

## 输出示例

```
======================================================================
CDC 检测报告: cross_clock.sv
======================================================================

  时钟域 (2):
    - top.clk_a
    - top.clk_b

  CDC 路径统计:
    总计: 3
    🔴 高风险: 1
    🟢 低风险: 2

  CDC 路径详情:

  [1] 🔴 top.data_a → top.data_sync
      域: top.clk_a → top.clk_b
      边: DATA | 同步器: ✗

  [2] 🟢 top.ctrl_a → top.ctrl_sync
      域: top.clk_a → top.clk_b
      边: DATA | 同步器: ✓
```

## 已知限制

1. **简化同步器识别**：当前通过信号名含 `sync` 识别，更准确的做法是识别 2-flop 结构
2. **单 module 局限**：跨 module 的 CDC 需要模块间连接分析
3. **异步复位**：未单独处理异步复位的跨域问题

## 应用场景

1. **验证计划**：识别需要 `sync_fifo` 或握手协议的跨域路径
2. **代码审查**：高风险 CDC 路径需要特别检查
3. **lint 集成**：可在 EDA 工具中作为 sign-off 检查项