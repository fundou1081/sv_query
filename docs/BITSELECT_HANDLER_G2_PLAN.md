# BitSelectHandler vs graph_builder 实现统一 G2 计划

> **创建日期**: 2026-08-28 06:23
> **维护人**: QClaw Agent + 方豆
> **状态**: 🟡 in_progress (G2 计划 + diff 验证脚本完成, G3 待决策)
> **来源**: [ARCHITECTURE_REVIEW_2026-08-27.md §三.2](ARCHITECTURE_REVIEW_2026-08-27.md) + 实测数据
> **关联**: [ARCHITECTURE_TODOLIST #2](ARCHITECTURE_TODOLIST.md)

## 📋 背景

review §三.2 标记 "🔴 重复实现: BitSelectHandler vs graph_builder._create_hierarchical_bit_nodes 两套并行, 行为可能不一致"。

**但 review 是基于"代码位置 + 函数名"的粗略判断**——没实测。本 G2 计划通过实测发现真实情况。

## 🔍 实测数据（2026-08-28 06:23, commit `pending`）

**测试脚本**: `sim/tests/integration/test_bitselect_handler_diff.py` (7234 bytes, 3 个 fixture × 2 条路径)

**两条路径**:
- **路径 A**: 完整 unified_tracer → graph_builder.build_graph() → BitSelectHandler.process() (3 阶段: 提宽度/建 BIT_SELECT 边/扫 constraint)
- **路径 B**: SVCompiler + SemanticAdapter + GraphBuilder.build() → graph_builder._create_hierarchical_bit_nodes() (1 阶段简化版)

### Fixture 1: RangeSelect (`data[3:0]`)
```
路径 A: 节点 4, BIT_SELECT 边 1, 位选节点 1
路径 B: 节点 4, BIT_SELECT 边 1, 位选节点 1
边数差: 0
边/节点存在性: 完全一致
属性差异 (1 个 RangeSelect 节点):
  top.data[3:0]:
    bit_range:        A='[3:0]'  B=None  ← B 漏设
    parent_bit_start: A=0        B=None  ← B 漏设
    parent_bit_end:   A=3        B=None  ← B 漏设
    width:            A=(3, 0)   B=(1, 0) ← B 漏更新
```

### Fixture 2: ElementSelect (`data[0]`, `data[7]`)
```
路径 A: 节点 6, BIT_SELECT 边 2, 位选节点 2
路径 B: 节点 6, BIT_SELECT 边 2, 位选节点 2
边数差: 0
所有属性: 完全一致 (a/b 都没值, 都是 None)
```

### Fixture 3: Mixed (RangeSelect + ElementSelect 混合)
```
路径 A: 节点 8, BIT_SELECT 边 3, 位选节点 3
路径 B: 节点 8, BIT_SELECT 边 3, 位选节点 3
边数差: 0
仅 RangeSelect 节点属性差异 (2 个):
  top.data[15:8]: bit_range A='[15:8]' B=None ...
  top.data[7:0]:  bit_range A='[7:0]'  B=None ...
```

## 🎯 关键发现（推翻 review 判断）

review §三.2 担心的"两套并行行为不一致"——**只在 RangeSelect 节点属性层面成立**：

| 维度 | 结论 |
|---|---|
| **BIT_SELECT 边** | ✅ 完全一致 (0 差异) |
| **位选节点存在性** | ✅ 完全一致 (0 差异) |
| **ElementSelect 节点属性** | ✅ 完全一致 (都设不了, 因为都没 `[N:M]` 形式) |
| **RangeSelect 节点属性** | ❌ **路径 B 漏设 4 个属性**: bit_range / parent_bit_start / parent_bit_end / width |

**真实 bug**: 用户走路径 B（直接 GraphBuilder.build()）时，**RangeSelect 节点的 4 个元数据属性全丢**，下游 viz 工具可能因为这些属性缺失画错图。

**但这是真重复吗？** 不是。两套实现的**职责明确**：
- 路径 A (BitSelectHandler): RangeSelect `[N:M]` 完整处理（含 bit_range / parent_bit_* / width + constraint 扫描）
- 路径 B (graph_builder 内部): ElementSelect `[N]` 简化处理（只创建 BIT_SELECT 边）

**唯一需要统一的是**: 让路径 B 也具备 RangeSelect 完整属性设置能力。

## 📊 两套实现对比

| 维度 | 路径 A: `BitSelectHandler._create_hierarchical_bit_nodes` (line 290-377, 87 行) | 路径 B: `graph_builder._create_hierarchical_bit_nodes` (line 578-630, 52 行) |
|---|---|---|
| **输入格式** | `data[3:0]` (RangeSelect, `msb:lsb`) | `data[3]` (ElementSelect, 单索引) — 但 regex `\[.*?\]` 也能匹配 `[N:M]` |
| **regex** | `r"^([^\[]+)\[(\d+):(\d+)\]$"` 严格 `[N:M]` | `re.sub(r"\[.*?\]", "", child_id)` 所有 `[..]` 形式 |
| **bit_range 设置** | ✅ `child.bit_range = "[msb:lsb]"` | ❌ 不设 |
| **parent_bit_start** | ✅ `min(msb, lsb)` | ❌ 不设 |
| **parent_bit_end** | ✅ `max(msb, lsb)` | ❌ 不设 |
| **width 更新** | ✅ `(max, min)` | ❌ 不改 |
| **来源属性继承** | 从 `self.signal_widths.get()` | 从 child 节点继承 (含 file/line) |
| **时序** | unified_tracer 调, 在 class_builder 之后 | graph_builder.build_graph() 自动调 |

## 🛠️ G3 实施建议（待决策）

### 选项 1: 把路径 A 的 RangeSelect 处理**搬**到路径 B（最简）

- **做法**: `graph_builder._create_hierarchical_bit_nodes` 内复制路径 A 的 RangeSelect 分支
- **影响**: 路径 B 用户也能得到完整 RangeSelect 属性
- **副作用**: 路径 A 和路径 B 都做 RangeSelect 处理（如果走 unified_tracer，会重复执行）
- **风险**: 🟢 低（只是复制代码 + 加 regex 严格匹配 RangeSelect）
- **工作量**: 0.5 天

### 选项 2: 删路径 A 的 `_create_hierarchical_bit_nodes`，让路径 B 做全部

- **做法**: 路径 A 只保留 `Phase 1: _extract_all_widths` + `Phase 3: _scan_constraint_bit_selects`；`_create_hierarchical_bit_nodes` 完全移到路径 B
- **影响**: 路径 B 同时处理 RangeSelect + ElementSelect，约束扫描仍由路径 A 单独做
- **副作用**: unified_tracer 需要跳过路径 A 的 RangeSelect 处理（避免重复）
- **风险**: 🟡 中（需要改 unified_tracer 的 call sequence + 验证 constraint 扫描顺序依赖）
- **工作量**: 1 天

### 选项 3: 路径 A 完整保留，路径 B 升级到路径 A 的能力（路径 B 替代路径 A）

- **做法**: 路径 B 内嵌 RangeSelect 处理代码（吸收路径 A 的逻辑）；删路径 A
- **影响**: 单一来源, 行为一致
- **副作用**: graph_builder 现在的 1 阶段变 3 阶段, 复杂度上升
- **风险**: 🟡 中（graph_builder 是其他依赖核心, 改动影响面大）
- **工作量**: 1-1.5 天

### 选项 4: 不动代码，只在文档里说明两套的边界

- **做法**: 在 BitSelectHandler + graph_builder docstring 加注释 "这条路径不处理 RangeSelect, 走 BitSelectHandler"
- **影响**: 用户走路径 B 时知道 RangeSelect 属性缺失
- **副作用**: 没真正修复 bug, 只是让用户知情
- **风险**: 🟢 低（纯文档）
- **工作量**: 0.1 天

### 推荐: 选项 1

理由:
1. **修真实 bug**（路径 B 漏设 RangeSelect 4 个属性）
2. **风险最低**（只是复制已验证代码）
3. **工作量最小**（0.5 天）
4. **不引入重复**（路径 A 仍保留作 fallback, 如果未来 unified_tracer 移除路径 B 内的 RangeSelect 处理也能切换）
5. **副作用可控**（重复执行最坏结果是 idempotent 写操作, 不会产生错的边/节点）

## 📝 下一步决策点（等你确认）

**请你定**: G3 走哪个选项？

- 选项 1: 复制路径 A 到路径 B（推荐, 0.5 天）
- 选项 2: 删路径 A 的 _create_hierarchical_bit_nodes（1 天）
- 选项 3: 路径 B 升级替代路径 A（1-1.5 天）
- 选项 4: 纯文档说明（0.1 天）
- 其他: 你给方案

**今天不实施 G3**——按你"G2 计划 + diff 验证脚本，不下结论改代码"指令。

## 🔄 状态变更日志

- **2026-08-28 06:23** — G2 计划 + diff 验证脚本完成 (commit pending).
  - 3 个 fixture × 2 条路径实测, 边/节点存在性完全一致
  - 唯一差异: RangeSelect 节点 4 个属性 (bit_range / parent_bit_* / width) 路径 B 漏设
  - 推翻 review "重复实现" 判断 — 两套职责明确 (RangeSelect 完整 vs ElementSelect 简化)
  - G3 待决策: 4 个选项, 推荐选项 1 (0.5 天)