# CURRENT_TODO — 当前正在做的事

> **计划源**: 代码修改计划以 [PLAN.md](PLAN.md) 为**全局唯一真相源**；本文件只记录"此刻"的上下文。
> **产品方向**: [product_direction_2026-10-31](docs/architecture/product_direction_2026-10-31.md) — agent RTL 查询 + 客观校验；动态值由外部波形工具提供。
> **状态**: P197.3 filelist refresh failure + load_graph guard。
> **最后更新**: 2026-11-23 (P197 code-smell audit)

---

## 🎯 当前计划（以 [PLAN.md](PLAN.md) 为准）

- **当前 item**: **P197.3 filelist refresh failure + load_graph capability guard** `<进行中>`
  - P195/P196 全部完成；0.3.6 已发布（release-check -> build -> publish）
  - P194.2f 已解除阻塞（P196.1/P196.2 已完成）
  - 独立复核报告: `/tmp/p195_final_review.md`
  - 未完成叶子：P197.3–P197.12、P194.5f–P194.5h、P194.6、P194.7、P193.10


## 📌 当前真实基线

```text
canonical:  3232 passed / 0 failed / 123 deferred / 0 unexecuted
opensource: 112 passed / 11 skipped / 0 failed
```

- 123 deferred = opensource suite（112 passed + 11 skipped），不是 123 unexecuted；
- 11 skip 中 2 个是 SPI snapshot 外部 fixture 缺失；

- 计数真相源：[docs/INDEX.md](docs/INDEX.md#-当前基线-单一真相源--计数只写在这里)。

## 🧭 产品边界

```text
主线：agent RTL 查询 + 客观 verify
```

- 39 core + 6 exp（exp 是 hidden 直接命令，不是 `svq exp` 命名空间）；
- coverage generation / `coverage.gen` 暂不推进；若重启，以 sv_query 为基底单开项目；
- RTL typo detection / ranking 属于独立项目 `rtl_typo_checker`（当前未依赖 sv_query）；sv_query 只保留客观 structural 检查；
- interactive debug（P62.2）gate 评估为 no-go，不开发 UI/REPL。

## ✅ P173 清理结果

1. CLI/exp truth：`trace impact` 已隐藏；CLI_SURFACE/feature map/EXP_NAMESPACE 已对齐；
2. 状态文档：CURRENT_TODO/private archive/PLAN/契约已对齐；
3. 证据：退役 zombie/coverage-suggest tests；canonical 3027；
4. coverage POC：conftest 改为 lazy import；公开示例已改写/归档。

## 🚫 不要再做的事

- 不要回到 `svq exp` 统一入口（已退役）；
- 不要用旧 `visualize` / `cdc` / `timing` / `sva` / `risk` 作为当前示例；
- 不要把 123 deferred 写成 unexecuted；
- 不要在未标定的 `trace impact` 风险分上做绝对风险声明。
