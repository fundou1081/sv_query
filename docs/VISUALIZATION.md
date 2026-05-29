# 信号图可视化

**sv_query** 提供强大的信号图可视化功能，将信号间的数据流关系、风险等级、验证覆盖状态融为一体，生成可直接用于 code review 的报告图。

## 功能特性

| 特性 | 说明 |
|------|------|
| **数据流边** | 显示驱动/负载关系（而非简单连接线） |
| **风险热力图** | 🔴🔴🔴 → 🟢🟢🟢 按功能复杂度×时序复杂度评分 |
| **覆盖状态标记** | ✓ SVA / 🟡 Coverage / ✓🟡 两者 / 🚨 缺口 |
| **分层布局** | INPUT 在上（rank=source），OUTPUT 在下（rank=sink） |
| **驱动条件** | `--show-conditions` 在边上显示驱动条件 |
| **曲线边** | `splines=spline` 曲线边，更清晰美观 |

## 快速开始

### 安装依赖

```bash
# 安装 graphviz（用于渲染 PNG）
brew install graphviz  # macOS
apt install graphviz  # Ubuntu/Debian
```

### 基本用法

```bash
# 生成信号图
python run_cli.py visualize graph -f top.sv --dot /tmp/graph.dot

# 渲染为 PNG
dot -Tpng /tmp/graph.dot -o graph.png
```

### 高级选项

```bash
# 显示驱动条件
python run_cli.py visualize graph -f top.sv --show-conditions --dot /tmp/graph.dot

# 只看数据流（排除时钟/复位边）
python run_cli.py visualize graph -f top.sv --exclude-clock --exclude-reset --dot /tmp/graph.dot

# 限制边数量（适用于大模块）
python run_cli.py visualize graph -f top.sv --max-edges 100 --dot /tmp/graph.dot

# 输出 Mermaid 格式（用于 Markdown 预览）
python run_cli.py visualize graph -f top.sv --mmd /tmp/graph.mmd
```

## 图例说明

### 节点边框颜色（覆盖状态）

| 状态 | 边框颜色 | 示例信号 |
|------|----------|----------|
| SVA + Coverage 都有 | 🟢 绿色 | `din_valid`, `din_ready` |
| 只有 SVA | 🔵 蓝色 | `stage2_valid`, `pipeline_stall` |
| 只有 Coverage | 🟠 橙色 | （较少见） |
| 无覆盖（高风险） | 🔴 红色 | `stage1_valid`, `result` |

### 节点填充颜色（风险等级）

| 等级 | 填充颜色 | 风险分数 |
|------|----------|----------|
| CRITICAL | 红色 | ≥60 |
| HIGH | 橙色 | 40-60 |
| MEDIUM | 黄色 | 20-40 |
| LOW | 绿色 | <20 |

### 边样式

| 类型 | 样式 | 颜色 | 粗细 |
|------|------|------|------|
| 数据流 | 实线 | 黑色 | 粗（2px） |
| 时钟 | 虚线 | 蓝色 | 细（1px） |
| 复位 | 虚线 | 红色 | 细（1px） |

## 分层布局

信号图自动按节点类型分层：

```
┌─────────────────────────────────────────────────────┐
│  [clk] [rst_n] [din] [din_valid] ...               │  ← rank=source (INPUT)
│          ↓         ↓         ↓                      │
│      [stage1_data] [stage1_valid]                   │  ← REG 层
│              ↓           ↓                         │
│      [stage2_data] [stage2_valid]                  │  ← REG 层
│              ↓           ↓                         │
│      [result]    [result_valid]                    │
│                     ↓                               │
│            [dout] [dout_valid]                      │  ← rank=sink (OUTPUT)
└─────────────────────────────────────────────────────┘
```

## 驱动条件

使用 `--show-conditions` 可以在边上显示驱动条件，格式为 `if (cond) 才驱动`：

### 条件格式

| 条件 | 含义 |
|------|------|
| `rst_n & din_valid & din_ready` | 多条件同时满足 |
| `!pipeline_stall` | 取反条件 |
| `ENABLE_IRQ & irq_pending` | 使能信号 |
| `!rst_n` | 复位条件（清零） |

