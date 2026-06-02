# P1 graph_builder.py 重构完整计划

> 创建时间: 2026-06-03 (重写)
> 状态: 规划完成, cycle 0
> 目标: **解决 5 个结构问题**, 不止物理移动
> 核心原则: 物理拆分是结果, 不是目标

---

## 1. 起点诊断 (2026-06-03)

### 1.1 之前 plan 的问题

`P1_GRAPH_BUILDER_REFACTOR.md` 之前版本 (commit 1baa2a9) 是**纯物理拆分**:
- 5 个 Extractor 类各搬到一个文件
- 0 逻辑改动, 0 净代码
- 用户说"如果只是物理移动位置, 没有必要, 主要看其他问题"

**用户对**。物理拆分改善可读性但不解决根本问题。

### 1.2 真问题 (按价值排序, 不按行数)

| # | 问题 | 证据 | 解决 |
|---|------|------|------|
| 1 | **8+ `ctx.get(...)` 模板 + 7+ `sig_cond` 模板** | V2.A.2 cycle 17d: 同样改动重复 3 次; 8 个 ctx-based 模板完全一样 | TraceEdgeFactory |
| 2 | **builder + visitor 靠 dict key 隐式协调** | V2.A.2 cycle 17a-b: 6 个 cycle 在解这个 wiring; 加 key 在 A, 忘记读在 B → 无报错 | BuilderContext dataclass |
| 3 | **4 个已知 bug 全是结构问题** | control_vars 未填, sig_cond-based 7+ 点没填 AST, case 路径未填 cond_expr, control_vars 字段声明了不用 | 修 4 个 bug |
| 4 | **0 单元测试** | find sim/tests -name "test_graph_builder*" 返回空 | 加 50+ 单元测试 |
| 5 | **3054 行 / 5 类挤一文件** | 类边界 L22/29/1791/2194/2627/2700 | 物理拆分 (上面 4 步完成后,这一步**变成"自然"**) |

**关键洞察**: 1-4 是**结构性问题**, 5 是**症状**。先治本后整理。

### 1.3 V2.A.2 的真教训

| Cycle | "应该"用时 | 实际 | 倍率 | 摩擦 |
|-------|----------|------|------|------|
| 16 | 5 min | 5 min | 1x | ✅ |
| 17a | 5 min | 15 min | 3x | 找 dict-key contract |
| 17b | 5 min | 30 min | 6x | 8 个 ctx.get 模板去重冲突 |
| 17c | 5 min | 20 min | 4x | 写测试才发现 adapter 没传 |
| 17d | 5 min | 30 min | 6x | 重复 3 次 edit 失败 (context 不够 unique) |
| 18 | 10 min | 15 min | 1.5x | ✅ |

**总: 应 35 min, 实际 115 min, 3.3x 慢**。全在 4 个**结构性问题**上摩擦。

如果有了 TraceEdgeFactory, 17d 的 7 行改动会变成 1 行 × 1 处。
如果有了 BuilderContext, 17a-b 的 wiring 不会有 3-6x 摩擦。

---

## 2. 目标

按"先治本后整理"原则,分阶段:

| 阶段 | 目标 | 状态 |
|------|------|------|
| **P1.1 TraceEdgeFactory** | 消除 8+ ctx.get + 7+ sig_cond 模板重复 | 主线 |
| **P1.2 修 4 个已知 bug** | 修结构 bug (顺路, 因为 factory 后改字段容易) | 主线 |
| **P1.3 单元测试** | 50+ 测试, 把 graph_builder 拉出测试真空 | 主线 |
| **P1.4 BuilderContext dataclass** | 替换 dict, 编译期 key 检查 (可选, 风险高) | 评估后 |
| **P1.5 物理拆分** | 上面 4 步完成后, 文件拆分是自然结果 | 评估后 |

**P1.1-P1.3 是必做**, **P1.4-P1.5 视前面收益决定**。

---

## 3. Cycle 拆分 (本计划)

### 3.1 总览

| Phase | Cycle | 内容 | 风险 | 行数 | 测试 |
|-------|-------|------|------|------|------|
| **1.1** | **1** | TraceEdgeFactory 类 + `make_edge()` 单方法 | 🟢 低 | +60 | +8 |
| **1.1** | **2** | ctx-based 8 个 TraceEdge 点改用 factory | 🟡 中 | -10 (去重) | +5 |
| **1.1** | **3** | sig_cond-based 7+ 个点改用 factory (ctx 化 sig_cond) | 🟡 中 | ~ +30 (ctx 化) | +5 |
| **2** | **4** | 修 control_vars 填 + control_vars 字段使用 | 🟡 中 | +20 | +3 |
| **2** | **5** | case 路径 condition_ast 透传 (visitor + builder) | 🟡 中 | +15 | +3 |
| **3** | **6** | TraceEdgeFactory 单元测试套件 | 🟢 低 | +150 (测试) | +15 |
| **3** | **7** | Bug 回归测试 (4 个 bug 各 2 测试) | 🟢 低 | +80 (测试) | +8 |
| **5** | **8** | 物理拆分 DriverExtractor (顺路做) | 🟢 低 | 0 净 | 0 |
| **5** | **9** | 物理拆分其他 3 个 Extractor | 🟢 低 | 0 净 | 0 |
| 收尾 | **10** | 文档 + 报告 | 🟢 0 | +100 md | 0 |
| **合计** | | | | **+445 行 (+150 测试 + ~30 实施 + 165 文档)** | **+47 测试** |

