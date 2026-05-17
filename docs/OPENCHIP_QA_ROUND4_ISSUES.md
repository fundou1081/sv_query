# OpenChip QA Round 4 - sv_query 问题分析与解决方案

**测试时间**: 2026-05-17
**测试项目**: clacc/bs_mult

---

## 问题汇总

| Issue | 问题 | 根因 | 优先级 |
|-------|------|------|--------|
| Issue 17 | 非ANSI端口位宽未提取 | 非ANSI端口位宽在 separate declaration 中 | P1 |
| Issue 18 | LOAD 边统计为 0 | 实例端口连接未建立 DRIVER/LOAD 边 | P1 |
| Issue 19 | 实例节点前缀 "top" | 硬编码 "top" 作为根模块前缀 | P1 |
| Issue 20 | 连接边只有 3 条 | assign 语句被正确解析，但实例端口连接未追踪 | P1 |

---

## 根因分析

### Issue 17/20: 非ANSI端口位宽丢失

**现象**:
```
p: output    # 应该是 output [29:0]
```

**根因**:
bs_mult 使用非ANSI端口声明：
```verilog
module bs_mult(clk, x, y, p, firstbit, lastbit);
    input clk;
    input x, y, firstbit, lastbit;
    output p;          // 位宽在 separate declaration 中定义
```

位宽 `[29:0]` 定义在 separate NetDeclaration 中，不在 PortDeclaration 中。

**pyslang AST 结构**:
- PortDeclaration (port p) 只有方向，没有位宽
- NetDeclaration (`wire [29:0] pout`) 有位宽，但不关联到 port

---

### Issue 18/19: 实例节点前缀错误 "top"

**现象**:
```
top.I0.clk     # 应该是 bs_mult.I0.clk
top.I0.pout    # 应该是 bs_mult.I0.pout
```

**根因**:
在 `graph_builder.py` 的 `extract()` 方法中，实例路径使用硬编码 "top" 作为根模块前缀：

```python
# graph_builder.py:1268-1282
def get_path(info, depth=0):
    if depth > 20:
        return f"top.{info['inst_name']}"  # 硬编码 "top"
    parent_mod = info['parent_module']
    if parent_mod == 'top':
        return f"top.{info['inst_name']}"  # 硬编码 "top"
```

当 `parent_module` 不是 'top' 时（如 'bs_mult'），也会 fallback 到 "top"。

---

## 解决方案

### 方案 A: 修复 Issue 17 (非ANSI端口位宽)

**思路**: 在解析端口时，同时查找 members 中的 NetDeclaration 来关联位宽

**修改位置**: `src/trace/core/base.py` → `get_port_name_and_direction()` 或 `extract_port_width()`

**实现**:
```python
def extract_port_width(self, port, scope=None) -> dict | tuple:
    # ... 现有逻辑 ...
    
    # [FIX] 如果是非ANSI端口，尝试从 members 中的 NetDeclaration 获取位宽
    if not width_found and scope:
        port_name = self.get_port_name(port)
        for member in scope.members:
            if member.kind == SyntaxKind.NetDeclaration:
                # 检查 decl 的 name 是否匹配
                decls = getattr(member, 'declarators', None)
                if decls:
                    for decl in decls:
                        decl_name = getattr(decl.name, 'value', None)
                        if decl_name == port_name:
                            # 从 this NetDeclaration 获取位宽
                            dt = getattr(member.header, 'dataType', None)
                            if dt and hasattr(dt, 'dimensions'):
                                # 解析 dimensions
                                pass
```

---

### 方案 B: 修复 Issue 18/19 (实例节点前缀)

**思路**: 动态获取根模块名，而非硬编码 "top"

**修改位置**: `src/trace/core/graph_builder.py` → `extract()` 方法中的路径构建逻辑

**实现**:
```python
# 获取根模块名 (第一个模块)
root_module = None
for mod in self.adapter.get_modules():
    mod_name = self.adapter.get_module_name(mod)
    if root_module is None:
        root_module = mod_name
    if mod_name == module_name:
        # 找到了当前模块，使用它的名字作为前缀
        break

# 替换硬编码 "top"
def get_path(info, depth=0):
    if depth > 20:
        return f"{root_module}.{info['inst_name']}"
    # ... 类似逻辑，但使用 root_module 替代 "top"
```

**替代方案 B2**: 在调用 `extract()` 前传入根模块名参数

```python
class GraphBuilder:
    def __init__(self, adapter, root_module_name='top'):
        self.adapter = adapter
        self.root_module_name = root_module_name  # 可配置
```

---

## 修复优先级建议

| 优先级 | Issue | 修复方案 | 工作量 |
|--------|-------|----------|--------|
| P1 | Issue 19 (top 前缀) | 方案 B | 小 |
| P1 | Issue 18 (LOAD 边) | 需要先修复 Issue 19 | 中 |
| P2 | Issue 17 (位宽) | 方案 A | 中 |
| P2 | Issue 20 (p 位宽) | 同 Issue 17 | 中 |

---

## 讨论点

1. **Issue 19 优先**: 因为实例节点命名是基础设施，其他功能依赖它
2. **方案选择**: 方案 B2 (传入根模块名) 比方案 B 更灵活
3. **向后兼容**: 修改实例节点前缀可能影响现有用户，需要评估

---

## 测试验证

修复后应能正确识别:

```
【端口】
  clk: input
  x: input
  y: input
  firstbit: input
  lastbit: input
  p: output [29:0]      # 位宽正确

【节点命名】
  bs_mult.clk
  bs_mult.xy
  bs_mult.I0.clk         # 前缀正确
  bs_mult.I0.pout

【连接边】
  bs_mult.I0.pout -> bs_mult.p (DRIVER)  # 实例端口连接
```

---

## 待确认

1. 根模块名应该动态获取还是可配置？
2. 实例节点命名格式是否需要保持兼容？
3. 是否需要同时修复 Issue 17/18，还是分步进行？