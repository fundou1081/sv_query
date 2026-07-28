
## V6.3+1/+2 突破 (2026-07-27)

今天彻底搞定了 case 套 ternary 的抽取 bug. driver_extractor.py 的 3 个 bug + visitor 的 2 个 bug, 让所有 mux 嵌套模式都能正确抽取 + 完整条件.

经验: 处理 AST 时, ParenthesizedExpressionSyntax 必须显式解包 — pyslang 把 `(sel ? a : b)` 包装成 `ParenthesizedExpressionSyntax { expression: ConditionalExpressionSyntax { ... } }`. 大多数 extraction code 假定 left/right 直接是 leaf, 看到 paren 就放弃.

关键文件:
- `src/trace/core/driver_extractor.py` (主抽取, 含 ternary decomposition)
- `src/trace/core/visitors/expression_visitor.py` (`get_signals_with_conditions`)
- `src/trace/core/visitors/signal_expression_visitor.py` (`get_all_signals`)
- `src/trace/core/visitors/statement_collector_visitor.py` (`visit_case_statement`)

