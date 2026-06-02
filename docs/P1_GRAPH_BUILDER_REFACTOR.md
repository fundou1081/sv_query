# P1 graph_builder.py 重构计划

> 创建时间: 2026-06-03
> 状态: 规划完成, cycle 0
> 目标: graph_builder.py 3054 行 → 多模块, 改善可测性 + 修复已知结构 bug
> 风险: 🟢 中 (纯物理拆分, 0 逻辑改动)

---

## 1. 起点诊断 (2026-06-03)

### 1.1 文件结构

`src/trace/core/graph_builder.py` 3054 行实际包含 **5 个类 + 1 data class**:

| 类 | 行 | 范围 | 状态 |
|----|----|------|------|
| `ExtractorResult` | 7 | L22-28 | data class |
| `DriverExtractor` | **1762** | L29-1790 | 寄居, 应该独立 |
| `LoadExtractor` | 402 | L1791-2193 | 寄居, 应该独立 |
| `ConnectionExtractor` | 432 | L2194-2626 | 寄居, 应该独立 |
| `ClockDomainExtractor` | 72 | L2627-2699 | 寄居, 应该独立 |
| `GraphBuilder` | 354 | L2700-3053 | 主类 (应保留) |

### 1.2 V2.A.2 暴露的问题 (详见 sv_query_status_20260603_v2a2.md)

1. **1554 → 1762 行的 DriverExtractor** 寄居在 graph_builder.py (我之前估错了)
2. **8+ `ctx.get(...)` 模板 + 7+ `sig_cond` 模板** 在 builder 主体内
3. **builder + visitor 靠 dict key 隐式协调** (V2.A.2 6 个 cycle 都在解这个)
4. **0 单元测试** (3054 行靠 11 个集成测试守护)
5. **4 个已知 bug** 全是结构问题 (control_vars, sig_cond, case, control_vars 字段未用)

### 1.3 V2.A.2 实际成本

| 应做 | 实际 | 倍率 | 摩擦来源 |
|------|------|------|----------|
| 35 min | 115 min | 3.3x | 全部在 graph_builder 协调成本 |

---

## 2. 目标

**最小风险** 完成 graph_builder.py 物理拆分, 改善:
- ✅ 可测性 (每个类独立可测)
- ✅ 可读性 (单一职责文件)
- ✅ 导入速度 (按需 import)
- ✅ V2.A.2 cycle 17e+ 等"修结构 bug"工作有基础

**不动** (留作后续 P1.x):
- ❌ dict 改 dataclass (治本但风险高)
- ❌ 单元测试套件 (阶段 2 任务)
- ❌ TraceEdge 工厂抽取 (后续 cycle)

---

## 3. Cycle 拆分 (本计划)

| Cycle | 内容 | 文件 | 风险 | 测试 |
|-------|------|------|------|------|
| **0** | **本计划文档** | `docs/P1_GRAPH_BUILDER_REFACTOR.md` | 🟢 0 | 0 |
| **1** | **DriverExtractor → `driver_extractor.py`** | 1 拆 1 | 🟢 低 | 跑回归 1380 测试 |
| **2** | LoadExtractor → `load_extractor.py` | 1 拆 1 | 🟢 低 | 跑回归 |
| **3** | ConnectionExtractor → `connection_extractor.py` | 1 拆 1 | 🟢 低 | 跑回归 |
| **4** | ClockDomainExtractor → `clock_domain_extractor.py` | 1 拆 1 | 🟢 低 | 跑回归 |
| **5** | graph_builder.py 留 GraphBuilder + 必要 re-export | cleanup | 🟢 低 | 跑回归 |
| **6** | 文档 + 收尾 | `docs/P1_GRAPH_BUILDER_REFACTOR.md` 更新 | 🟢 0 | 0 |
| **合计** | 4 个新文件 | **0 净代码改动** (纯搬家) | | **1380 回归** |

### 3.1 Cycle 1 详细 (先做这一个,验证模式)

**目标**: 把 `DriverExtractor` 类从 `graph_builder.py` 搬到新 `driver_extractor.py`

**步骤**:
1. 创建 `src/trace/core/driver_extractor.py`
2. 复制 `class DriverExtractor` 完整定义 (L29-1790, 含所有方法和内部辅助)
3. 添加必要 imports (重跑 imports 检测)
4. 在 `graph_builder.py` 改成:
   ```python
   from .driver_extractor import DriverExtractor  # re-export
   ```
5. 删除 graph_builder.py 中的类定义
6. 跑 1380 测试, 必须全过

**风险**:
- imports 顺序/循环依赖 (可能需要 `__init__.py` 调整)
- 内部辅助类 (`_get_all_signals` 重复定义在 L38 和 L1776,需要小心)

**保护**:
- 改动前后 `git diff` 逐行核对
- 1380 测试必过
- `ruff check src/` 干净

### 3.2 Cycle 2-4 同样模式

每个 Extractor 都是:
1. 复制类到新文件
2. 调整 imports
3. 原文件 re-export
4. 测试

### 3.3 Cycle 5 收尾

`graph_builder.py` 应该只剩 `GraphBuilder` 主类 + `ExtractorResult` data class + 4 个 re-export。

---

## 4. 验收标准

- [ ] 5 个新文件存在, 各 Extractor 独立
- [ ] graph_builder.py 缩到 < 400 行 (只剩 GraphBuilder + ExtractorResult)
- [ ] `from trace.core.graph_builder import DriverExtractor` 仍工作 (re-export 兼容)
- [ ] 1380 现有测试全过
- [ ] ruff src/ 0 新错误 (允许同 7 个 pre-existing)
- [ ] 0 行删除 / 0 行净改动 (纯搬家)
- [ ] V2.A.2 测试 (TestGraphBuilderConditionAstV2A2 等) 不需要改

---

## 5. 不在本计划范围 (后续 P1.x)

| 后续 | 内容 | 估计 cycle |
|------|------|----------|
| P1.7 | TraceEdgeFactory 抽取 (8+ ctx.get + 7+ sig_cond 模板) | 2 |
| P1.8 | dict → `BuilderContext` dataclass | 1-2 |
| P1.9 | graph_builder 单元测试 (50+ 测试) | 1-2 |
| P1.10 | 修 4 个已知 bug (control_vars, sig_cond, case, control_vars 字段) | 2 |
| P1.11 | V2.A.2 cycle 17e+ (sig_cond-based 7+ 点 + case 路径) | 2 |

---

## 6. 经验教训 (预设)

- **物理拆分是最低风险改动**: 不动逻辑, 0 净代码, 测试守护
- **每 cycle 一个类**: 不贪多, 验证模式后再推下一个
- **re-export 保兼容**: `from graph_builder import DriverExtractor` 仍工作
- **跑测试作单一信号**: 1380 全过就是成功的唯一标准
- **用户已确认"小心"原则**: 每个 cycle 给他看 diff

---

## 7. 时间线

| 时间 | 事件 |
|------|------|
| 2026-06-03 00:35 | 用户询问 graph_builder 重构话题 |
| 2026-06-03 00:38 | 用户说"先 commit" (本计划文档) |
| TBD | Cycle 1-5 实施 |

---

**创建**: 2026-06-03
**状态**: 规划完成, cycle 0 待用户 sign-off
**下一步**: cycle 1 (DriverExtractor 物理拆分) — 等用户确认
