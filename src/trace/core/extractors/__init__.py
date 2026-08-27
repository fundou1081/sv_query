# ==============================================================================
# extractors/ - 按 SV 语法类别拆分的 driver extractor 子模块
#
# 起源: ARCHITECTURE_REVIEW_2026-08-27.md §三.1 — driver_extractor.py 单文件 4101 行
# 巨型单文件反模式, 按 SV 语法天然可拆 (assign/always/wire_init/function/case/
# ternary/bit_select/struct/generate/alias 12+ 类).
#
# 拆分原则 (ARCHITECTURE_TODOLIST #1 G2 plan):
# - 每个 extractor 是独立模块, 接收 adapter + result + 共享 callback
# - 不建类继承 DriverExtractor (避免循环 import)
# - 共享 helper (ensure_signal_node / append_edge) 放 _common.py
# - 行为完全一致: 同样的边、同样的节点、同样的 node_id 格式
# - 拆完跑全套 1460+ 测试 + 7 个 spec_unsupported + 4 个 case27 truth
# ==============================================================================
