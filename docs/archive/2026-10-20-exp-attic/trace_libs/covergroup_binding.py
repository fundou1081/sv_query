# covergroup_binding.py - covergroup 实例化绑定 (G2 iter_163, 方案 B)
#
# Q4: "p.cg 采样 p.addr" — class 内 covergroup 定义 × class 实例 → 绑定。
#
# 架构 (B): 观察域独立 — 本模块只做**纯映射**, 不建图不查图:
# - 输入: CovergroupExtractor 的定义 (CovergroupInfo, 含 instance_rule) +
#   class 实例路径表 (调用方从主图 trace_class_instances 提供)
# - 输出: BoundCovergroupInstance — cg 定义 + 宿主实例路径 (top.p) +
#   采样实例引用 (p.addr, G1 class_prop ref 映射到实例路径)
#
# 依据:
# - instance_rule='ctor_new' (ctor 对成员 cg new()) → 每个类实例 p 携带
#   p.<cg> 实例; 'uninstantiated' → 实例不活, 不绑定; 'module_scope' →
#   采样 = module 作用域信号 (实例无关, 无逐实例映射 — G3 Q1 走 module 域)
# - G1 类型级决策: cp 采样 class 属性 addr (host=packet) → 绑定后 p.addr
#   (D3: 实例级 = 数据端点, 主图按需创建)

from dataclasses import dataclass, field

from .graph.covergroup_models import CovergroupInfo, SampledSignal


@dataclass
class BoundCoverpoint:
    """绑定后单个 coverpoint: cp 名 + 实例化后的采样引用 (p.addr)."""

    cp_name: str
    signal_raw: str  # G1 signal 原文 (显示/兼容)
    sampled: list[SampledSignal] = field(default_factory=list)  # 实例级 refs


@dataclass
class BoundCovergroupInstance:
    """Q4 答案形态: cg 定义绑定到一个 class 实例."""

    cg: CovergroupInfo
    instance_path: str  # 'top.p'
    coverpoints: list[BoundCoverpoint] = field(default_factory=list)

    @property
    def sampled_signals(self) -> list[str]:
        """该 cg 实例采样的实例信号去重列表 (Q1 侧输入)."""
        seen = set()
        out = []
        for cp in self.coverpoints:
            for s in cp.sampled:
                if s.name not in seen:
                    seen.add(s.name)
                    out.append(s.name)
        return out


def bind_class_covergroups(
    cgs: list[CovergroupInfo],
    class_instances: dict[str, list[str]],
) -> list[BoundCovergroupInstance]:
    """class cg (rule='ctor_new') × class 实例 → 绑定列表.

    class_instances: {class_name: [实例路径...]} — 来自主图
    trace_class_instances (C2, iter_152)。纯映射, 图不变。

    边界 (文档标记): 条件化 new() (if (en) cg = new()) 的分支 = 运行时 —
    instance_rule 仍 'ctor_new', 绑定不区分活/死实例 (models 注释)。
    """
    out: list[BoundCovergroupInstance] = []
    for cg in cgs:
        if not cg.in_class or cg.instance_rule != "ctor_new":
            continue
        insts = class_instances.get(cg.in_class, [])
        for path in insts:
            out.append(_bind_to_instance(cg, path))
    return out


def _bind_to_instance(cg: CovergroupInfo, instance_path: str) -> BoundCovergroupInstance:
    """cg 定义 → 单实例绑定: class_prop ref (addr) → 实例 ref (p.addr)."""
    bound_cps: list[BoundCoverpoint] = []
    for cp in cg.coverpoints:
        inst_refs: list[SampledSignal] = []
        for s in cp.sampled:
            if s.kind == "class_prop":
                inst_refs.append(SampledSignal(
                    name=f"{instance_path}.{s.name}",
                    kind="instance_prop",  # 已实例化 (G3 桥按图解析/建节点)
                    host=s.host,
                    select=s.select,
                    raw=s.raw,
                ))
        bound_cps.append(BoundCoverpoint(
            cp_name=cp.name,
            signal_raw=cp.signal,
            sampled=inst_refs,
        ))
    return BoundCovergroupInstance(
        cg=cg,
        instance_path=instance_path,
        coverpoints=bound_cps,
    )
