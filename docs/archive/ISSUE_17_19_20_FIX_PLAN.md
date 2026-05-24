# Issue 17/19/20 修复方案

**创建时间**: 2026-05-17
**状态**: 进行中
**修复目标**: Issue 17 (非ANSI位宽) / Issue 19 (top前缀) / Issue 20 (连接边)

---

## Issue 19: 实例节点前缀错误 "top"

### 问题描述

```
实际: top.I0.clk, top.I0.pout, ...
期望: bs_mult.I0.clk, bs_mult.I0.pout, ...
```

### 根因

`graph_builder.py:1268-1282` 硬编码 "top" 作为根模块前缀

### 修复方案

**修改文件**: `src/trace/core/graph_builder.py`

**修改位置**: `extract()` 方法中的路径构建逻辑

**修改内容**:
1. 动态获取根模块名 (第一个解析的模块名)
2. 将硬编码 "top" 替换为动态获取的根模块名

```python
# 添加实例变量
self.root_module_name = None

# 在 extract() 开始时获取根模块名
if self.root_module_name is None:
    for mod in self.adapter.get_modules():
        self.root_module_name = self.adapter.get_module_name(mod)
        break

# 将所有 "top." 替换为 f"{self.root_module_name}."
```

---

## Issue 17/20: 非ANSI端口位宽丢失

### 问题描述

```
实际: p: output
期望: p: output [29:0]
```

### 根因

非ANSI端口的位宽定义在 separate NetDeclaration 中：
```verilog
module bs_mult(clk, x, y, p, ...);  // 端口列表无位宽
    output p;                        // separate declaration 无位宽信息
```

### 修复方案

**修改文件**: `src/trace/core/base.py` → `extract_port_width()`

**修改内容**:
1. 当从 port 本身无法获取位宽时
2. 在 scope.members 中查找匹配的 NetDeclaration
3. 从 NetDeclaration.header.dataType.dimensions 提取位宽

---

## 修复顺序

1. **Issue 19** (top前缀) - 基础设施修复
2. **Issue 17/20** (位宽) - 功能修复

---

## 测试用例

```bash
cd ~/my_dv_proj/sv_query
PYTHONPATH=src python3 << 'PYEOF'
from trace.unified_tracer import UnifiedTracer
import pyslang, logging, sys
logging.disable(logging.CRITICAL)
sys.path.insert(0, 'src')

path = '/Users/fundou/my_dv_proj/clacc/bs_mult.v'
tree = pyslang.SyntaxTree.fromFile(path)
tracer = UnifiedTracer(trees={'bs_mult.v': tree}, log_level='ERROR')
tracer.build_graph()
graph = tracer.get_graph()
adapter = tracer._get_adapter()

modules = list(adapter.get_modules())
bs_mult = modules[0]

# Issue 19 测试: 节点前缀应为 bs_mult 而非 top
print("=== Issue 19 测试: 节点前缀 ===")
for node_id in list(graph.nodes())[:5]:
    print(f"  {node_id}")
top_count = sum(1 for n in graph.nodes() if n.startswith('top.'))
bs_mult_count = sum(1 for n in graph.nodes() if n.startswith('bs_mult.'))
print(f"top.* 前缀: {top_count}")
print(f"bs_mult.* 前缀: {bs_mult_count}")
print(f"期望: bs_mult_count > 0, top_count = 0")

# Issue 17 测试: p 的位宽应为 [29:0]
print("\n=== Issue 17 测试: p 位宽 ===")
ports = adapter.get_port_declarations(bs_mult)
for port in ports:
    pname, pdir = adapter.get_port_name_and_direction(port)
    if pname == 'p':
        width = adapter.extract_port_width(port, scope=bs_mult)
        msb = width.get('msb_eval', width.get('msb_raw')) if isinstance(width, dict) else width[0] if width else None
        print(f"p: {pdir} [msb={msb}]")
        print(f"期望: msb=29")

# Issue 20 测试: 边数量应该 > 3
print("\n=== Issue 20 测试: 边数量 ===")
edge_count = len(graph.edges())
print(f"总边数: {edge_count}")
print(f"期望: > 3 (应该有实例端口连接边)")
PYEOF
```

---

## Rollback 方案

```bash
git checkout fix_round4_pre
```

---

## 进度记录

| 时间 | 操作 | 结果 |
|------|------|------|
| 2026-05-17 10:00 | 创建 tag fix_round4_pre | ✅ |
| 2026-05-17 10:00 | 开始修复 Issue 19 | ⏳ 进行中 |