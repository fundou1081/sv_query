# 关键路径分析

基于寄存器级图的**关键路径识别**：通过 SCC 缩点和 DAG 最长路径算法定位时序瓶颈。

## 算法原理

### 1. 寄存器级图构建

```
原始信号图                      寄存器级图
──────────────────              ────────────────
din → stage1_data               din → stage1_data
       ↓                               ↓
stage1_data → stage2_data       stage1_data → stage2_data
       ↓                               ↓
stage2_data → result             stage2_data → result
       ↓                               ↓
result → dout                    result → dout
```

**排除**：时钟边（`CLOCK`/`PosEdge`）、复位边（`RESET`/`NegEdge`）

### 2. 寄存器深度估计

BFS 从主输入（PORT_IN，不含时钟/复位）出发，追踪到目标节点经过的**寄存器级数**：

```
depth = 路径上 REG 节点的个数
```

### 3. SCC 缩点

对于有环图，先用 Tarjan 算法找**强连通分量**（SCC），然后缩点为 DAG。

### 4. DAG 最长路径

在缩点后的 DAG 上，用拓扑排序 + 动态规划找最长路径。

## CLI 用法

```bash
# 关键路径分析（文本输出）
python run_cli.py timing analyze -f top.sv

# JSON 输出
python run_cli.py timing analyze -f top.sv --json

# 最大路径数（默认 5）
python run_cli.py timing analyze -f top.sv --max-paths 10
```

## 输出示例

```
======================================================================
关键路径分析: data_path.sv
======================================================================

  节点统计: 总=20 | 寄存器=6

  关键路径 (按深度排序):
  排名   深度    得分     寄存器路径                         
  ──── ───── ────── ──────────────────────────────
     1     3      6 stage1_data → stage2_data →...
     2     2      3 stage1_data → stage2_data
     3     1      1 stage1_data

  详细路径:

  [1] 深度=3, 得分=6
      din → stage1_data → stage2_data → result
```

## 应用场景

1. **时序瓶颈定位**：深度 ≥ 3 的路径可能是关键路径
2. **流水线设计评估**：检查各阶段的寄存器深度是否均衡
3. **布局布线指导**：高得分路径上的寄存器需要特别关注
4. **与 SVA 时序比对**：SVA `|=>` 深度应与实际路径深度匹配