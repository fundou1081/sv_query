# Handler 完整性报告（基于实际使用情况）

> 生成时间: 2026-05-24 16:35 GMT+8
> 评估标准: 只考虑语义 AST 中实际出现的 pyslang 类型

---

## 一、基础数据

| 指标 | 数量 |
|------|------|
| pyslang SyntaxKind 总数 | 536 |
| 已定义的 Handler 总数 | 375 |
| **代码中实际引用的 SyntaxKind** | **31** |
| 有 Handler 且被使用 | 22 |
| 被使用但无 Handler | 9 |
| 有 Handler 但从未使用 | 353 |

---

## 二、覆盖率分析（正确计算）

| 指标 | 公式 | 结果 |
|------|------|------|
| Handler 定义覆盖率 | 375/536 | 70.0% |
| **实际使用覆盖率** | **31/536** | **5.8%** |

### 正确理解
- 我们定义了 375 个 Handler（覆盖 70% 的 pyslang 类型）
- 但代码实际**只用到 31 个** SyntaxKind
- **94.1% 的 Handler 是死代码**（353 个从未被调用）

---

## 三、问题诊断

### 严重问题
1. **死代码率 94.1%** - 353 个 Handler 定义后从未被调用
2. **缺失 9 个实际需要的 Handler** - 代码在用但没实现

### 未使用的 Handler (353 个)
这些 Handler 占 94.1%，是纯粹的死代码：

| 分类 | 数量 | 示例 |
|------|------|------|
| Property 表达式 | 50+ | `AssertPropertyStatement`, `AssumePropertyStatement` |
| Sequence 表达式 | 30+ | `AndSequenceExpr`, `OrSequenceExpr` |
| Constraint 相关 | 40+ | `ConditionalConstraint`, `ImplicationConstraint` |
| Coverage 相关 | 30+ | `CoverGroup`, `CoverPoint`, `CoverCross` |
| Class 相关 | 20+ | `ClassDeclaration`, `ClassMethodDeclaration` |
| 其他表达式 | 100+ | `AddExpression`, `SubtractExpression` 等 |

### 缺失的 Handler (9 个实际需要)
```python
Declarator, HierarchicalInstance, ImplicitAnsiPort,
ImplicitNonAnsiPort, NamedType, PORT_OUT,
SeparatedList, SyntaxList, VariableDimension
```

---

## 四、建议

### 立即行动
1. **删除 353 个未使用的 Handler** - 大幅减少死代码
2. **补充缺失的 9 个 Handler** - 确保实际使用的功能完整
3. **保留 22 个核心 Handler** - 实际业务需要的

### 长期改进
1. 添加 Handler 前必须验证代码中是否实际需要
2. 使用代码覆盖率工具验证 Handler 被调用
3. 定期运行使用情况分析脚本

---

## 五、铁律补充建议

基于本次分析，建议新增：

### 铁律33: Handler 必须基于实际需要添加
**规则**: 添加 Handler 前必须确认代码中有对应的 SyntaxKind 引用，禁止基于假设或文档添加

### 铁律34: 定期清理未使用的 Handler
**规则**: 每个季度运行使用情况分析，删除从未被调用的 Handler

---

*本报告由 usage_analysis.py 自动生成*