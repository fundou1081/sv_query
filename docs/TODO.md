# TODO - sv_query 项目

> 创建时间: 2026-05-24
> 项目路径: /Users/fundou/my_dv_proj/sv_query

---

## 当前任务

### P1 - 高优先级

_(无)_

---

### P2 - 中优先级

#### [ ] SignalExpressionVisitor 单 dispatch 重构
- **类型**: 重构 (优化，非必需)
- **描述**: 将双接口 (visit + get_all_signals) 重构为单 dispatch + SignalResult
- **参考文档**: `docs/ARCHITECTURE_IMPROVEMENT.md`
- **预期收益**: 
  - -50% handler 代码量
  - 消除别名映射重复
  - 提升可测试性
- **风险**: 中等 (需迁移 40+ handlers)
- **状态**: 当前系统已使用 Visitor 模式，无 Legacy fallback
- **前置条件**: 可选重构，当前系统稳定

#### [ ] StatementCollectorVisitor 架构对齐 (可选)
- **类型**: 重构
- **描述**: 参照 SignalExpressionVisitor 重构方案进行类似改进
- **参考文档**: `docs/ARCHITECTURE_IMPROVEMENT.md`
- **前置条件**: 可选，当前系统工作正常

---

### P3 - 低优先级 / 长期

#### [ ] Visitor 组合模式实现
- **类型**: 架构改进
- **描述**: 将 Visitor 拆分为 SignalExtractor / ContextExtractor 等可组合组件
- **前置条件**: 单 dispatch 重构完成

#### [ ] 类型安全增强
- **类型**: 改进
- **描述**: 使用 Protocol 定义节点类型，提升 IDE 自动补全和类型检查
- **前置条件**: Python 3.8+ (runtime checkable)

---

## 已完成

### ✅ P1 - 高优先级

#### [x] Visitor 替代 Legacy Fallback
- **完成时间**: 2026-05-23
- **描述**: [铁律29] 移除 fallback，Legacy 方法抛出 NotImplementedError
- **验证**: 834 测试通过，无 fallback 触发

#### [x] SignalExpressionVisitor 覆盖率增强
- **完成时间**: 2026-05-23
- **描述**: 从初始覆盖率增强到 38/41 ExpressionKind (93%)
- **新增方法**: 20+ visit methods, 20+ get_all methods

#### [x] StatementCollectorVisitor 覆盖率增强
- **完成时间**: 2026-05-23
- **描述**: 从初始覆盖率增强到 30/32 StatementKind (94%)
- **新增方法**: 14 visit methods

### ✅ P2 - 中优先级

#### [x] 架构改善提案文档
- **完成时间**: 2026-05-24
- **描述**: 创建 `docs/ARCHITECTURE_IMPROVEMENT.md`，详细记录问题、方案、迁移路径
- **提交**: `1d55e4c`

---

## 备注

- P2 重构任务建议在有明确需求时进行（如需要支持更多 SV 类型）
- 当前系统稳定，可作为后续改进的基准
- 每次提交前确保 834 测试通过