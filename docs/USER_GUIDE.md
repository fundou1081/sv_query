# sv_query 用户指南

**版本**: 2.0
**更新日期**: 2026-06-01

---

## 目录

1. [安装](#安装)
2. [快速开始](#快速开始)
3. [CLI 使用](#cli-使用)
4. [Python API](#python-api)
5. [多文件项目 (Filelist)](#多文件项目-filelist)
6. [可视化](#可视化)
7. [解析范围说明](#解析范围说明)
8. [常见问题](#常见问题)

---

## 安装

```bash
# 从源码安装
git clone https://github.com/fundou1081/sv_query.git
cd sv_query
pip install -e .
```

---

## 快速开始

### CLI 方式（推荐）

```bash
# 查看所有命令
python run_cli.py --help

# 信号图可视化
python run_cli.py visualize graph -f your_module.sv --dot out.dot

# 数据流分析
python run_cli.py dataflow -f your_module.sv --from sig_a --to sig_b

# CDC 分析
python run_cli.py cdc -f your_module.sv

# 时序分析
python run_cli.py timing -f your_module.sv

# SVA 提取
python run_cli.py sva -f your_module.sv

# 风险分析
python run_cli.py risk analyze -f your_module.sv
```

### Python API

```python
from trace.unified_tracer import UnifiedTracer

# 解析文件
with open('your_module.sv') as f:
    source = f.read()
tracer = UnifiedTracer(sources={'your_module.sv': source})
tracer.build_graph()

# 获取图
graph = tracer.get_graph()
print(f"节点数: {len(graph.nodes())}")
print(f"边数: {len(graph.edges())}")

# 获取适配器
adapter = tracer._get_adapter()
modules = list(adapter.get_modules())
for module in modules:
    name = adapter.get_module_name(module)
    print(f"Module: {name}")
```

---

## CLI 使用

### 主要命令

```bash
python run_cli.py <command> [options]
```

| Command | 功能 |
|---------|------|
| `trace` | 信号追踪 (fanin/fanout/impact) |
| `diff` | 比较两个版本 |
| `snapshot` | snapshot 管理 |
| `dataflow` | 数据流路径分析 |
| `controlflow` | 控制流分析 |
| `risk` | 风险评分 |
| `sva` | SVA 提取 |
| `timing` | 时序分析 |
| `cdc` | 跨时钟域检测 |
| `verify` | 验证缺口 |
| `visualize` | 图可视化 |
| `stats` | 图统计 |

### `visualize graph` 选项

```bash
python run_cli.py visualize graph \
    -f <file.sv> \                    # 必需：源文件
    --dot output.dot \                 # DOT 输出
    --mmd output.mmd \                 # Mermaid 输出
    --html output.html \               # HTML 输出
    --layout TB \                      # TB (top-bottom) / LR (left-right)
    --no-edges \                       # 隐藏边
    --show-labels \                    # 显示边标签
    --show-conditions \                # 显示驱动条件
    --max-edges 200 \                  # 最大边数
    --exclude-clock \                  # 排除时钟
    --exclude-reset \                  # 排除复位
    --cluster-modules \                # 模块聚类
    --layout-engine dot \              # dot / neato / fdp
    -I include1,include2 \             # include 路径 (逗号分隔)
    --filelist project.fl              # filelist 路径
```

### `visualize gap` 选项

```bash
python run_cli.py visualize gap \
    -f <file.sv> \
    --dot gap.dot \
    --html gap.html \
    --min-risk 20.0
```

---

## Python API

### 基础用法

```python
from trace.unified_tracer import UnifiedTracer

# 单文件
with open('module.sv') as f:
    source = f.read()
tracer = UnifiedTracer(sources={'module.sv': source})
graph = tracer.build_graph()
```

### 多文件

```python
sources = {}
for f in ['module_a.sv', 'module_b.sv', 'package.sv']:
    with open(f) as fp:
        sources[f] = fp.read()
tracer = UnifiedTracer(sources=sources)
graph = tracer.build_graph()
```

### 使用 Filelist

```python
tracer = UnifiedTracer(
    sources={},                          # 留空
    filelist='project.fl',               # filelist 路径
    include_dirs=['extra/include']       # 额外 include 路径
)
graph = tracer.build_graph()
```

### 读取所有源码 (for SVA/Covergroup)

```python
tracer = UnifiedTracer(filelist='project.fl')
graph = tracer.build_graph()

# 复用 tracer 已加载的 sources 给 SVA/Covergroup
compiler = tracer._get_compiler()
sources = compiler._sources

from trace.core.sva_extractor import SVAExtractor
sva = SVAExtractor(sources).extract()
```

### 完整示例：追踪信号

```python
from trace.unified_tracer import UnifiedTracer

tracer = UnifiedTracer(
    sources={'top.sv': open('top.sv').read()}
)
graph = tracer.build_graph()

# 查找信号的所有驱动
from trace.core.query import SignalTracer
sig_tracer = SignalTracer(graph)
drivers = sig_tracer.trace_drivers('top.clk')
for d in drivers:
    print(f"Driver: {d.source} -> {d.target}")
```

---

## 多文件项目 (Filelist)

对于大型 SV 项目（CVA6, OpenTitan, SiFive 核心等），使用 filelist 格式。

### 快速示例

```bash
# 设置环境变量
export CVA6_REPO_DIR=/path/to/cva6
export TARGET_CFG=cv64a6_imafdc_sv39

# 使用 filelist
python run_cli.py visualize graph \
    -f $CVA6_REPO_DIR/core/cva6.sv \
    --filelist $CVA6_REPO_DIR/core/Flist.cva6
```

### Filelist 语法

```filelist
// 注释
# 注释

// Include 路径
+incdir+core/include
+incdir+vendor/lib/include

// 文件路径
${CVA6_REPO_DIR}/core/cva6.sv
$HOME/module.sv

// 嵌套加载
-F vendor/Flist.lib

// 宏定义
+define+DEBUG=1
```

### 支持的环境变量

| 变量 | 用途 |
|------|------|
| `CVA6_REPO_DIR` | CVA6 仓库根目录 |
| `HPDCACHE_DIR` | HPDCACHE 路径 |
| `TARGET_CFG` | 配置包名 (e.g. `cv64a6_imafdc_sv39`) |
| `VCS_HOME` | VCS 工具路径 |
| `UVM_HOME` | UVM 库路径 |

**详细文档**: 参考 `docs/FILELIST.md`

---

## 可视化

### 生成图

```bash
# DOT 文件
python run_cli.py visualize graph -f module.sv --dot out.dot

# PNG（正方形）
python run_cli.py visualize graph -f module.sv --dot out.dot && \
    dot -Tpng -Gsize=10 -Gratio=compress out.dot -o out.png
```

### 图片比例

默认生成正方形图片 (10 英寸)，不裁剪超出内容：
- `size=10` - 最大尺寸
- `ratio=compress` - 压缩布局适应正方

### 验证缺口

```bash
python run_cli.py visualize gap -f module.sv --dot gap.dot --min-risk 25
```

高亮无 SVA/Coverage 的高风险信号。

### 布局选项

```bash
# Top-Bottom (默认)
python run_cli.py visualize graph -f m.sv --layout TB

# Left-Right
python run_cli.py visualize graph -f m.sv --layout LR

# neato 力导向
python run_cli.py visualize graph -f m.sv --layout-engine neato
```

---

## 解析范围说明

### ⚠️ 重要: 需要传入所有相关文件

sv_query 不会自动发现同目录的相关文件。

| 场景 | 缺少文件时 | 传入所有文件后 |
|------|-----------|---------------|
| 单文件 | 边数: 0-3 | 边数: 100+ |
| 多文件项目 | 边数: 0 | 边数: 数千+ |

**正确做法**: 使用 filelist 或 glob 模式。

```python
from glob import glob
files = glob('project/**/*.sv', recursive=True)
sources = {f: open(f).read() for f in files}
tracer = UnifiedTracer(sources=sources)
```

---

## 常见问题

### Q: 为什么边数为 0？

**A**: 最常见原因是**缺少子模块文件**。

解决：
1. 使用 `--filelist` 加载完整项目
2. 使用 `-I` 添加 include 路径
3. 检查警告信息中提到的"可能缺少文件"提示

### Q: parameter type 解析失败？

**A**: CVA6 等工业级代码大量使用 `parameter type`，独立看子模块无法解析。

解决：
1. 从顶层文件入口（`cva6.sv`）
2. 包含所有依赖的包和模块

### Q: UVM 解析失败？

**A**: sv_query 自动检测 UVM 引用并加载默认 UVM 路径。如果失败：

```python
import os
os.environ['UVM_HOME'] = '/path/to/uvm-1.2'
```

### Q: pyslang 触发 UnicodeDecodeError？

**A**: 这是 CVA6 等复杂类型系统触发的 pyslang bug。sv_query 已添加防护（占位符 `_inst_`、`_bad_`）。这是已知限制。

### Q: 如何生成完整图（含所有边）？

**A**: 调整 `--max-edges`：

```bash
python run_cli.py visualize graph -f m.sv --dot out.dot --max-edges 5000
```

### Q: 输出 PNG 比例不对？

**A**: 已默认使用正方形 (`size=10`, `ratio=compress`)。如需调整：

```bash
dot -Tpng -Gsize="20,10" -Gratio=compress in.dot -o out.png
```

---

## 限制与已知问题

| 问题 | 状态 | 说明 |
|------|------|------|
| 复杂 `parameter type` | 限制 | 需从顶层入口 |
| 宏定义 typedef | 限制 | pyslang 不能完全展开 |
| CVA6 完整解析 | 部分 | cvxif 等子模块有 Unicode bug |
| 错误容错 | 限制 | 任意错误导致整个图失败 |
| 大型项目 (>200 模块) | 性能 | 建议分模块分析 |

---

## 相关文档

- `docs/README.md` - 项目总览
- `docs/ARCHITECTURE.md` - 架构说明
- `docs/FILELIST.md` - Filelist 详细格式
- `docs/DOC_IMPL_GAP.md` - 文档与实现差异
- `docs/DISCIPLINE_VIOLATIONS.md` - 已知限制

---

## 联系方式

- GitHub: https://github.com/fundou1081/sv_query
- Issues: https://github.com/fundou1081/sv_query/issues

**最后更新**: 2026-06-01
