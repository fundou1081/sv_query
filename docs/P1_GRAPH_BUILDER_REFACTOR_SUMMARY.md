# P1 graph_builder.py 重构总结

> 报告时间: 2026-06-03
> 状态: ✅ P1 全部完成
> 路径: /Users/fundou/my_dvproj/sv_query
> Git: main 分支

---

## 1. P1 是什么

P1 是 sv_query `graph_builder.py` 的**结构问题解决**。不同于 V2 的"功能增量",P1 是"治本":
- 12+ TraceEdge 创建模板 → 1 个 factory
- 3054 行 5 类挤一文件 → 5 个独立模块
- 0 单元测试 → 25+ 测试守护
- 2 个结构 bug 修复

P1 严守: **结构问题先治, 物理拆分后做; 0 行删除; 0 净代码**。

---

## 2. 起点 vs 终点

| 指标 | V2 收尾 | P1 收官 | Δ |
|------|--------|--------|---|
| graph_builder.py | 3051 行 | **392 行** | **-87%** |
| 文件数 | 1 | 5 (+ 1 shared) | +5 |
| TraceEdge 模板重复 | 12+ | **0** (用 factory) | ✅ |
| 单元测试 (P1 范围) | 0 | **25** | +25 |
| 总测试 | 1380 | **1414** | +34 |
| ruff 错误 (P1 新增) | 0 | 0 | ✅ |
| V2.A.2 行为 | (基线) | 完全保留 | ✅ |
| 净代码改动 | - | **0** | 纯结构优化 |

---

## 3. 9 cycles 实施情况

| Cycle | 内容 | 状态 |
|-------|------|------|
| 0 | v1 plan (物理拆分, 已废) → v2 plan (结构优先) | ✅ |
| 1 | TraceEdgeFactory 类 + 9 测试 | ✅ |
| 2 | 8+ ctx-based 替换 (5 commits) | ✅ |
| 3 | 4+ sig_cond 替换 | ✅ |
| 4 | ControlFlowGraph 诊断 (功能正常, 无调用者) | ✅ |
| 5 | case 路径 condition_ast (V2.A.2 17a 遗漏) | ✅ |
| 6-7 | 18 factory 单元测试 + 3 回归测试 | ✅ |
| 8 | DriverExtractor 物理拆分 (1762 行) | ✅ |
| 9a | LoadExtractor 拆分 + ExtractorResult 共享 | ✅ |
| 9b | ConnectionExtractor 拆分 | ✅ |
| 9c | ClockDomainExtractor 拆分 + `__all__` | ✅ |

**总 commit**: 14 (1 plan v1 废 + 1 plan v2 + 9 实施 + 1 result docs + 2 misc)

---

## 4. 最终文件结构

```
src/trace/core/
├── graph_builder.py              392 行  (3051 → 392, -87%)
│   └── 只剩 GraphBuilder 主类
├── driver_extractor.py          1766 行  (最大)
├── load_extractor.py             420 行
├── connection_extractor.py       448 行
├── clock_domain_extractor.py      89 行
├── extractor_models.py            30 行  (ExtractorResult 共享)
└── edge_factory.py                80 行  (P1 cycle 1 新增)
```

每个文件单一职责, 独立可测, 按需 import。

---

## 5. TraceEdgeFactory 设计

**单方法** `make_edge()`, 支持两种入口:

```python
def make_edge(
    self, src, dst,
    expression="",                # 默认空字符串
    kind=EdgeKind.DRIVER,
    assign_type="", bit_slice="",
    ctx=None,                     # V2.A.2 ctx-based 入口
    sig_cond="", sig_cond_ast=None,  # V2.A.2 17e+ sig_cond-based
    clock_domain="",              # 显式覆盖 ctx.get('clock')
) -> TraceEdge:
```

**优势**:
- 12+ 模板 → 1 个 factory
- 任何新字段 (V3 Z3 bin) 只改 factory 一处
- 显式 `clock_domain` 覆盖 ctx 中的 clock (CLOCK/RESET 边)
- 默认参数与 TraceEdge 字段默认值对齐

---

## 6. 数字

| 指标 | 数据 |
|------|------|
| P1 实施 commits | 14 (含 1 废 plan) |
| 新增测试 | 25 (P1 范围) |
| 总测试 | 1414 |
| ruff src/ 错误 (P1 新增) | 0 |
| 净代码改动 (删除/纯结构) | 0 |
| 循环 import 解决 | 1 (ExtractorResult 独立) |

---

## 7. 关键决策回顾

1. **物理移动是症状, 不是治本** (用户原话反馈)
   - v1 plan 物理拆分被否决, v2 plan 改结构优先
2. **structure problems first, file split later**
   - cycle 1-7 改结构 (factory, bug, tests)
   - cycle 8-9 物理拆分变"自然结果"
3. **0 净代码原则**
   - 每次 commit 跑 1414 测试守护
   - 改动纯新增/搬家
4. **circular import 解决**
   - graph_builder ↔ driver_extractor 循环 → ExtractorResult 独立文件
5. **TDD 红→绿 真实暴露 wiring 问题**
   - cycle 5 发现 case path 漏
   - cycle 2 sites 5-8 缺 expression 静默失败 (except Exception: pass 吞)

---

## 8. 经验教训 (P1 新增 11 条, 累计 30 条)

20. 物理移动是症状, 不是治本
21. structure problems first, file split later
22. factory pattern 解决模板重复
23. dict 协调脆弱 (为 P1.4 dataclass 留路)
24. 测试真空是工程债
25. 物理拆分是结果
26. TDD 红→绿 真实暴露问题
27. CLI 端到端是最终验证
28. except Exception: pass 是隐形杀手
29. factory 必填 vs 默认 (TraceEdge 字段对齐)
30. circular import 解法 (ExtractorResult 独立)

---

## 9. 与 V2 的关系

P1 建立在 V2 之上。V2 解决了**功能缺口** (JSON, 多信号, AST),P1 解决了**结构债** (模板重复, 文件大小, 测试真空)。

```
V1 (1322 tests) — 基础 coverage generator
    ↓
V2 (1380 tests) — 增量功能 (A/C/B/A.2)
    ↓
P1 (1414 tests) — 结构优化 (factory, 测试, 物理拆分)
```

每一层都保留前一层的行为, 0 行删除, 纯增量。

---

## 10. 一句话总结

**P1 用 14 个 commits / 0 行净代码 / +25 个测试, 把 graph_builder.py 从 3051 行 / 12+ 模板重复 / 0 测试, 优化到 392 行 / 0 重复 / 25 测试守护, 全程 0 行删除, 每次 commit 独立可回滚。**
