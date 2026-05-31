# sv_query 代码架构深度 Review 报告

> 日期: 2026-05-31
> Review 维度: 运行时状态 / 未来演进 / Bug修复理解度

---

## 1. 运行时实际状态

### 1.1 测试健康度

| 指标 | 数值 | 评估 |
|------|------|------|
| 总测试数 | 1080+ | ✅ 健康 |
| 通过率 | 100% (1 skipped) | ✅ 优秀 |
| 测试耗时 | ~22s | ✅ 合理 |
| [NOT TESTED] 注释 | ~50+ 个 | ⚠️ signal_expression_visitor.py |

**结论**: 核心功能运行稳定，无运行时错误。

---

### 1.2 已知 Bug 分析

根据 `docs/archive/SVQUERY_ISSUES_AND_FIXES.md` 和 `ISSUE_ROOT_CAUSE.md`:

| Issue | 位置 | 类型 | 状态 |
|-------|------|------|------|
| Issue 28 | graph_builder.py | 注释过滤 | ✅ 已修复 |
| Issue 33 | graph_builder.py | 字面量节点 | ✅ 已修复 |
| Issue 34 | graph_builder.py | 循环变量 | ✅ 已修复 |
| Issue 21, 27 | base.py/graph_builder.py | 参数表达式 | ✅ 已修复 |
| Issue 29 | base.py | 复杂参数 | ✅ 已修复 |
| Issue 31 | base.py | 位宽解析 | ✅ 已修复 |

**Bug 修复模式观察**:
- Bug 多集中在 graph_builder.py 的信号提取逻辑
- 根因往往是 pyslang API 变化（`.timing` vs `.timingControl` 等）
- 修复方式是添加 `hasattr` + fallback 逻辑

**这说明什么？**
- Bug 修复分散在各 Extractor 内部，职责内聚
- 拆分 graph_builder.py 不会让 bug 更好修

---

### 1.3 代码质量铁律

DriverExtractor 内有明确的铁律标注：

```python
# [铁律29] 使用 Visitor 替代旧实现，保留 fallback
# [铁律3.1] 禁止静默忽略错误 (except: pass)
```

**这说明有架构规范，不是野蛮生长。**

---

## 2. 未来功能演进

### 2.1 规划中的功能

根据 DESIGNER_PLAN.md:

| 功能 | 需求 | 影响组件 |
|------|------|----------|
| SVA skeleton 生成 | P2 | signal_expression_visitor.py |
| Covergroup skeleton 生成 | P2 | constraint_visitor.py |
| neato 力导向布局 | 4.1 | signal_graph_viewer.py |
| 高风险区域聚焦 | 4.1 | signal_graph_viewer.py |

### 2.2 演进对架构的要求

**SVA skeleton 生成** 需要：
- 信号表达式解析 → `signal_expression_visitor.py`
- 条件提取 → `DriverExtractor._extract_condition_str()`
- 模板生成 → 新模块

**结论**: 
- 新功能主要扩展 `signal_expression_visitor.py`（已是 7341 行）
- 不需要重构 graph_builder.py
- 需要关注的是 `signal_expression_visitor.py` 的可扩展性

---

### 2.3 Visitor 模式的问题

`signal_expression_visitor.py` (7341 行, 644 methods) 存在可扩展性问题：

```python
# 问题：每新增一种表达式类型，需要添加 2 个方法
def get_all_xxx(self, node): ...     # get_all_*
def extract_xxx(self, node): ...    # extract_*
```

**如果有 50+ [NOT TESTED] 表达式类型**：
- 代码膨胀但未被充分测试
- 新增功能需要修改大文件

**建议关注点**：不在 graph_builder.py，在于 `signal_expression_visitor.py` 的测试覆盖。

---

## 3. Bug 修复理解度

### 3.1 历史 Bug 模式

| Bug 类型 | 常见位置 | 修复难度 |
|----------|----------|----------|
| pyslang API 变化 | 各处 hasattr fallback | 🟢 简单 |
| 表达式解析遗漏 | signal_expression_visitor | 🟡 中等 |
| 端口/连接追踪 | graph_builder.py | 🟡 中等 |
| 参数展开 | base.py | 🟠 复杂 |

### 3.2 修复难度评估

