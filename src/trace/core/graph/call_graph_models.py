# call_graph_models.py - 函数调用图数据模型
#
# 独立于 SignalGraph，用于调用图构建和分析。

from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class CallNode:
    """调用图节点"""
    caller: str              # 调用者 (如 "my_seq::body")
    callee: str              # 被调用者 (如 "do_drive")
    kind: str                # "call" | "fork" | "randomize"
    line: int = 0            # 源码行号
    children: List['CallNode'] = field(default_factory=list)  # 子调用
    join_type: str = ""      # "join" | "join_none" | "join_any" (仅 fork)
    randomize_vars: List[str] = field(default_factory=list)  # randomize 的变量
    inline_constraint: str = ""  # inline constraint 文本


@dataclass
class CallGraph:
    """完整调用图"""
    entry_point: str              # 入口函数/任务 (如 "my_seq::body")
    root: CallNode = None         # 根节点
    randomize_calls: List[CallNode] = field(default_factory=list)  # 所有 randomize 调用
    fork_points: List[CallNode] = field(default_factory=list)      # 所有 fork 点
    errors: List[str] = field(default_factory=list)                # 解析错误
