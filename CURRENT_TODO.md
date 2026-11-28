# CURRENT_TODO — 当前正在做的事

> **计划源**: 代码修改计划以 [PLAN.md](PLAN.md) 为**全局唯一真相源**；本文件只记录"此刻"的上下文。
> **产品方向**: [product_direction_2026-10-31](docs/architecture/product_direction_2026-10-31.md) — agent RTL 查询 + 客观校验；动态值由外部波形工具提供。
> **状态**: 0.3.9 已发布；worker 架构复审发现 3 个 pre-existing P1，进入 P199/0.3.10 fast-follow。
> **最后更新**: 2026-11-28 (0.3.9 architecture review)

---

## 🎯 当前计划（以 [PLAN.md](PLAN.md) 为准）

- **当前 item**: **P199.1 data-edge authority** `<进行中>`
- **发布**: 0.3.9 已上 PyPI/GitHub；0.3.10 为 P1 修复 fast-follow，未发布。
- **架构复审**: [P199_ARCH_REVIEW_2026-11-28.md](docs/validation/P199_ARCH_REVIEW_2026-11-28.md)
- **worker 原始报告**: [2026-11-28_fe379c03.md](docs/validation/reviews/2026-11-28_fe379c03.md)
- **未完成叶子**:
  - P199.1–P199.7（0.3.10 内部工作）
  - P194.5d（blocked，外部 benchmark）
  - P193.10（外部 trial users）

### 0.3.10 顺序

```text
1. P199.1 edge authority（P1）
2. P199.2 evidence authority（P1）
3. P199.3 semantic literal classification（P1）
4. P199.4 session contract
5. P199.5/6 identity + snapshot metadata
6. P199.7 tri-state
7. P199.0 release gate + independent review
```

---

## 📌 当前真实基线

```text
canonical:  3410 passed / 0 failed / 123 deferred / 0 unexecuted
opensource: 112 passed / 11 skipped / 0 failed
```

- 123 deferred = opensource suite（112 passed + 11 skipped），不是 123 unexecuted；
- 11 skip 中 2 个是 SPI snapshot 外部 fixture 缺失；
- 计数真相源：[docs/INDEX.md](docs/INDEX.md#-当前基线-单一真相源--计数只写在这里)。

---

## 🚨 0.3.9 已知 P1（0.3.10 必修）

```text
W039-01  drivers --depth 1 / verify_driver 接受 CLOCK 边
W039-02  trace evidence is_verified 可以落在 condition line
W039-03  verification 用 ID regex 判 literal -> picorv32 36 个假 violation
```

Claims 状态：C-87 / C-88 / C-89 `known-broken`；Known Limitations §3.30。

### 0.3.9 已知 P2

```text
W039-04 snapshot evidence 选 CLOCK 边
W039-05 condition 缺失被写成 false/unconditional
W039-06 session `arguments` contract mismatch
W039-07 session verify_consistency 只支持 connection
W039-08 ports module-name 与 instance-path namespace 不一致
W039-09 snapshot edge_count raw vs canonical 不一致
W039-10 snapshot save 文件类型错误无结构化 JSON
```

---

## 🧭 产品边界

```text
主线：agent RTL 查询 + 客观 verify
```

- 39 core + 6 exp（exp 是 hidden 直接命令，不是 `svq exp` 命名空间）；
- coverage generation / `coverage.gen` 暂不推进；若重启，以 sv_query 为基底单开项目；
- RTL typo detection / ranking 属于独立项目 `rtl_typo_checker`；
- interactive debug（P62.2）no-go，不开发 UI/REPL；
- 外部 benchmark / 真实用户验证仍由 P194.5d / P193.10 承担，未完成。

## 🚫 不要再做的事

- 不要回到 `svq exp` 统一入口（已退役）；
- 不要用旧 `visualize` / `cdc` / `timing` / `sva` / `risk` 作为当前示例；
- 不要把 123 deferred 写成 unexecuted；
- 不要在未标定的 `trace impact` 风险分上做绝对风险声明；
- 不要把 `drivers --depth 1` 或 `is_verified` 在 W039-01/02 修复前当作最终权威。
