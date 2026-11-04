# Task: 语义提取 regex 纪律（P66）

**状态**: 已完成
**方豆决定 (2026-11-04)**: 仅 UVM 宏相关部分允许 regex；class/constraint/covergroup 语义必须走 pyslang semantic。

## 交付

- DISCIPLINE / CODING_STYLE / AGENTS 明确规则与唯一例外；
- 方法调用提取从 regex 迁到 semantic AST（消除现有非 UVM regex）；
- `tools/check_semantic_regex.py` 机械检查 + 自检测试；
- 文档登记与全量回归。

## 例外边界

- 允许：`src/trace/core/query/uvm.py` 的 `uvm_*_utils` / `uvm_do*` /
  `uvm_declare_p_sequencer` / `type_id::create` / factory create；
- 原因：pyslang 预处理后宏调用不在 semantic syntax；
- 输出必须标 `confidence=syntactic`，不能作为 verify 证明。
