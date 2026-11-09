# Iteration 448: P136.5 solve/dist

**状态**: ✅
**日期**: 2026-11-09

## 实现

- solve…before 从 syntax 解析，CONSTRAINT_SOLVE extra + HAS_BEFORE；
- solve 不加入 block 的值 CONSTRAINS（旧契约保持）；
- dist 文本存入 CONSTRAINT_EXPR extra；
- trace constraints / class relations schema 输出 solve_before + dist。

## 验证

solve/dist 2 tests；constraint derivative 仍锁定“solve 非值约束”；schema contract 通过。

## 边界

solve 只输出 before；dist 是文本，不做权重计算。
