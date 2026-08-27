# ==============================================================================
# extractors/_common.py - 共享 helper 协议
#
# [ARCHITECTURE_TODOLIST #1] 拆 driver_extractor.py 4101 行的共享基础设施.
# 所有 extractor (alias/assign/always/...) 通过 callback 协议调用这些 helper,
# 避免每个 extractor 都继承 DriverExtractor (会引入循环 import).
#
# 协议: Protocol class, 不强制继承, 只描述 duck type.
# 真实实现仍由 driver_extractor.DriverExtractor 提供, 这里只规定接口.
# ==============================================================================
from typing import Any, Callable, Protocol

from ..graph.models import EdgeKind, NodeKind


class ExtractorHelpers(Protocol):
    """[2026-08-27 20:38] Extractor 共享的 helper 协议.

    driver_extractor.DriverExtractor 实例隐式满足该协议
    (它实现了 ensure_signal_node / append_edge).
    extractor 模块通过 receive 这些 callable 来工作, 不依赖 DriverExtractor 类.
    """

    def ensure_signal_node(
        self,
        result: Any,
        node_id: str,
        name: str,
        module_name: str,
        file: str = "",
        line: int = 0,
    ) -> None:
        """确保 result.nodes 包含指定 id 的 TraceNode. 已存在则跳过."""
        ...

    def append_edge(
        self,
        result: Any,
        src: str,
        dst: str,
        kind: EdgeKind = EdgeKind.DRIVER,
        assign_type: str = "",
        **kwargs: Any,
    ) -> None:
        """统一入口: 走 edge factory 创建 TraceEdge 并 append 到 result.edges."""
        ...


# 显式 callable 别名 — extractor 函数签名直接用这些类型, 不依赖 Protocol 运行时检查
EnsureSignalNodeFn = Callable[[Any, str, str, str, str, int], None]
AppendEdgeFn = Callable[..., None]
