# sv_query 架构设计

## 统一架构 (四层)

```
┌─────────────────────────────────────────────────────────────┐
│           Query Layer (查询层)                         │
├─────────────────────────────────────────────────────────────┤
│   UnifiedTracer                                       │
│   - trace_signal(sig)    → 场景A: driver→load        │
│   - trace_module(mod)    → 场景B: 端口连接            │
│   - trace_clock_domain(clk) → 场景C: 时钟域寄存器链   │
├─────────────────────────────────────────────────────────────┤
│           Graph Layer (图表层)                        │
├─────────────────────────────────────────────────────────────┤
│   SignalGraph (基于 networkx DiGraph)                  │
├─────────────────────────────────────────────────────────────┤
│           Builder Layer (构建层)                      │
├─────────────────────────────────────────────────────────────┤
│   GraphBuilder + Extractors                            │
│   - DriverExtractor, LoadExtractor                     │
│   - ConnectionExtractor, ClockDomainExtractor         │
├─────────────────────────────────────────────────────────────┤
│           Extractor Layer (提取层)                      │
├─────────────────────────────────────────────────────────────┤
│   Parser (pyslang) + AST 遍历                         │
└─────────────────────────────────────────────────────────────┘
```

## 文件结构

```
sv_query/
└── src/
    └── trace/
        ├── __init__.py
        ├── unified_tracer.py     # Query Layer
        └── core/
            ├── __init__.py
            ├── graph_models.py      # Graph Layer
            ├── graph_builder.py # Builder Layer
            ├── query_signal.py  # 场景A
            ├── query_module.py  # 场景B
            └── query_clock_domain.py  # 场景C
```

## API

```python
from trace import UnifiedTracer

tracer = UnifiedTracer(parser)
graph = tracer.build_graph()

# 场景A
chain = tracer.trace_signal("data")

# 场景B
conn = tracer.trace_module("top")

# 场景C
domain = tracer.trace_clock_domain("clk")
```

---

*更新时间: 2026-05-04*
