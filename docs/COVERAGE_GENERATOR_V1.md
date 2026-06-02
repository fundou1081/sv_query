# Control Coverage Generator V1 发布说明

> 发布日期: 2026-06-02
> 版本: V1
> 状态: 已完成
> TDD 流程: 10 个 cycle 全部完成

---

## V1 目标

基于已有的 `true condition` 提取能力, 递归展开到原子信号 (含位选),
自动生成 `cross` coverage 模板 + 关键值 bins.

---

## 最终数据

- 总代码量: ~1600 行 (src + tests)
- 新增测试: 68 个 (V1 全覆盖)
- TDD Cycle: 10 个 (Red→Green→Refactor)
- Git commits: 10 个 (含 1 个 plan + 9 个 cycle)
- 测试总通过: 1315 / 1315 (100%)
- ruff 错误: 0 (新增代码)
- 文档: 1 个用户文档 (8516 字节)

---

## 已实现功能

### 核心算法
- 表达式解析 (含位选 a[3:0], 字面量过滤, 三元/二元/比较)
- Driver 链递归追踪
- 模块端口边界停止
- 跨模块检测 (报错)
- 循环引用保护 (visited 集合)
- 深度限制 (max_depth)
- 信号树大小限制 (max_signals=5, 超限报错)

### 复用现有模块
- SignalGraph.find_drivers() - 沿 driver 链
- SignalExpressionVisitor.extract() - AST 路径 (已修复 dispatch bug)
- TraceEdge.effective_condition - 条件数据源
- TraceNode.is_port - 端口检测
- NodeKind.PORT_IN/OUT/INOUT - 端口 kind

### 输出
- Markdown 报告 (含概要, 错误, 原子信号清单, 控制块详情, covergroup 模板)
- 证据链 (EvidenceStep 列表)
- CLI 入口 (coverage suggest)

---

## TDD 意外发现的 Bug (已修复)

在 Cycle 8 (AST 集成) 期间, 发现并修复了 SignalExpressionVisitor 的 3 个 bug:

1. Dispatch 错误: self._HANDLERS[kind_name](self, node)
   - 但 method 已经是 bound method, 多传了 self
   - 修复: self._HANDLERS[kind_name](node)

2. SignalResult.merge() 缺失: 多个 handler 引用但方法不存在
   - 修复: 添加 merge() 方法, 支持链式调用

3. extract_identifier_name 不设 all_signals: 只设了 primary
   - 修复: 同时设置 all_signals=[signal_name]

这些 bug 影响所有用 SignalExpressionVisitor 的代码, 不只是 coverage_generator.

---

## 文件结构

```
src/trace/core/
  coverage_models.py       # 数据类 (SourceLocation, AtomicSignal, etc.)
  coverage_generator.py    # 核心类 (ControlCoverageGenerator)

src/cli/commands/
  coverage.py              # CLI 入口 (coverage suggest)

sim/tests/unit/
  test_coverage_generator.py  # 68 个测试 (10 cycle)

docs/
  COVERAGE_GENERATOR_PLAN.md   # 实施计划
  COVERAGE_GENERATOR.md         # 用户文档
  COVERAGE_GENERATOR_V1.md      # 本文档
```

---

## 快速体验

```bash
# 用项目自带的 test_data_path.sv 体验
python run_cli.py coverage suggest \
  -f sim/tests/regression/test_data_path.sv \
  --signal data_path.stage1_data
```

---

## V1 限制 (V2 候选)

| 限制 | 原因 | V2 计划 |
|------|------|---------|
| 跨模块信号 | RTL 通常不会这么设计 | 提示用户用顶层信号 |
| 多信号同时 decompose | V1 只处理第一个 | 扩展支持 |
| JSON 输出 | CLI 占位符 | 复用 dataclass.asdict |
| AST 自动提取 | graph_builder 暂存条件字符串 | 添加 condition_ast 字段 |
| 关键值 bin 自动生成 | 需 Z3 求解 | V3 集成 Z3 |
| ControlFlowGraph 集成 | control_vars 字段未填充 | 修复 graph_builder |

---

## 经验教训

1. TDD 价值: Cycle 8 发现了 3 个已存在但未测试的 bug
2. 小步快跑: 每个 cycle 一个特性, 可独立回滚
3. 真实数据测试: Cycle 7 用 test_data_path.sv 跑通
4. 优先复用: 避免重写 SignalExpressionVisitor, 先用字符串解析
5. 明确停止条件: 端口, 深度, 循环都需要明确终止

---

**下一步**: 等待 V2 需求 (AST 集成 / Z3 / 多信号) 或进入其他项目
