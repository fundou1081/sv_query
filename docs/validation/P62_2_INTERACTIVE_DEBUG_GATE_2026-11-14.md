# P62.2 interactive debug gate assessment

**日期**: 2026-11-14
**状态**: ✅ 已完成（gate no-go，不开发）

## 1. 设计 gate

来源：[structural_review_plan_2026-11-02](../architecture/structural_review_plan_2026-11-02.md) §7.2。

启动交互式 debug 必须同时满足：

1. P60 子图 API 在真实 review 中稳定使用；
2. P61 至少产出一组真实 typo/symmetry finding；
3. 静态 artifact 被证明降低 review 时间；
4. 有长驻 session/API 方案，不每次点击重建图。

## 2. 当前证据

| 条件 | 状态 | 证据 |
|---|---|---|
| 1. P60 子图稳定 | 部分 | P60 实现 + tests；没有真实 review 使用时长/稳定性记录 |
| 2. P61 真实 finding | 部分 | P61.2 finding schema + tests；未证明在真实项目 review 中产出并被采用 |
| 3. 静态 artifact 降低 review 时间 | **未满足** | P62.1 SVG/HTML 已实现，但没有 before/after review-time 测量 |
| 4. 长驻 session/API | **未满足** | 没有 session 对象/API；现有 P74/P79 是 agent 多轮 query pilot |

## 3. 决策

按 gate 收口：**不开发交互式 debug UI/REPL**。

P62.2 的 gate 评估结论是 **no-go**，原因：

```text
缺少条件 3/4 的可验证证据：静态 artifact review-time 测量 + 长驻 session/API。
```

不是“做不了”，而是现在做会违反产品方向中“最后做，且有 gate”的约束。

## 4. 重新评估需要的最小证据

- 一次真实 review：有 finding、生成 artifact、记录 review time；
- 一个长驻 session/API 设计：一次建图，多轮 expand/evidence，不重复 parse；
- 明确 session 生命周期和缓存失效策略。

在这些证据出现前，不创建 `review debug` 命令。
