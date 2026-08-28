# 架构决策: BitSelect 提取改用 pyslang Semantic API (替代 regex)

> **决策 ID**: ARCH-2026-08-28-bitselect-semantic-api
> **关联**: [ARCHITECTURE_TODOLIST #2](../ARCHITECTURE_TODOLIST.md) / [BITSELECT_HANDLER_G2_PLAN.md](../BITSELECT_HANDLER_G2_PLAN.md)
> **迭代记录**: [iter_035](../task_tree/iterations/iter_035_bitselect_semantic_api_decision.md)

---

## 时间

- **2026-08-28 06:36 GMT+8** — 方豆首次指示 "走 g3 的 3" (前一 session)
- **2026-08-28 07:46 GMT+8** — 方豆再次确认 "选择 semantic api", 本决策正式归档

---

## 遇到的问题

`ARCHITECTURE_REVIEW_2026-08-27.md` §三.2 标记 "BitSelectHandler vs graph_builder 两套并行实现"。
G2 实测 (commit `78eb602` / `49b475c`) 推翻了 "重复实现" 的判断, 但暴露了**更严重的问题**:

1. **表层 bug**: 路径 B (`graph_builder._create_hierarchical_bit_nodes`) 漏设 RangeSelect 4 个属性
   (`bit_range` / `parent_bit_start` / `parent_bit_end` / `width`)
2. **🔴 真正的架构债**: **两套实现都完全不用 pyslang API, 全部靠 regex 反推节点 ID 字符串**
   - 路径 A: `r"^([^\[]+)\[(\d+):(\d+)\]$"`
   - 路径 B: `re.sub(r"\[.*?\]", "", child_id)`
3. **架构方向冲突**: 这与项目 2026-08-15 确立的 **"pure semantic API — 不允许 fallback 到 string"**
   (见 `AGENTS.md` 历史背景) 直接矛盾

---

## 考虑的方案

| 选项 | 做法 | 成本 | 风险 | 是否治本 |
|---|---|---|---|---|
| 1 | 复制路径 A 的属性设置到路径 B | 0.5 天 | 🟢 低 | ❌ 仍是 regex |
| 2 | 删路径 A 的 `_create_hierarchical_bit_nodes` | 1 天 | 🟡 中 | ❌ 仍是 regex |
| **3** | **用 pyslang API 替代 regex** | **1-2 天** | 🟡 中 | ✅ **治本** |
| 4 | 纯文档说明边界 | 0.1 天 | 🟢 低 | ❌ 不修 bug |
| 5 | 选项 1 + 新建 #8 修 generate-for 位选 | 1.5+ 天 | 🟢 低 | ❌ 仍是 regex |

**上一轮 AI 助手推荐选项 5**（成本最低、风险最小）。

---

## 决策结果

### ✅ 采纳 **选项 3 — 用 pyslang Semantic API 替代 regex**

方豆两次明确指示 (06:36 "走 g3 的 3" / 07:46 "选择 semantic api")。

**理由**:
1. **唯一与项目既定架构方向一致的选项** — 选项 1/2/5 都把 regex 债留在原地, 属于
   `AGENTS.md` "修 bug 要修根因" 表格里的 **症状层 / 行为层**, 而非根因层
2. **regex 反推节点 ID 是结构信息字符串化** — 违反 "结构化数据优于字符串" 原则
3. 与 todolist **#7 (迁 pyslang 11.0 native API)** 呼应, 可作为 #7 的前置验证

---

## 利弊权衡

### 接受的代价

- **成本最高** (1-2 天 vs 选项 1 的 0.5 天)
- **风险中等** — pyslang 11.0 AST API 不完全熟悉, 需要探索
- **放弃了"最快修好表层 bug"** — 选项 1 半天就能让 RangeSelect 4 属性回来

### 换来的收益

- 根除 regex 脆弱性, 同类 bug **不会再出现**
- 与 "pure semantic API" 架构方向一致, 不再累积矛盾
- 为 #7 pyslang native API 迁移铺路

### 明确不在本决策范围

- **#8 generate-for 内动态位选** (`acc[i]` 不产生 BIT_SELECT 边) — 属于 generate 展开 /
  driver_extractor 范围, 单独立项

---

## 关键技术事实 (实测确认)

- `pyslang 11.0 RangeSelectExpression`: `.left.value` (msb) / `.right.value` (lsb)
- `pyslang 11.0 ElementSelectExpression`: `.selector.value` (index)
- `root.visit(callback)` 是 11.0 真实遍历 API, callback 返回 `True`/`False` 控制是否深入
- `node.kind == ExpressionKind.RangeSelect / ElementSelect`
- parameter 位选 (`data[W-1:0]`) 经 `eval(EvalContext)` 可拿到真实整数

---

## 实施状态 (2026-08-28 07:46)

⚠️ **未完成, 未提交** — 详见 iter_035。

已有**未提交**的实现 (前一 session 按 06:36 指示所做):
- `src/trace/core/extractors/_common.py` — 新增 `BitSelectHit` / `iter_bit_selects()` /
  `_PyslangSelectWalker` (+492 行)
- `src/trace/core/graph_builder.py` — `_create_hierarchical_bit_nodes` 改用 helper (+145 行)
- `sim/tests/unit/test_common_bit_selects.py` — 新增单测 (未跟踪)

**遗留问题 (需后续处理)**:
1. 🔴 **`_common.py:441` 存在 silent fallback** — `if not _HAS_PYSLANG: return  # 退化: 让调用方走 regex 老路径`,
   违反 `AGENTS.md` 核心纪律 #2 "禁止 fallback"。应改为显式报错或 sentinel。
2. 🔴 **路径 A (`bit_select_handler.py`) 尚未改造** — 目前只改了路径 B, regex 债只清了一半
3. ⚠️ `graph_builder.py:442` 仍保留 `import re`
