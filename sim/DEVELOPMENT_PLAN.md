# sv_query 开发计划
# ======================

## 当前状态

- **测试数**: 485 tests
- **核心功能**: 全部验证通过 ✓
- **最后更新**: 2026-05-10

---

## 已完成功能

### 1. 核心解析模块 ✅
- [x] PyslangAdapter - pyslang AST 适配器
- [x] 模块/端口/信号解析
- [x] 生成块 (generate block) 支持

### 2. 信号追踪 ✅
- [x] DriverExtractor - 驱动追溯
- [x] LoadExtractor - 负载追溯
- [x] SignalTracer - 统一信号追踪
- [x] 实例端口穿透追踪

### 3. 实例连接 ✅
- [x] ConnectionExtractor - 实例端口连接
- [x] 命名端口连接
- [x] 位置端口连接
- [x] generate 块内实例支持

### 4. 图构建 ✅
- [x] GraphBuilder - 统一图构建器
- [x] SignalGraph - 信号图模型
- [x] TraceNode/TraceEdge - 节点边模型
- [x] 跨实例边创建

### 5. 查询接口 ✅
- [x] UnifiedTracer - 统一查询入口
- [x] trace_signal() - 信号追踪
- [x] trace_fanout() - 扇出追踪
- [x] get_module_hierarchy() - 模块层级

### 6. 测试覆盖 ✅
- [x] 单元测试 (30 tests)
- [x] 集成测试 (47 tests)
- [x] 回归测试 (408 tests)

---

## 架构概览

```
src/trace/
├── core/
│   ├── base.py           # PyslangAdapter
│   ├── graph_models.py  # TraceNode, TraceEdge, EdgeKind, NodeKind
│   ├── graph_builder.py  # GraphBuilder, Extractors
│   └── query_signal.py   # SignalTracer
├── unified_tracer.py      # UnifiedTracer
└── __init__.py
```

---

## 测试统计

| 类型 | 数量 | 状态 |
|------|------|------|
| Unit Tests | 30 | ✅ |
| Integration Tests | 47 | ✅ |
| Regression Tests | 408 | ✅ |
| **总计** | **485** | ✅ |

---

## 下一步计划

暂无待处理事项。项目功能已稳定，测试覆盖完整。

---

## 版本历史

| 日期 | 版本 | 变化 |
|------|------|------|
| 2026-05-10 | v1.0 | 485 tests, generate block support |
| 2026-05-09 | v0.9 | 160 tests, 基础功能完成 |