### 3.2 Cycle 1 详细 (TraceEdgeFactory 类)

**目标**: 创建 `src/trace/core/edge_factory.py`, 单方法 `make_edge()`

**新文件** (~60 行):
```python
@dataclass
class EdgeContext:
    """集中所有 TraceEdge 上下文 (替代 ctx dict 字段访问)"""
    clock: str = ""
    condition: str = ""
    effective_condition: str = ""
    condition_ast: Any | None = None  # V2.A.2 加的
    reset: str = ""

class TraceEdgeFactory:
    """统一创建 TraceEdge (消除 8+ ctx.get + 7+ sig_cond 模板)"""
    def make_edge(
        self,
        src: str,
        dst: str,
        expression: str,
        kind: EdgeKind = EdgeKind.DRIVER,
        assign_type: str = "continuous",
        bit_slice: str = "",
        ctx: dict | None = None,
        # V2.A.2 延伸: 也支持 sig_cond 直接传
        sig_cond: str = "",
        sig_cond_ast: Any | None = None,
    ) -> TraceEdge:
        """从 ctx dict 或直接参数构造 TraceEdge"""
        c = ctx or {}
        return TraceEdge(
            src=src, dst=dst, kind=kind, assign_type=assign_type,
            expression=expression, bit_slice=bit_slice,
            clock_domain=c.get("clock", "") if ctx else "",
            condition=c.get("condition", "") if ctx else sig_cond,
            effective_condition=c.get("effective_condition", "") if ctx else "",
            condition_ast=(
                c.get("condition_ast") if ctx
                else sig_cond_ast  # sig_cond-based 点
            ),
        )
```

**测试**:
- 1.1 空 ctx + 参数 → 正确 TraceEdge
- 1.2 ctx dict 含 condition → 读 ctx
- 1.3 ctx dict 含 condition_ast → 读 ctx
- 1.4 sig_cond 字符串 + sig_cond_ast → 走 sig_cond 路径
- 1.5 边界: None ctx + 空 sig_cond → 所有字段默认值
- 1.6 assign_type 透传
- 1.7 bit_slice 透传
- 1.8 多次创建不同 kind → 正确

**好处**:
- 8+ ctx-based 点改成 `factory.make_edge(src, dst, expr, ctx=ctx)` 一行
- 7+ sig_cond-based 点改成 `factory.make_edge(src, dst, expr, sig_cond=sig_cond, sig_cond_ast=...)` 一行
- **新字段 (如 V3 Z3 bin) 只在 factory 改一处**

### 3.3 Cycle 2 详细 (替换 8+ ctx-based 创建点)

**目标**: graph_builder.py 8 个 `TraceEdge(condition=ctx.get(...), ...)` 改用 factory

**步骤**:
1. 在 GraphBuilder `__init__` 加 `self._edge_factory = TraceEdgeFactory()`
2. 8 个创建点逐个替换 (每点 1 commit, 跑测试)
3. 全部替换后, 删 ctx-based 模板代码

**安全**:
- 8 个独立 commit, 任何 1 个出问题可 `git revert`
- 1380 测试守护
- factory 的 8 个测试已守住 factory 行为

### 3.4 Cycle 3 详细 (替换 7+ sig_cond-based 创建点)

**目标**: sig_cond-based 创建点也走 factory (传 sig_cond + sig_cond_ast)

**挑战**:
- `sig_cond` 来自局部变量 (不是 ctx)
- sig_cond 的 AST 来自哪里? 需要新 ctx 化
- **V2.A.2 17e+ 一直推迟的工作**

**步骤**:
1. 找到 sig_cond 的源头 (通常是 `if (cond) x <= ...` 的 cond)
2. 把 `sig_cond` 和 `sig_cond_ast` 一起塞进局部变量
3. 创建点用 `factory.make_edge(src, dst, expr, sig_cond=..., sig_cond_ast=...)`
4. 跑测试

**预计改动**: 30 行 (新增 sig_cond_ast 跟踪 + 7+ 个点替换)

### 3.5 Cycle 4 详细 (修 control_vars bug)

**目标**: graph_builder.py 已知 bug — `CONTROL_FLOW_BLOCK.control_vars` 未填

