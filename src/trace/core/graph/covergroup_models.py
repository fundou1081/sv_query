# covergroup_models.py - Covergroup 结构化数据模型
#
# 独立于 SignalGraph，用于 covergroup 信息提取和后续分析。

from dataclasses import dataclass, field


@dataclass
class BinsInfo:
    """单个 bins 的信息"""

    name: str  # bin 名称
    kind: str  # "bins" | "illegal_bins" | "ignore_bins"
    values: str  # 值描述 (如 "[0:63]", "{1,2,3}")
    source_range: str = ""  # 源码位置


@dataclass
class CoverpointInfo:
    """单个 coverpoint 的信息"""

    name: str  # coverpoint 名称 (可能为空)
    signal: str  # 采样信号名
    bins: list[BinsInfo] = field(default_factory=list)
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass
class CoverCrossInfo:
    """cross coverage 的信息"""

    name: str  # cross 名称
    items: list[str] = field(default_factory=list)  # 参与 cross 的 coverpoint 名称
    iff: str = ""  # iff 条件 (如有)


@dataclass
class CovergroupInfo:
    """covergroup 的完整信息"""

    name: str  # covergroup 名称
    clock: str = ""  # 采样时钟
    coverpoints: list[CoverpointInfo] = field(default_factory=list)
    crosses: list[CoverCrossInfo] = field(default_factory=list)
    attributes: dict[str, str] = field(default_factory=dict)
    in_class: str = ""  # 所在 class 名称 (如有)
    source_file: str = ""  # 源文件名
    source_line: int = 0  # 源码行号
    errors: list[str] = field(default_factory=list)  # 解析错误
