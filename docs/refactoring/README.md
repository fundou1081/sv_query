# sv_query Refactoring Plans (2026-06-26)

> 系统化代码 bad smell 审计 + 拆解计划
> 详细分析见各文档

## 📋 文档列表

| 文档 | 内容 | 优先级 |
|------|------|--------|
| [2026-06-26_bad_smell_audit.md](2026-06-26_bad_smell_audit.md) | Bad smell 完整审计 (5 大类, 18 god class, 40+ long method) | 背景 |
| [2026-06-26_refactoring_roadmap.md](2026-06-26_refactoring_roadmap.md) | 3 块并行拆解 roadmap (C / B / A) | 总览 |
| [2026-06-26_extract_refactoring.md](2026-06-26_extract_refactoring.md) | **B. DriverExtractor.extract() 817 行拆 30 行详细 plan** | ⭐ 当前焦点 |

## 🎯 决策记录 (2026-06-26)

### 选 B 不选 C 作为先做

**B** (DriverExtractor.extract() 拆) vs **C** (P0 helper 抽取):
- B 改善 -800 行 (817→30), C 改善 -50 行 (净)
- B 解决 god method (阻碍 debug), C 解决重复代码 (polish)
- B 风险 🟢 LOW, C 风险 🟢 LOW
- B 收益高 C **16 倍**

**C 降为 P1, B 优先做**. (注: 之前 discussion assistant 写的 plan 保持 C 优先, 跟方浩 2026-06-26 决策冲突. **以本 README 决策为准**.)

## 📅 执行顺序 (修订)

1. **B. DriverExtractor.extract() 拆 (1-2 周)** ← 当前先做
2. **C. P0 helper 抽取 (2-3 天)** ← B 完成后做
3. **A. SignalExpressionVisitor 拆分 (2-3 周)** ← 长期

总预计: 4-6 周

## 🛠️ 状态

- [ ] **B-Phase 1-2**: port_nodes + var_nodes (Day 1-2, 未开始)
- [ ] B-Phase 3-4: net_aliases + net_decls (Day 3-4)
- [ ] B-Phase 5: assignments (Day 5-7)
- [ ] B-Phase 6: always_blocks (Day 8-9)
- [ ] B-Phase 7: post_process (Day 10)
- [ ] 同步拆 _handle_invocation 462 行 (Day 11-12)
- [ ] TraceNode/Edge helper 抽取 (Day 13-14)
- [ ] C: P0 helper 抽取
- [ ] A: SignalExpressionVisitor 拆分

## 🔗 相关资源

- `src/trace/core/driver_extractor.py` (817 行 extract)
- `src/trace/core/visitors/signal_expression_visitor.py` (7312 行 god class)
- `src/trace/core/_safe_attrs.py` (未来, C 块 helper)
- `docs/ARCHITECTURE_REFACTOR_IMPACT.md` (历史 refactor 记录)
