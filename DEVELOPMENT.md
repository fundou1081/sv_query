# sv_query 开发规范 (纪律要求增强版)

---

## 状态标注

| 状态 | 说明 | 触发校验 |
|------|------|---------|
| [草案] | AI生成，未经确认 | 人工审查 |
| [审查中] | 经评审，待人工 | 人工审查 |
| [生效] | 已确认执行 | CI强制校验 |
| [废弃] | 已过时，不再使用 | 无 |

---

## 一、四层架构 (铁律)

```
┌─────────────────────────────────────────────────────────────┐
│ Query Layer: unified_tracer.py                            │
├─────────────────────────────────────────────────────────────┤
│ Graph Layer: graph_models.py (networkx)                   │
├─────────────────────────────────────────────────────────────┤
│ Builder Layer: graph_builder.py                            │
├─────────────────────────────────────────────────────────────┤
│ Extractor Layer: base.py + pyslang_adapter.py               │
└─────────────────────────────────────────────────────────────┘
```

### [生效] 约束

- 禁止在 Query 层直接操作 Graph
- 禁止在 Tracer 中修改 Graph
- 禁止硬编码 Parser (必须用适配器)
- 禁止创建新 Graph 类
- 禁止修改 networkx 内部

### 适用范围：src/trace/ 下所有 .py 文件

### 校验方式 [生效]
```bash
# 检测禁止模式
grep -rn "_graph.add_node\|_graph.add_edge" src/trace/
grep -rn "parser.trees\[" src/trace/
```

---

## 二、数据纪律 (新增)

### [生效] 约束 1：数据沿袭

**必须**：所有硬件语义提取必须通过 pyslang AST 遍历实现

**禁止**：用正则表达式解析 SystemVerilog 源代码文本

**原理**：正则无法正确处理拼接赋值、宏展开、位选择、注释中的代码等，导致输出不可信

**违规后果**：
- 时序路径分析可能跳过拼接赋值
- 位选择信号被混淆为同一信号

**适用范围**：src/trace/ 下所有 .py 文件

**校验方式** [生效]
```bash
grep -rn "re\.findall\|re\.match\|re\.search" src/trace/core/
# 允许：日志格式化、CLI参数解析
# 禁止：SV源码分析
```

### [生效] 约束 2：数据模型即契约

**必须**：
- 新增字段必须同步实现
- 未实现的字段必须删除或标注 `TODO: 未实现`
- 禁止保留"僵尸字段"（未使用的字段）

**原理**：数据模型是项目的核心契约，僵尸字段导致下游使用时误判为空值

**违规后果**：下游代码读取空字段导致运行时错误

**适用范围**：graph_models.py 中的 TraceNode, TraceEdge

**校验方式** [审查中]
- 运行 `json.dumps()` 时检测空字段
- 静态分析 dataclass 字段使用率

### [生效] 约束 3：位精确性

**必须**：保留位选择信息，禁止截断为裸信号名

**原理**：位选择信号 (data[7:0] vs data[15:8]) 是不同的硬件信号

**违规后果**：跨时钟域分析、时序路径分析出错

**适用范围**：所有返回信号关系的 API

**校验方式** [草案]
- 检查 graph_models.py 的 width 字段是否���正确传递

---

## 三、模块纪律

### 文件规则 [生效]

| 功能 | 文件 |
|------|------|
| 统一入口 | unified_tracer.py |
| 图模型 | graph_models.py |
| 构建器 | graph_builder.py |
| AST遍历 | base.py |
| pyslang适配 | pyslang_adapter.py |
| 信号查询 | query_signal.py |
| 模块查询 | query_module.py |
| 时钟域查询 | query_clock_domain.py |

**约束**：
- 禁止创建新目录 (src/trace/ 下深度<=3)
- 禁止改名：文件名必须小写+下划线

### 类规则 [生效]