**步骤**:
1. 找 `control_vars` 字段定义位置
2. 找应该填它的位置 (visitor 或 builder)
3. 加填的代码
4. 加测试 (regression: 填前空, 填后有)

### 3.6 Cycle 5 详细 (case 路径 condition_ast 透传)

**目标**: V2.A.2 cycle 17a 漏掉的 case 路径

**步骤**:
1. visitor `visit_case_statement` (line 760-781) 加 `condition_ast: item_cond_expr`
2. builder 确认 case 路径的 TraceEdge 也用 factory
3. 测试: 跑 SV 带 `case` 的文件, 验证 case 条件也有 AST 证据

### 3.7 Cycle 6-7 详细 (单元测试)

**目标**: graph_builder 有 50+ 单元测试

**Cycle 6**: TraceEdgeFactory 单元测试 (15 测试)
- 每个 factory 方法的边界 case
- 各种 ctx 组合
- 各种 sig_cond/sig_cond_ast 组合

**Cycle 7**: Bug 回归测试 (8 测试)
- control_vars 填前后对比
- case 路径 AST 填前后对比
- sig_cond-based 点的 AST 填前后对比

### 3.8 Cycle 8-9 详细 (物理拆分, 顺路做)

**目标**: DriverExtractor 搬到 `driver_extractor.py` (其他 3 个随后)

**为什么放最后**: 上面 7 个 cycle 改了 graph_builder, 现在它已经松散些, 拆分是"自然"。

**步骤**:
- Cycle 8: DriverExtractor → driver_extractor.py (1762 行, 走 cycle 1 失败的 教训, 提前 import 分析)
- Cycle 9: 其他 3 个 Extractor (LoadExtractor/ConnectionExtractor/ClockDomainExtractor) → 各文件

### 3.9 Cycle 10 收尾

- 更新 `P1_GRAPH_BUILDER_REFACTOR.md` 实施结果
- 数字 + commits 总结
- 哪些做到了, 哪些推到 P1.4 / P1.5 (可选)

---

## 4. 验收标准 (整个 P1 计划)

- [ ] TraceEdgeFactory 类存在并测试
- [ ] 8+ ctx-based 创建点都用 factory
- [ ] 7+ sig_cond-based 创建点都用 factory
- [ ] control_vars 已知 bug 修复 (有回归测试)
- [ ] case 路径 condition_ast 透传 (有测试)
- [ ] 50+ 新单元测试
- [ ] graph_builder.py < 2000 行 (从 3054 缩)
- [ ] 1380 现有测试全过
- [ ] V2.A.2 行为不变 (回归保护)
- [ ] ruff src/ 不引入新错误
- [ ] V2.A.2 cycle 17e+ 不再需要 (因为 cycle 3 解决了)

---

## 5. 不在本计划范围

| 后续 | 内容 | 风险 | 评估点 |
|------|------|------|--------|
| P1.4 | BuilderContext dataclass (替换 ctx dict) | 🟡 中-高 | 视 P1.1-P1.3 收益 |
| P1.5 | graph_builder.py 进一步拆分 (主类拆 sub-builders) | 🟡 中 | 视 P1.1-P1.3 收益 |
| V2.A.2 cycle 17e+ | (被 P1 cycle 3 替代) | - | - |
| V3 | Z3 / from_dict / JSON Schema | - | V2 收尾后启动 |

---

## 6. 经验教训 (从 V2.A.2 提炼)

15. **物理移动是症状, 不是治本**: 文件拆小但结构问题 (8+ 模板, dict 协调) 仍在
16. **structure problems first, file split later**: 先改结构, 拆分自然发生
17. **每次小步可独立回滚**: V2.A.2 6 个 cycle 守住"小心", P1 沿用
18. **TDD 红→绿 真实暴露问题**: 17c 写测试才发现 graph 缺 adapter
19. **CLI 端到端是最终验证**: 单元测试通过 ≠ 用户能用

### P1 新增教训 (预设)
20. **factory pattern 解决模板重复**: 8+ ctx.get 模板 = 1 个 factory
21. **dict 协调脆弱**: 改 key 名时无编译期检查
22. **测试真空是工程债**: 3054 行 0 测试 = bug 只能端到端发现
23. **物理拆分是结果**: 改完结构, 拆分自然; 反之不自然

---

## 7. 时间线

| 时间 | 事件 |
|------|------|
| 2026-06-03 00:35 | 用户问 graph_builder 重构 |
| 2026-06-03 00:38 | 之前 plan (物理拆分) commit, 但用户说"主要看其他问题" |
| 2026-06-03 00:42 | revert cycle 1 (物理拆分), 重写完整 plan (本文件) |
| TBD | Cycle 1 (TraceEdgeFactory) — 等用户 sign-off |

---

**创建**: 2026-06-03
**状态**: 规划完成, 等用户 sign-off
**下一步**: Cycle 1 (TraceEdgeFactory 类 + 8 测试) — 用户 OK 后开
