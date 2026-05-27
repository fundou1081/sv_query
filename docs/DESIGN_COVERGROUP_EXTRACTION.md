# Covergroup 结构化提取架构设计

> 创建时间: 2026-05-28
> 状态: 设计中
> 关联: `REQUIREMENT_COVERGROUP_ANALYSIS.md`

---

## 一、目标

从 SV 源码中完整提取 covergroup 结构化数据，支持后续：
- covergroup ↔ constraint 一致性比对
- RTL coverage 合理性分析

## 二、pyslang API 分析

### CovergroupDeclaration 结构

```
CovergroupDeclaration
  SyntaxList[0]:          attributes/options (option.per_instance = 1)
  EventControlWithExpression: 采样时钟 @(posedge clk)
  SyntaxList[N]:          成员列表 (N=5 for module, N=4 for class)
    Coverpoint
      SyntaxList[0]:      attributes
      ImplicitType:       类型声明
      IdentifierName[3]:  信号名 (.identifier.value)
      SyntaxList[5]:      bins 列表
        CoverageBins
          .name:           bin 名称
          .keyword:        "bins" / "illegal_bins" / "ignore_bins"
          SyntaxList[0]:   attributes
          RangeCoverageBinInitializer: 值范围 {[0:63]}
    CoverCross
      SyntaxList:         attributes
      SeparatedList:      cross 的 coverpoint 列表
      SyntaxList:         cross body (iff/bins)
```

### 关键 API

| 元素 | pyslang 访问方式 |
|------|-----------------|
| covergroup 名称 | `getattr(node, 'name', '')` |
| 采样时钟 | `EventControlWithExpression` 子节点 |
| coverpoint 信号名 | `IdentifierName.identifier.value` |
| bin 名称 | `CoverageBins.name` |
| bin 类型 | `CoverageBins.keyword` (bins/illegal_bins/ignore_bins) |
| bin 值范围 | `RangeCoverageBinInitializer` 或 `ExpressionCoverageBinInitializer` |
| cross 列表 | `CoverCross` 的 `SeparatedList` |

---

## 三、架构设计

### 现有架构

```
┌─────────────────────────────────────────┐
│ Query Layer: unified_tracer.py          │
├─────────────────────────────────────────┤
│ Graph Layer: graph/models.py            │
├─────────────────────────────────────────┤
│ Builder Layer: graph_builder.py         │
│             class_graph_builder.py      │
├─────────────────────────────────────────┤
│ Extractor Layer: base.py + visitors/    │
└─────────────────────────────────────────┘
```

### 新增组件

```
┌─────────────────────────────────────────────────────────┐
│ Query Layer                                             │
│   unified_tracer.py → get_covergroups()                 │
├─────────────────────────────────────────────────────────┤
│ Data Model (新增)                                       │
│   graph/covergroup_models.py                            │
│   - CovergroupInfo, CoverpointInfo, BinsInfo            │
│   - CoverCrossInfo                                       │
├─────────────────────────────────────────────────────────┤
│ Extractor (新增)                                        │
│   covergroup_extractor.py                               │
│   - CovergroupExtractor: 语法树遍历 + 结构化提取         │
│   - 独立于 GraphBuilder，不修改 SignalGraph              │
├─────────────────────────────────────────────────────────┤
│ Parser Layer (已有)                                     │
│   pyslang SyntaxTree → CovergroupDeclaration            │
└─────────────────────────────────────────────────────────┘
```

### 设计原则

1. **独立提取器**：`CovergroupExtractor` 独立于 `GraphBuilder`，不修改 `SignalGraph`
2. **数据模型独立**：使用专用数据类，不复用 `TraceNode`/`TraceEdge`
3. **语法树直读**：直接遍历 pyslang 语法树，不经过 `SemanticAdapter`
4. **模块 + 类均支持**：同时扫描 `module` 和 `class` 中的 covergroup

---

## 四、数据模型

```python
# graph/covergroup_models.py

@dataclass
class BinsInfo:
    """单个 bins 的信息"""
    name: str                    # bin 名称
    kind: str                    # "bins" | "illegal_bins" | "ignore_bins"
    values: str                  # 值描述 (如 "[0:63]", "{1,2,3}")
    source_range: str = ""       # 源码位置

@dataclass
class CoverpointInfo:
    """单个 coverpoint 的信息"""
    name: str                    # coverpoint 名称 (可能为空)
    signal: str                  # 采样信号名
    bins: List[BinsInfo]         # bins 列表
    attributes: Dict[str, str]   # option.xxx 属性

@dataclass
class CoverCrossInfo:
    """cross coverage 的信息"""
    name: str                    # cross 名称
    items: List[str]             # 参与 cross 的 coverpoint 名称
    iff: str = ""                # iff 条件 (如有)

@dataclass
class CovergroupInfo:
    """covergroup 的完整信息"""
    name: str                    # covergroup 名称
    clock: str                   # 采样时钟
    coverpoints: List[CoverpointInfo]
    crosses: List[CoverCrossInfo]
    attributes: Dict[str, str]   # option.xxx 属性
    in_class: str = ""           # 所在 class 名称 (如有)
    source_file: str = ""        # 源文件名
    source_line: int = 0         # 源码行号
```

---

## 五、实现计划

### Phase 1: CovergroupExtractor (核心)

```python
# covergroup_extractor.py

class CovergroupExtractor:
    """Covergroup 结构化提取器
    
    直接遍历 pyslang 语法树，提取 covergroup 信息。
    不修改 SignalGraph，独立输出。
    """
    
    def __init__(self, sources: Dict[str, str]):
        """
        Args:
            sources: {filename: source_code} 字典
        """
        self._sources = sources
    
    def extract(self) -> List[CovergroupInfo]:
        """提取所有 covergroup"""
        results = []
        for fname, source in self._sources.items():
            tree = pyslang.SyntaxTree.fromText(source)
            self._walk(tree.root, fname, results)
        return results
```

### Phase 2: 集成到 UnifiedTracer

```python
# unified_tracer.py 新增方法

def get_covergroups(self) -> List[CovergroupInfo]:
    """获取所有 covergroup 的结构化信息"""
    extractor = CovergroupExtractor(self._sources)
    return extractor.extract()
```

### Phase 3: 查询 API (后续)

```python
# 查询 coverpoint 的 bins 覆盖
def get_coverpoint_bins(self, signal: str) -> List[BinsInfo]:
    """查询信号的 coverpoint bins"""

# 查询 constraint vs covergroup 一致性
def check_constraint_coverage(self, class_name: str) -> CoverageReport:
    """比对 constraint 空间 vs covergroup bins 覆盖"""
```

---

## 六、文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/trace/core/graph/covergroup_models.py` | 新增 | 数据模型 |
| `src/trace/core/covergroup_extractor.py` | 新增 | 提取器 |
| `src/trace/unified_tracer.py` | 修改 | 添加 `get_covergroups()` |
| `sim/tests/regression/test_covergroup_extraction.py` | 新增 | 金标准测试 |

---

## 七、与现有架构的关系

```
CovergroupExtractor  ← 独立提取，不经过 GraphBuilder
       ↓
CovergroupInfo       ← 独立数据模型，不进 SignalGraph
       ↓
UnifiedTracer.get_covergroups()  ← 统一查询入口
       ↓
后续: CoverageAnalyzer  ← 比对 constraint vs covergroup
```

**关键决策**：Covergroup 信息不放入 SignalGraph。原因：
1. Covergroup 是验证结构，不是信号流
2. 放入 SignalGraph 会污染信号追踪的语义
3. 独立数据模型更灵活，支持后续分析
