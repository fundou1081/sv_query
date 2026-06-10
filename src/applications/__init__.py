"""
trace.applications — 应用层

每个子目录 = 一个 application domain:
  - bus:       Bus 协议检测 (AXI4 / AXI4-Stream / TL-UL / APB / AHB / Wishbone)
  - cpu:       🔮 CPU pipeline / 微架构分析 (规划中)
  - operator:  🔮 算子识别 / 加速器分析 (规划中)

设计原则:
  - 各 application 独立, 不共享抽象基类 (YAGNI — 等真有第二个再加 base.py)
  - 可以依赖 trace.core/ 下的通用能力 (graph, query, analyzer, builder)
  - 应用间不直接依赖, 互不污染
"""
