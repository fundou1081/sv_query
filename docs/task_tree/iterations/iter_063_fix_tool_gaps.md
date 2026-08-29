# Iteration 063: 修复工具缺口 #36/#37/#39-immediate

**Metadata**:
- **Iteration #**: 063
- **Task Tree Level**: L2
- **Parent Task**: iter_062 发现的工具缺口修复 (EXTRACTION_COVERAGE #34-#40)
- **Created**: 2026-08-29 GMT+8
- **Author**: AI 助手
- **Outcome**: ⚠️ 部分完成 (修 3 项, 3 项 pyslang 限制, 1 项设计约束, 1 项无消费者)

## 🎯 本次目标

方豆 "修发现的工具缺口" — EXTRACTION_COVERAGE #34-#40 (iter_062 写测试时发现)。

## 📊 当前状态 / 预期结果

7 个缺口, 逐个核实可修性后修复。预期: 修可修的, pyslang 限制如实记录。

## 🔬 实际结果

### ✅ 已修复 (3 项)

**#36 covergroup iff 建模**: CoverpointInfo 加 `iff` 字段 (CoverCrossInfo 已有),
_parse_coverpoint/_parse_cover_cross 从 syntax.iff 提取 (去 "iff" 前缀)。
实测: `coverpoint data iff (enable)` → iff='enable'; `cross addr, mode iff (reset==0)` → iff='reset == 0'。

**#37 wildcard/transition bins**: BinsInfo 加 `bin_type` 字段。
- wildcard: keyword 前的独立修饰 token (keyword 本身不含), 用 syntax 完整文本
  判断 "wildcard" 位于 bins 关键字之前 (坑: 直接查 keyword 抓不到)
- transition: initializer 含 "=>" (如 `(0 => 1 => 2)`)
实测: wildcard read_op → 'wildcard'; trans → 'transition'; 普通 bins → ''。

**#39 immediate assertion**: sva_extractor 新增 _parse_immediate_assertion +
_collect_immediate_assertions。
- 形态 1: 命名 `immediate_assert: assert (...)` → 语义 StatementBlock.syntax =
  ImmediateAssertionStatementSyntax (keyword/expr/action)
- 形态 2: 块内 assume/cover → ProceduralBlockSyntax.statement =
  BlockStatementSyntax.items 递归收集
- else 消息提取 ($error("mismatch")) + 去重 (两路径重复)
实测: assert(kind/message/signals) + assume + cover 全提取。

### 🚫 pyslang 限制 (3 项, 无法在 sv_query 修)

- **#34 not inside**: `val not inside {...}` → constraints 属性返回
  **InvalidConstraint** (pyslang 语义层不解析 not inside)
- **#38 参数化 covergroup**: bins 内引用 covergroup 参数编译失败; 参数化实例化
  `cg #(16)` 报 "not a generic class type"
- **#39 expect**: expect 关键字在 pyslang 语义层**丢失** — expect property 呈现
  为空的 `property (p_req);` (与普通 property 引用不可区分)

### 🚫 设计约束 (1 项, 不改既定设计)

- **#40 数组索引边**: `_common.py:474` "ElementSelect 仅当 selector 是
  IntegerLiteral 时产出" — 动态索引 mem[idx] 有意不产出节点。实测字面索引
  `mem[0] = a` / `data[3:0]` 都正常; 动态索引是设计选择 (改会影响既定行为)。

### ⚪ 无消费者 (1 项, 不造死字段)

- **#35 soft/:/ 区分**: dist :/ 可提取 (DistWeight.Kind = PerValue/PerRange),
  但当前约束分析不消费权重类型; soft 本身是 pyslang 限制 (解析成普通
  Expression, soft 修饰丢失)。

### 测试更新

- test_covergroup_advanced.py: iff/bin_type 断言加强 (修复证明)
- test_sva_advanced.py: immediate 断言改为"提取成功"; expect 记录限制

### 回归

- regression 770 passed + 2 failed (均 pre-existing) / unit 子集 43 passed /
  ruff 全过 — 零新回归

## 💡 关键发现 / 关键技术 / 决策

1. **"修缺口"先核实可修性**: 7 个缺口里 3 个是 pyslang 限制 (not inside /
   参数化 covergroup / expect), 1 个是设计约束 (动态索引), 1 个无消费者 —
   **只有 3 个真正可修**。逐个 probe pyslang 语义层呈现是前提。
2. **pyslang 语义层丢修饰的规律**: soft (丢 soft)、expect (丢 expect 关键字)、
   not inside (InvalidConstraint) — pyslang 对"修饰类"语法的语义呈现不完整。
   这类缺口 sv_query 无法从语义层恢复 (除非回退 syntax 层, 违反铁律1)。
3. **syntax 层提取的坑**: wildcard 修饰在 keyword 前的独立 token (keyword 本身
   不含); immediate assertion 有 StatementBlock 与 BlockStatementSyntax.items
   两条路径 (需去重) — probe 属性结构比猜快。
