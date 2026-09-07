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
    bin_type: str = ""  # [iter_062] "wildcard" | "transition" | "" (普通 bins)
    source_range: str = ""  # 源码位置


@dataclass
class SampledSignal:
    """coverpoint 采样的单个信号引用 (G1 结构化解析, iter_162).

    coverpoint.signal 保留 syntax 原文 (8 消费方兼容); sampled 是结构化
    引用 — 按 scope 分类 (module 信号 / class 属性), G3 查询桥据此映射
    主图 id (fanin) 与 class 结构 (约束/rand)。

    边界 (文档标记, 非 G1 承诺):
    - 中段 select 链 (a[0].b) select 归并到 path 后段 (近似, 罕见形态)
    - 函数调用表达式不解析 callee (procedural 域), 实参引用保留
    - 分类 = 所在 scope (class → class_prop), 跨域引用 (class 内采样
      module 层次名) 分类近似 — G3 桥按图解析纠正
    """

    name: str  # 路径名 'din' / 's.x' (不含 select)
    kind: str  # 'module' | 'class_prop'
    host: str = ""  # class_prop → 所在 class 名; module → '' (G2 实例绑定)
    select: str = ""  # '[3:0]' / '[1]' / 多维拼接; 无 = ''
    raw: str = ""  # 该引用原文 (含 select, 如 'din[3:0]')


@dataclass
class CoverpointInfo:
    """单个 coverpoint 的信息"""

    name: str  # coverpoint 名称 (可能为空)
    signal: str  # 采样信号名 (syntax 原文, 兼容保留)
    bins: list[BinsInfo] = field(default_factory=list)
    iff: str = ""  # [iter_062] iff 条件 (如 "enable"), 无条件为空
    attributes: dict[str, str] = field(default_factory=dict)
    sampled: list[SampledSignal] = field(default_factory=list)  # [G1 iter_162]


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
    host_module: str = ""  # [G3 iter_165] module 顶层 cg 的宿主实例路径
    # (elaboration 锚点: 'top' / 'top.u_sub'; Q1 采样信号 → 图 id 需模块
    # 前缀。class cg = '' — 类型级锚点在 in_class)。多实例模块 → 逐实例
    # 记录 (每 elaboration 一份, 定义级去重 = 未来项)。
    instance_rule: str = ""  # [G2 iter_163] 实例化规则 (见下)
    source_file: str = ""  # 源文件名
    source_line: int = 0  # 源码行号
    errors: list[str] = field(default_factory=list)  # 解析错误

    # instance_rule (G2, 2026-09-06):
    # - 'module_scope'    — module 顶层 covergroup: 实例化在模块作用域, 采样 =
    #   module 作用域信号 (实例无关 — 逐模块实例的 cg 存在性 = 运行时边界,
    #   不影响采样信号映射, 文档标记)
    # - 'ctor_new'        — class 内 covergroup: 类构造函数对成员 cg 无条件
    #   new() → 每个类实例 p 携带 p.<cg> 实例 (静态绑定; 条件化 new() 的
    #   分支语义 = 运行时边界 — 存在即绑定, 文档标记)
    # - 'uninstantiated'  — class 内 covergroup: 构造函数未 new() 该成员
    #   (embedded covergroup 变量只能在新方法里赋值 — LRM; 无 new = 实例
    #   不活, 不静态绑定)
    # 依据: slang 语义 — class 内 covergroup 声明 = CovergroupType + 同名
    # ClassProperty (类型 <unnamed covergroup>); new() 调用只在 ctor syntax
    # 层 (语义子树无语句)。
