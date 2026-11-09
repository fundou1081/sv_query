# Discipline audit remediation（2026-11-09）

**来源**: worker independent audit（BLOCK）
**结果**: F1–F15 已处理；F2/F3–F6 的自动 FIFO 部分由 P138 整体删除；F12 O(E²) nit 保留

---

## 1. 原始 blocker

| ID | 问题 | 处理 |
|---|---|---|
| F1 | solve/dist regex，`check_semantic_regex` 失败 | 改为 semantic syntax AST；门禁恢复 |
| F2 | FIFO 边无条件创建 | 改为 `include_fifo_edges` 显式 build 选项 |
| F3 | verify 跨 FIFO 仍 verified | 改用 PathResolver 默认过滤 |
| F4 | dataflow 跨 FIFO 且 latency=0 | 默认无 FIFO 边 + path filter |
| F5 | undirected paths 走 FIFO | 统一 visible_neighbors（successors+predecessors） |
| F6 | fanin 把 FIFO 当驱动递归 | 显式跳过 FIFO |
| F7 | unknown_kind 从 reason 猜 | `_claim_result` 显式传入 |
| F8 | tb-join 第三份 constraint dict | 统一 `constraints.constraint_dict` |
| F9 | P135/P136 完成证据不足、task/overview 缺失 | 补 task 文件、overview 行；复测后保留完成 |
| F10 | source scan 可被注释 module 骗过 | 改为 syntax AST module declaration 检查 |
| F11 | `unique` 与“不宣称唯一”冲突 | 改为 `single_candidate` |
| F12 | 空 after loop；O(E²) | 删除空 loop；O(E²) 记录为后续 |
| F13 | architecture JSON 不含 filter 状态 | 增加 `result.view` |
| F14 | FIFO 只测 directed；P136.1 无测试 | 新增 visibility/warning 回归 |

## 2. 修复原则

- FIFO 默认不可见；`paths --through-fifo` 显式构建/遍历；
- 所有 consumer 共用 `edge_visibility`；
- 不再新增 regex 提取；
- constraint serialization 单实现；
- 不删除审计要求的旧测试。

## 3. 验证

```text
check_semantic_regex: ✅
check_except_pass: ✅
check_docs / check_plan / check_crap / check_cli_layers: ✅
warning: 2 passed
（FIFO visibility 测试已随 P138 删除）
constraint / verify / schema / architecture / tb join: targeted passed
```

## 4. 剩余

F12 剩余性能 nit：`ConstraintTracer._analyze_block` 仍逐边扫描（O(E²)），
不影响正确性；后续可做索引优化。
F15 已支持 `--base <commit>` commit range。