### 示例

```
din ──────────────────→ stage1_data
   [rst_n & din_valid & din_ready]

stage1 ─────────────────→ stage2_data
   [rst_n & !pipeline_stall]

1'b0 ──────────────────→ result_valid
   [!rst_n]  ← 复位时清零
```

## 开源项目测试

| 项目 | 文件 | 节点 | 高风险缺口 | 说明 |
|------|------|------|------------|------|
| test_data_path | sim/tests/regression/test_data_path.sv | 20 | 3 | 有 SVA/Coverage |
| AXI-RAM | verilog-axi/rtl/axi_ram.v | 83 | 32 | AXI 接口 |
| PicoRV32 | /tmp/picorv32/picorv32.v | 644 | 250 | RISC-V CPU |
| PTP TD Leaf | verilog-ethernet/rtl/ptp_td_leaf.v | 213 | 153 | 以太网时间同步 |
| PCIe DMA | verilog-pcie/rtl/pcie_us_axi_dma_rd.v | 413 | 166 | PCIe DMA 引擎 |

## 与验证缺口检测结合

信号图可以与 `verify gap` 命令结合使用，生成统一的验证缺口视图：

```bash
# 生成验证缺口图
python run_cli.py verify gap -f top.sv --dot /tmp/gap.dot --mmd /tmp/gap.mmd

# 渲染
dot -Tpng /tmp/gap.dot -o gap.png
```

这会高亮显示所有高风险但无 SVA/Coverage 的信号，便于优先补充验证。

---

## AST 缓存功能

### 功能说明

AST 缓存用于避免重复解析未变化的源文件。基于源文件内容的 **SHA256 hash** 判断是否需要重新解析。

### 缓存机制

| 组件 | 是否缓存 | 说明 |
|------|----------|------|
| Graph Building (UnifiedTracer) | ✅ 支持 | `--cache` 参数启用 |
| SVAExtractor | ❌ 每次解析 | 暂未缓存 |
| CovergroupExtractor | ❌ 每次解析 | 暂未缓存 |


### CLI 用法

```bash
# 第一次运行（无缓存）
python run_cli.py visualize graph -f top.sv --dot /tmp/graph.dot

# 第二次运行（使用缓存）
python run_cli.py visualize graph -f top.sv --dot /tmp/graph.dot --cache

# 强制重建缓存
python run_cli.py visualize graph -f top.sv --cache --rebuild
```

### Python API 用法

```python
from trace.unified_tracer import UnifiedTracer
from trace.core.cache import get_cache

# 方式1：build_graph 参数
tracer = UnifiedTracer(sources={'file.sv': source})
graph = tracer.build_graph(use_cache=True)  # 自动检查/更新缓存

# 方式2：管理缓存
cache = get_cache()
cache.cache_stats()   # 查看统计
cache.list_cache()     # 列出所有缓存
cache.invalidate()     # 清除所有缓存
```

### 缓存存储位置

```
~/.svq/cache/<hash>.json
```

缓存文件包含：
- 版本信息 (`version`)
- 源文件 hash (`sources_hash`)
- 完整 Graph 数据（节点、边、驱动关系）


### 性能说明

| 场景 | 效果 | 说明 |
|------|------|------|
| 单次运行 | 无明显提升 | 缓存主要用于重复查询 |
| pytest 测试套件 | ~1% 提升 | 多测试共享缓存 |
| 大文件 (PicoRV32) | 约 700ms | 缓存命中/重新解析耗时相近 |

> ⚠️ 当前实现中，缓存命中与重新解析耗时相近。对于超大模块（500+ 节点），缓存效果更明显。

### 适用场景

| 场景 | 推荐 |
|------|------|
| 多次重复查询同一模块 | ✅ 使用 `--cache` |
| pytest 批量测试 | ✅ 使用 `--cache` |
| 单次分析 | ❌ 不需要 `--cache` |
| 大模块重复可视化 | ✅ 使用 `--cache` |