**graph_builder.py 内的 Bug 修复**:
- 难度：🟢 低-中等
- 原因：逻辑相对独立，有测试覆盖
- 证据：Issue 28/33/34 都在此处但都已修复

**base.py PyslangAdapter 的 Bug 修复**:
- 难度：🟡 中等
- 原因：2050 行，职责多
- 证据：Issue 29/31/21 在此处

**signal_expression_visitor.py 的 Bug 修复**:
- 难度：🟡 中等
- 原因：7341 行，表达式类型多
- 证据：50+ [NOT TESTED] 标记

---

## 4. 真正的架构问题

### 4.1 问题定位

| 文件 | 行数 | 实际问题是... |
|------|------|---------------|
| `graph_builder.py` | 2832 | ❌ 不是问题，5 个独立 class |
| `base.py` | 2318 | ⚠️ PyslangAdapter 2050 行，职责多 |
| `semantic_adapter.py` | 1637 | ⚠️ 职责不清晰 |
| `signal_expression_visitor.py` | 7341 | 🔴 测试覆盖不足 |
| `DriverExtractor` | 1554 | 🟡 可接受，但偏大 |

### 4.2 真正的可维护性问题

**1. signal_expression_visitor.py 测试不足**
- 50+ 个 `[NOT TESTED]` 表达式类型
- 这些代码虽存在但无法验证正确性
- 影响：对新语法支持慢，Bug 发现滞后

**2. base.py PyslangAdapter 职责膨胀**
- 2050 行，包含：
  - AST 遍历
  - 端口解析
  - 实例提取
  - 参数解析
  - 类型系统
- 建议：按职责拆分

**3. semantic_adapter.py vs base.py 重复**
- 两个文件处理相似的语义问题
- 职责边界不清晰

---

## 5. 结论与建议

### 5.1 最终结论

| 评估项 | 结论 |
|--------|------|
| graph_builder.py 需要拆分？ | **❌ 不需要** |
| DriverExtractor 需要拆分？ | **⚠️ 可考虑，但非紧急** |
| base.py PyslangAdapter 需要拆分？ | **🟡 建议关注** |
| signal_expression_visitor.py 测试需加强？ | **🔴 建议优先** |
| semantic_adapter.py 职责需理清？ | **🟡 建议理清** |

### 5.2 实际推荐的行动

| 优先级 | 行动 | 理由 |
|--------|------|------|
| 🔴 P0 | **加强 signal_expression_visitor 测试** | 50+ [NOT TESTED] 是隐患 |
| 🟠 P1 | **拆分 base.py PyslangAdapter** | 2050 行太大，职责多 |
| 🟡 P2 | **理清 semantic_adapter vs base.py** | 减少重复职责 |
| 🟢 P3 | GraphBuilder 相关 | 暂不需要 |

### 5.3 为什么不推荐拆分 graph_builder.py

1. **运行时状态良好**：1080+ 测试全部通过
2. **Bug 修复无障碍**：历史 Bug 都在此处修复，无困难
3. **未来演进无关**：规划中的功能不依赖 graph_builder 重构
4. **代码结构合理**：内部是 5 个独立 class，不是 monolith

---

## 6. 附录：各文件问题定位

```
signal_expression_visitor.py (7341行)
├── 问题：测试覆盖不足（50+ [NOT TESTED]）
├── 建议：优先补测试，不是拆分
└── 影响：SVA skeleton 生成依赖此文件

base.py (2318行)
├── ASTWalker (63行) ✅ 无问题
├── PyslangAdapter (2050行) ⚠️ 职责多，需要拆分
└── Collector classes (191行) ✅ 独立性好

graph_builder.py (2832行)
├── DriverExtractor (1554行) 🟡 稍大但可接受
├── LoadExtractor (409行) ✅ 无问题
├── ConnectionExtractor (402行) ✅ 无问题
├── ClockDomainExtractor (73行) ✅ 无问题
└── GraphBuilder (370行) ✅ orchestrator，无问题

semantic_adapter.py (1637行)
├── 问题：与 base.py 职责有重叠
└── 建议：理清边界或合并
```

---

*Review 完成。结论：graph_builder.py 不需要拆分，真正需要关注的是 signal_expression_visitor.py 的测试覆盖和 base.py 的职责理清。*