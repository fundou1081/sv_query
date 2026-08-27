# BitSelectHandler vs graph_builder 实现统一 G2 计划

> **创建日期**: 2026-08-28 06:23
> **维护人**: QClaw Agent + 方豆
> **状态**: 🟡 in_progress (G2 计划 + diff 验证脚本完成, G3 待决策)
> **来源**: [ARCHITECTURE_REVIEW_2026-08-27.md §三.2](ARCHITECTURE_REVIEW_2026-08-27.md) + 实测数据
> **关联**: [ARCHITECTURE_TODOLIST #2](ARCHITECTURE_TODOLIST.md)

## 📋 背景

review §三.2 标记 "🔴 重复实现: BitSelectHandler vs graph_builder._create_hierarchical_bit_nodes 两套并行, 行为可能不一致"。

**但 review 是基于"代码位置 + 函数名"的粗略判断**——没实测。本 G2 计划通过实测发现真实情况。

## 🔍 实测数据（2026-08-28 06:23 + 06:33, commit `pending`）

**测试脚本**: `sim/tests/integration/test_bitselect_handler_diff.py` (8 KB+, 7 个 fixture × 2 条路径)

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

### 🆕 Fixture 4 (06:33): Parameter 位选 (`data[W-1:0]`)
```
路径 A: 节点 4, BIT_SELECT 边 1, 位选节点 1
路径 B: 节点 4, BIT_SELECT 边 1, 位选节点 1
边数差: 0
仅 RangeSelect 节点属性差异 (1 个):
  top.data[7:0]: bit_range A='[7:0]' B=None ...
注: pyslang elaboration 时把 W-1 折叠为 7, 节点 ID 同 Fixture 1
```

### 🆕 Fixture 5 (06:33): Generate-for 动态位选 (`acc[i]`, `acc[i+1]`)
```
路径 A: 节点 3, BIT_SELECT 边 0, 位选节点 0
路径 B: 节点 3, BIT_SELECT 边 0, 位选节点 0
边数差: 0
🔴 严重: 动态位选根本不产生 BIT_SELECT 边 (pyslang 展开 generate 后
节点 ID 是 'top.gen_accum[0].acc[0]', ElementSelect [0] 不被视为位选)
```

### 🆕 Fixture 6 (06:33): Nested 位选 (`data[3:0][1:0]`)
```
路径 A: ❌ pyslang 编译失败 - 'cannot chain select after range select'
路径 B: — (同上)
注: SV 规范本身不允许这种写法, 测试不作为边界 case 参考
```

### 🆕 Fixture 7 (06:33): Struct 字段位选 (`pkt.addr[3:0]`)
```
路径 A: 节点 5, BIT_SELECT 边 3, 位选节点 1
路径 B: 节点 5, BIT_SELECT 边 3, 位选节点 1
边数差: 0
仅 RangeSelect 节点属性差异 (1 个):
  top.pkt.addr[3:0]: bit_range A='[3:0]' B=None ...
注: regex r'^[^\[]+' 能匹配 'pkt.addr' 前缀, 正常处理
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

### 🆕 06:33 边界测试关键修正

之前担心"regex 处理不了多种位选形式"——**实测下来不成立**：

| 位选形式 | 是否产生 BIT_SELECT 边 | 是否被 regex 漏掉 |
|---|---|---|
| `data[3:0]` (RangeSelect 整数) | ✅ 1 条 | ⚠️ 路径 B 漏 4 属性 |
| `data[0]` (ElementSelect 整数) | ✅ 1 条 | ✅ OK（路径 A/B 一致） |
| `data[W-1:0]` (RangeSelect parameter) | ✅ 1 条（同 `[7:0]`） | ⚠️ 路径 B 漏 4 属性 |
| `data[i]` (ElementSelect generate 内) | ❌ 0 条 | ℹ️ **根本不是位选节点问题**，是 generate 展开问题 |
| `data[i+1]` (ElementSelect 表达式) | ❌ 0 条 | ℹ️ 同上 |
| `pkt.addr[3:0]` (Struct 字段) | ✅ 1 条 | ⚠️ 路径 B 漏 4 属性 |
| `data[3:0][1:0]` (嵌套) | — | SV 非法，pyslang 编译失败 |

**修正结论**:
- regex 实际**比想象的鲁棒**——pyslang elaboration 把 parameter 折叠、struct 字段前缀被 regex 捕获
- **真正的额外 bug**: generate-for 内动态位选**根本不产生 BIT_SELECT 边**——这是**更大的架构 gap**，但**不在 #2 BitSelectHandler 范围内**（属于 generate 展开或 driver_extractor 的问题）
- 建议作为新 todolist 项 **#8 修 generate-for 内动态位选**

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
| **pyslang API 使用** | ❌ **完全不用**, 全 regex | ❌ **完全不用**, 全 regex |

🔴 **关键架构问题 (06:33 发现)**: 两套实现**都用 regex 反推节点 ID 字符串**, 都没用 pyslang 11.0 native API (`RangeSelect.left.value` / `RangeSelect.right.value` 等结构化属性)。这是**比"两套并行"更严重的架构债**——应该用 `isinstance(node.expr, RangeSelect)` 等结构化查询替代 regex。

## 🛠️ G3 实施建议（待决策）

### 选项 1: 把路径 A 的 RangeSelect 处理**搬**到路径 B（最简）

- **做法**: `graph_builder._create_hierarchical_bit_nodes` 内复制路径 A 的 RangeSelect 分支
- **影响**: 路径 B 用户也能得到完整 RangeSelect 属性
- **副作用**: 路径 A 和路径 B 都做 RangeSelect 处理（如果走 unified_tracer，会重复执行）
- **风险**: 🟢 低（只是复制代码 + 加 regex 严格匹配 RangeSelect）
- **工作量**: 0.5 天
- **注意**: 仍然是 regex 方案, 不解决"没用 pyslang API"架构债

### 选项 2: 删路径 A 的 `_create_hierarchical_bit_nodes`，让路径 B 做全部

- **做法**: 路径 A 只保留 `Phase 1: _extract_all_widths` + `Phase 3: _scan_constraint_bit_selects`；`_create_hierarchical_bit_nodes` 完全移到路径 B
- **影响**: 路径 B 同时处理 RangeSelect + ElementSelect，约束扫描仍由路径 A 单独做
- **副作用**: unified_tracer 需要跳过路径 A 的 RangeSelect 处理（避免重复）
- **风险**: 🟡 中（需要改 unified_tracer 的 call sequence + 验证 constraint 扫描顺序依赖）
- **工作量**: 1 天
- **注意**: 仍然是 regex 方案

### 选项 3: 用 pyslang API 替代 regex（治本）

- **做法**: 两套实现都改用 `isinstance(node.expr, RangeSelect)` 等结构化查询替代 regex
- **影响**: 根本解决"regex 反推脆弱性"架构债
- **副作用**: 需要研究 pyslang 11.0 AST API（不完全熟悉, 需要探索）
- **风险**: 🟡 中（pyslang API 不熟, 可能踩坑）
- **工作量**: 1-2 天
- **额外收益**: 跟 todolist #7 pyslang native API 重构呼应, 可作为 #7 的前置

### 选项 4: 不动代码，只在文档里说明两套的边界

- **做法**: 在 BitSelectHandler + graph_builder docstring 加注释 "这条路径不处理 RangeSelect, 走 BitSelectHandler"
- **影响**: 用户走路径 B 时知道 RangeSelect 属性缺失
- **副作用**: 没真正修复 bug, 只是让用户知情
- **风险**: 🟢 低（纯文档）
- **工作量**: 0.1 天

### 🆕 选项 5 (06:33 新增): #2 选项 1 + 新建 #8 修 generate-for 动态位选

- **#2 做选项 1** (0.5 天): 修 RangeSelect 4 属性漏设
- **#8 新建** (1+ 天): 修 generate-for 内动态位选 (`acc[i]`, `acc[i+1]`) 不产生 BIT_SELECT 边
- **理由**: 两个 bug 范围不同, #8 不在 #2 BitSelectHandler 范围内（属于 generate 展开或 driver_extractor 问题）
- **工作量**: #2 0.5 天 + #8 1+ 天 = 总 1.5+ 天

### 推荐: 选项 5

理由:
1. **修两个独立 bug**（#2 RangeSelect 4 属性 + #8 generate-for 位选）
2. **选项 1 仍修主 bug**（低风险, 0.5 天）
3. **#8 单独建项**，避免在 #2 里跨范围改 driver_extractor 或 generate 展开逻辑
4. **保留未来用 pyslang API 替代 regex 的机会**（选项 3 作为后续 #9 单独评估）

## 📝 下一步决策点（等你确认）

**请你定**: G3 走哪个选项？

- 选项 1: 复制路径 A 到路径 B（0.5 天, 仅修 #2）
- 选项 2: 删路径 A 的 _create_hierarchical_bit_nodes（1 天）
- 选项 3: 用 pyslang API 替代 regex（1-2 天, 治本）
- 选项 4: 纯文档说明（0.1 天）
- **选项 5: 选项 1 + 新建 #8 修 generate-for 动态位选**（推荐, #2 0.5 天 + #8 1+ 天）
- 其他: 你给方案

**今天不实施 G3**——按你"G2 计划 + diff 验证脚本，不下结论改代码"指令。

## 🔄 状态变更日志

- **2026-08-28 06:23** — G2 计划 + diff 验证脚本完成 (commit `78eb602`).
  - 3 个 fixture × 2 条路径实测, 边/节点存在性完全一致
  - 唯一差异: RangeSelect 节点 4 个属性 (bit_range / parent_bit_* / width) 路径 B 漏设
  - 推翻 review "重复实现" 判断 — 两套职责明确 (RangeSelect 完整 vs ElementSelect 简化)
  - G3 待决策: 4 个选项, 推荐选项 1 (0.5 天)
- **2026-08-28 06:33** — 加 4 个边界 fixture 实测 (commit pending).
  - Parameter 位选 (`data[W-1:0]`): pyslang elaboration 折叠 W-1→7, 节点 ID 同 `[7:0]`, 行为同 Fixture 1
  - Generate-for 动态位选 (`acc[i]`, `acc[i+1]`): 🔴 **不产生 BIT_SELECT 边**——pyslang 完全展开 generate 后, 节点 ID 是 `acc[0]` 这种 ElementSelect 形式, 两套实现都不视为位选
  - Nested 位选 (`data[3:0][1:0]`): SV 非法, pyslang 编译失败
  - Struct 字段位选 (`pkt.addr[3:0]`): regex `[^\[]+` 能匹配 `pkt.addr` 前缀, 正常处理
  - 修正结论: regex 实际**比想象的鲁棒**; 真实额外 bug 是 generate-for 位选, 不在 #2 范围
  - G3 选项更新: 增选项 5（推荐, #2 选项 1 + 新建 #8）
  - **新架构债发现**: 两套实现**完全不用 pyslang API**, 全 regex——这是比"两套并行"更严重的债, 建议未来选项 3 单独评估