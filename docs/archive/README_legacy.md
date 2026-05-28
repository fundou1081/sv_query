# 归档文件说明

## pyslang_adapter_legacy.py

**归档日期**: 2026-05-29
**归档原因**: 死代码清理

包含两个已删除的便捷函数：
- `trace_signal_from_file(f, sig)` — 从文件解析并追踪信号
- `trace_signal_from_code(c, sig)` — 从代码字符串解析并追踪信号

**删除原因**:
1. 项目早期的快速原型验证函数，已被 `UnifiedTracer` 替代
2. 直接使用 `SyntaxTree`，违反铁律1（必须使用 Semantic AST）
3. 无任何调用方（死代码）

**替代方案**: 使用 `UnifiedTracer(sources={...}).build_graph()` 完成相同功能。
