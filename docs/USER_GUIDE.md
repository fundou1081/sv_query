# sv_query 用户指南

**版本**: 1.0
**更新日期**: 2026-05-17

---

## 目录

1. [安装](#安装)
2. [快速开始](#快速开始)
3. [使用方法](#使用方法)
4. [解析范围说明](#解析范围说明)
5. [常见问题](#常见问题)

---

## 安装

```bash
pip install sv_query
# 或
git clone https://github.com/yourrepo/sv_query.git
cd sv_query
pip install -e .
```

---

## 快速开始

### Python API

```python
from sv_query import UnifiedTracer
import pyslang

# 解析文件
tree = pyslang.SyntaxTree.fromFile('your_module.v')
tracer = UnifiedTracer(trees={'your_module.v': tree})
tracer.build_graph()

# 获取信息
adapter = tracer._get_adapter()
modules = list(adapter.get_modules())

for module in modules:
    name = adapter.get_module_name(module)
    params = adapter.get_module_parameters(module)
    ports = adapter.get_port_declarations(module)
    print(f"Module: {name}, Params: {len(params)}, Ports: {len(ports)}")
```

### CLI

```bash
sv_query your_module.v --module-name
sv_query your_module.v --ports
sv_query your_module.v --instances
```

---

## 使用方法

### 解析单个文件

```python
from sv_query import UnifiedTracer
import pyslang

path = 'your_module.v'
tree = pyslang.SyntaxTree.fromFile(path)
tracer = UnifiedTracer(trees={'your_module.v': tree}, log_level='INFO')
tracer.build_graph()
graph = tracer.get_graph()

print(f"节点数: {len(graph.nodes())}")
print(f"边数: {len(graph.edges())}")
```

### 解析多个文件

```python
from sv_query import UnifiedTracer
import pyslang

trees = {
    'module_a.v': pyslang.SyntaxTree.fromFile('module_a.v'),
    'module_b.v': pyslang.SyntaxTree.fromFile('module_b.v'),
}
tracer = UnifiedTracer(trees=trees)
tracer.build_graph()
```

### 使用 glob 模式

```bash
sv_query 'path/to/**/*.v'  # 递归解析所有 .v 文件
sv_query 'file1.v file2.v file3.v'  # 解析多个指定文件
```

---

## 解析范围说明

### ⚠️ 重要: 需要传入所有相关文件

sv_query **不会自动发现**同目录或子目录的相关文件。为了获取完整的分析结果，**请务必传入所有相关的 Verilog 文件**。

#### 为什么需要这样做？

当解析一个模块时，sv_query 需要知道该模块中实例化的子模块的端口定义，才能：
1. 确定实例端口的方向 (input/output)
2. 建立模块之间的连接边
3. 追踪信号驱动关系

如果缺少子模块文件，sv_query 将无法建立这些连接，**边数会很少或为0**。

#### 缺少文件时的警告

当 sv_query 检测到实例但无法获取其模块的端口定义时，会输出警告：

```
[sv_query] 可能缺少文件: 实例 'I0' 的模块 'sub_module' 没有找到端口定义。
  → 可能原因: 解析的文件范围不完整，缺少 'sub_module' 的定义文件
  → 建议: 确保传入所有相关的 Verilog 文件
```

#### 正确的做法

**错误示例** (只传入顶层文件):
```python
# 只解析顶层模块
tree = pyslang.SyntaxTree.fromFile('top.v')
tracer = UnifiedTracer(trees={'top.v': tree})  # ❌ 缺少子模块
```

**正确示例** (传入所有相关文件):
```python
from glob import glob
import pyslang

# 解析整个目录的所有 .v 文件
files = glob('path/to/**/*.v', recursive=True)
trees = {f: pyslang.SyntaxTree.fromFile(f) for f in files}
tracer = UnifiedTracer(trees=trees)  # ✅ 包含所有文件
```

#### 实际案例

| 场景 | 缺少文件时 | 传入所有文件后 |
|------|-----------|---------------|
| bs_mult | 边数: 3 | 边数: 708 |
| cva6 | 边数: 0 | 边数: 2000+ |
| NV_nvdla | 边数: 0 | 边数: 5000+ |

---

## 常见问题

### Q: 为什么边数为0或很少？

**A**: 最常见的原因是**缺少子模块文件**。请确认已传入所有相关的 Verilog 文件。

检查方法：
1. 查看警告信息中提到的缺少的模块名
2. 确认这些模块的文件是否在解析范围内

### Q: 实例连接数为0是怎么回事？

**A**: 这通常意味着子模块未解析，导致无法获取端口定义。

解决方法是确保传入子模块的 Verilog 文件。

### Q: 如何检查缺少哪些文件？

**A**: 查看 sv_query 的警告信息。当检测到实例但无法获取端口定义时，会输出警告提示缺少的模块名。

### Q: 可以自动发现同目录的文件吗？

**A**: 目前不支持自动目录扫描。这是已知限制，计划在将来版本中改进。

---

## 限制与已知问题

| 问题 | 状态 | 说明 |
|------|------|------|
| 目录自动扫描 | 限制 | 将来版本计划支持 |
| `define 宏解析 | 限制 | 无法解析 `define 宏 |
| 复杂参数对象 | 限制 | 部分复杂参数可能无法展开 |

---

## 联系方式

如有问题，请提交 Issue 或联系维护者。