| 类 | 文件 |
|---|------|
| UnifiedTracer | unified_tracer.py |
| SignalGraph | graph_models.py |
| GraphBuilder | graph_builder.py |
| ASTWalker | base.py |
| PyslangAdapter | pyslang_adapter.py |
| SignalTracer | query_signal.py |
| ModuleTracer | query_module.py |
| ClockDomainTracer | query_clock_domain.py |

---

## 四、接口纪律

### [生效] 约束

- 统一入口必须是 `UnifiedTracer`
- 方法命名必须具体：
  - `trace_signal(signal, module=None)`
  - `trace_module(module)`
  - `trace_clock_domain(clock)`

**禁止**：
- `query(signal)` - 不具体
- `get(signal)` - 不具体
- `find(signal)` - 不具体

---

## 五、依赖规则

### [生效]

**必须**：networkx>=3.0

**禁止**：igraph, graphviz, pygraphviz

### 新增依赖 [草案]

```
1. 在 requirements.txt 添加
2. 在 CHANGELOG.md 记录原因
3. 说明为何必需
```

---

## 六、测试纪律

### [生效] 约束：金标准不可退化

**必须**：
- 推导金标准 → 运行代码 → 对比结果
- 任何差异必须修复，否则提交不得通过

**原理**：防止代码修改后输出悄悄改变

**校验方式 [草案]**
```python
# 测试模板
gold = {"signal": ["driver1", "driver2"]}
actual = adapter.drivers
assert set(gold.values()) == set(actual.values())
```

### 测试文件位置

```
sim/
└── test_*.sv (金标准RTL)
tests/
└── test_*.py (金标准测试)
```

---

## 七、变更纪律

### 变更等级

| 等级 | 范围 | 需要 |
|------|------|------|
| 不能改 | 架构、核心数据结构 | 人工评审 |
| 需测试 | 性能优化、新功能 | 测试通过 |
| 自由改 | 文档、日志 | 无 |

---

## 八、Git 规则

### [生效] 提交信息格式

```
<type>: <描述>

Types:
- feat: 新功能
- fix: Bug修复
- refactor: 重构
- docs: 文档
- test: 测试
```

### 分支命名 [生效]

```
feature/xxx
fix/bug-xxx
refactor/xxx
```

---

## 九、代码审查检查清单

提交前必须检查：

- [ ] 代码在正确文件？
- [ ] 没有直接操作 Graph？
- [ ] 没有硬编码 Parser？
- [ ] 没有使用正则分析源码？
- [ ] 数据模型没有僵尸字段？
- [ ] 文件命名正确？
- [ ] 类名符合规范？
- [ ] 方法命名具体？
- [ ] 没有新增禁止的依赖？
- [ ] 金标准验证通过？

---

## 十、校验脚本

### CI 自动校验

创建 `.github/workflows/check_discipline.py`：

```python
#!/usr/bin/env python3
"""纪律校验脚本 - CI使用"""

import subprocess
import sys
import os

def check_regex():
    """检测正则使用"""
    result = subprocess.run(
        ["grep", "-rn", "re\\.(findall|match|search)", 
         "src/trace/core/", "--include=*.py"],
        capture_output=True, text=True
    )
    # 排除日志/CLI
    violations = []
    for line in result.stdout.strip().split('\n'):
        if line and not any(x in line for x in ['log', 'cli', '__pycache__']):
            violations.append(line)
    return violations

def check_file_structure():
    """检测文件结构"""
    errors = []
    # 检查禁止文件
    forbidden = ['query.py', 'tracer.py', 'builder.py']
    for f in forbidden:
        if os.path.exists(f"src/trace/{f}"):
            errors.append(f"禁止文件名: {f}")
    return errors

if __name__ == "__main__":
    errors = []
    errors.extend(check_regex())
    errors.extend(check_file_structure())
    
    if errors:
        print("❌ 纪律违规:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("✅ 纪律校验通过")
        sys.exit(0)
```

---

*更新时间: 2026-05-04*
*下次审查: 2026-07-01*
