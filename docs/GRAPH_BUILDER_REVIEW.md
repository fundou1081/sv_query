# GraphBuilder 重构必要性 Review 结论

> 日期: 2026-05-31
> 基于代码实际结构分析

---

## 1. 真实数据

| Class | 行数 | 问题程度 |
|-------|------|----------|
| **DriverExtractor** | **1554** | 🔴 **真正的巨无霸** |
| GraphBuilder | 370 | 🟢 正常 |
| LoadExtractor | 409 | 🟡 稍大，可接受 |
| ConnectionExtractor | 402 | 🟡 稍大，可接受 |
| ClockDomainExtractor | 73 | 🟢 正常 |

**关键发现**：
- GraphBuilder 本身只有 370 行，不是问题
- **DriverExtractor 一个类就有 1554 行**，才是真正的 monolith

---

## 2. 结论

### ❌ 不需要拆分 graph_builder.py

**理由**：
1. GraphBuilder (370行) 本身不大，是正常的协调器
2. 它做的是 orchestrator 的事——调用各个 Extractor
3. 拆分 GraphBuilder 收益很小

### 🔴 DriverExtractor 需要考虑拆分

**理由**：
1. 1554 行，单一职责承担过重
2. 包含多个子职责：
   - 信号表达式解析（SignalExpressionVisitor）
   - 赋值语句收集
   - 时钟/复位提取
   - 函数调用展开
3. 如果要拆，应该按子职责拆分

---

## 3. 建议的拆分方案（如果决定拆）

```
core/graph_builder.py (保持不变)
    └── DriverExtractor (拆分到)
    
core/builders/
├── __init__.py
├── driver_assignment_builder.py  # 赋值语句解析 (~500行)
├── driver_clock_reset_builder.py  # 时钟/复位提取 (~400行)
├── driver_invocation_builder.py  # 函数调用展开 (~400行)
└── driver_expression_resolver.py  # 表达式解析 (~300行)
```

**影响范围**：
- 只影响 `graph_builder.py` 内部
- 外部（CLI、测试）完全无感知
- 风险极低

---

## 4. 最终建议

| 决策 | 建议 |
|------|------|
| 拆分 graph_builder.py？ | ❌ **不需要** |
| 拆分 DriverExtractor？ | ⚠️ **可以考虑**，但不紧急 |
| 什么时候拆 DriverExtractor？ | 当 DriverExtractor 出现 bug 难修或功能难加时 |

### 推荐行动优先级

| 优先级 | 行动 | 理由 |
|--------|------|------|
| 🟢 低 | **暂不拆分任何文件** | 当前运行良好，无明显问题 |
| 🟡 中 | 如果非要拆 | **只拆 DriverExtractor**，按子职责拆分 |

---

## 5. 架构 Review 总结

**我之前给出的是"过度焦虑"的建议**：
- 把 2832 行当问题 → 实际上是多个独立 class 放在同一文件
- 没细看就建议拆 → 应该先理解代码结构

**正确的评估方式**：
1. 先看文件内有哪些 class
2. 算每个 class 的行数
3. 判断哪个 class 真的有问题
4. 只拆有问题的

---

*结论：graph_builder.py 不需要拆分。*
*如果未来要动，应该拆分 DriverExtractor，但不是现在。*