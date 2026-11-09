# Iteration 449: Discipline remediation（audit BLOCK）

**状态**: ✅
**日期**: 2026-11-09

## 来源

Worker independent discipline audit verdict = BLOCK。F1–F14 全部处理。

## 结果

- regex 违规清零；
- FIFO 默认不可见，所有 consumer 统一 visibility；
- verify/dataflow/fanin/undirected paths 不再跨 FIFO；
- solve/dist 改 semantic syntax AST；
- unknown_kind 显式；
- constraint dict 单实现；
- warning 用真实 ModuleDeclarationSyntax；
- task file/overview 补齐；
- 新增 visibility/warning 回归。

## 剩余

F15 check_crap 只 diff worktree，post-commit 无法证明 commit range（工具范围问题）。
