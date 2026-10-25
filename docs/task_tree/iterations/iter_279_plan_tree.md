# Iteration 279: 全局唯一计划树（PLAN.md）+ 流程强制

**Metadata**:
- **Iteration #**: 279
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-25 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "用一个全局唯一的计划树来管理目前以及将来所有的代码修改计划"）
- **Outcome**: ✅ 计划树建立 + 机械校验 + AGENTS/WORKFLOW/INDEX 联动

## 🎯 目标

把"接下来做什么、做到哪"从散落的对话/文档里收口到**一个全局唯一的计划树**，
并写进流程：**先更新计划文档，再开工；开工前核对上一轮状态；按需扩展子计划**。

## 🔧 交付物

| # | 文件 | 内容 |
|---|---|---|
| 1 | [`PLAN.md`](../../../PLAN.md)（根目录） | 唯一计划树：`current item` + 4 组计划项 + 已完成归档 |
| 2 | `tools/check_plan.py` | 机械校验：current 一致 / id 唯一 / 子项有父 / 状态词合法 / 叶子至多一个进行中 |
| 3 | `AGENTS.md` v2.2 | §0 恢复上下文把 PLAN.md 提到第 2 位 + 核对上一轮状态；§2 开工先登记计划；§3 新增 check_plan |
| 4 | `docs/dev/WORKFLOW.md` | §0.1 设施表新增"计划树"（唯一计划源）；§1.1 新增第 0 步；§1.3 收尾表新增 PLAN.md |
| 5 | `CURRENT_TODO.md` | 顶部声明：计划以 PLAN.md 为准，本文件只记"此刻"上下文 |

## 📐 计划树格式（校验器强制）

```
current item : P0.1 图快照基线工具 <待做>

P0 建图层与查询层的结构化拆分 <进行中>
-- P0.1 图快照基线工具：… <待做>
-- P0.2 拆 _trace_drivers_recursive… <待做>
```

- 行格式：`[-- ]P<数字>[.<数字>…] <内容> <状态>`
- 状态词：`待做` / `进行中` / `已完成` / `阻塞` / `放弃`
- id 全局唯一；子项父项必须是顶层项
- 父项可整体标 `进行中`（组在做）；**叶子项**最多一个 `进行中`，且 current 标 `进行中` 时必须是它

## 📋 初始计划（来自 iter_278 审计）

| id | 项 | 依据 |
|---|---|---|
| P0.1 | 图快照基线工具 | 拆 P0.2 前必须能证明"行为没变" |
| P0.2 | 拆 `_trace_drivers_recursive`（343 行，6 类规则） | 唯一"改一处怕碰另一处"的地方 |
| P0.3 | GraphBuilder 6 个后处理 pass 改声明式 pipeline | pass 顺序是隐式约定 |
| P1.1 / P1.2 | `visualize module` 换实例级边推导 → 删 MIG 映射 | 视图层最后一处双命名空间残留 |
| P2.1 | 位选/interface/inout/class-struct 边缘补测 | 主干稳、边缘薄 |
| P3.x | 长期 backlog（巨型私有方法 / 缓存过期 / exp 想法） | 不排期 |

## ✅ 验证

```bash
python3 tools/check_plan.py     # ✅ PLAN.md 通过 (17 个计划项)
```

## 💡 说明

- 计划树**只管计划**：迭代历史仍进 `docs/task_tree/iterations/`，避免计划文件变成流水账。
- "已完成"区只保留最近几项，便于**核查上一轮**；更早历史查 iterations + git log。
- 新工作一律**扩展子项**（如 `P0.4`），不改旧项语义 —— 保证 id 可长期引用。
