# ==============================================================================
# query/covergroup.py - Covergroup 联系查询 (iter_165 G3, 方案 B)
#
# 架构决策 (plan B / D4 范式): covergroup = 覆盖率**观察域**, 独立于数据流。
# 定义来自 CovergroupExtractor (独立结构, 不进主图); 本 tracer 经**采样引用**
# 桥接主图 — 数据 fanin 单一实现 (委托 UnifiedTracer.trace_fanin), 观察边
# 不建图。
#
# 回答 (方豆 Q 形):
#   Q1 trace_sampling_chain(cg, cp, instance?) — 这个 coverpoint 采样什么
#      信号 → 该信号谁驱动? (cg → signal → fanin)
#   Q2 trace_coverpoints(signal_id)          — 信号 X 被哪些 covergroup/
#      coverpoint 采样? (反向: module 顶层 / class 类型级 / 实例级)
#   Q3 trace_rand_linkage(cg, cp, instance?) — class cg 采样 rand 属性 →
#      受哪些约束? (委托 ConstraintTracer, D4)
#
# 语义边界 (静态限定, 文档标记):
# - class cg 的数据端点 = 实例 (D3): Q1/Q3 需 instance (top.p); 类型级
#   packet.addr 无驱动 (结构宿主)。instance 缺省时若该类实例唯一则自动取。
# - module cg 采样 = module 作用域信号, 宿主锚点 = CovergroupInfo.
#   host_module (elaboration 路径; 多实例模块 = 逐实例记录, 定义级去重未来项)。
# - Q3 约束作用于 rand 属性; 属性是否 rand 的标记 = 未来 (semantic 侧)。
# ==============================================================================
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class SamplingInfo:
    """Q1: 单个 coverpoint 的采样链 (cp → 采样信号 → 驱动)."""

    cp_name: str
    signal_raw: str  # G1 signal 原文 (如 '{din, a}')
    sampled: list[str] = field(default_factory=list)  # 图内信号 id (top.din)
    drivers: list[str] = field(default_factory=list)  # 各采样信号的 fanin 并集
    missing: list[str] = field(default_factory=list)  # 无锚/无实例 → 未成图 id


@dataclass
class CoverpointRef:
    """Q2: 一个采样匹配 (谁在采样 signal_id)."""

    cg_name: str
    cp_name: str
    in_class: str  # class cg = class 名; module cg = ''
    host_module: str  # module cg 宿主实例路径; class cg = ''
    ref_name: str  # 匹配的采样引用名 ('din' / 'addr')
    select: str  # 引用 select ('' / '[3:0]')
    instance: str = ""  # 实例级匹配 (top.p); 类型级 = ''


@dataclass
class RandLinkage:
    """Q3: cg 采样的属性 → 约束 (Q3)."""

    cg_name: str
    cp_name: str
    prop_id: str  # 类型级 packet.addr / 实例 top.p.addr (查询传入)
    constraints: list = field(default_factory=list)  # ConstraintInfo (query.constraint)


class CovergroupTracer:
    """covergroup 联系查询 — 观察域独立 tracer (B).

    构造: cgs (CovergroupExtractor 输出) + tracer (UnifiedTracer —
    图/class 实例/约束的委托面, 数据 fanin 单一实现)。
    """

    def __init__(self, cgs: list, tracer):
        self._cgs = cgs
        self._tr = tracer
        self._inst_cache: dict[str, list[str]] = {}  # class → 实例路径

    # =========================================================================
    # 内部
    # =========================================================================

    def _class_instances(self, class_name: str) -> list[str]:
        """class 实例路径 (主图 trace_class_instances, 惰性缓存)."""
        if class_name not in self._inst_cache:
            try:
                nodes = self._tr.trace_class_instances(class_name)
                self._inst_cache[class_name] = [n.id for n in nodes]
            except Exception as e:
                logger.warning("class 实例枚举失败 (%s): %s", class_name, e)
                self._inst_cache[class_name] = []
        return self._inst_cache[class_name]

    @staticmethod
    def _resolve_instance(cg, instance: str | None, instances: list[str]) -> str:
        """class cg 的数据端点实例: 显式 / 唯一自动 / 否则空 (歧义须显式).

        [iter_167 C4] 显式 instance 校验: 不在该类实例集 → 空 (missing),
        不静默造 bogus id (如 'top.nope.addr'); 实例集为空 (图未枚举, 如
        extends 子类实例直查父类 cg) 时不拦 — 显式路径放行 (B1 边界)。
        """
        if instance:
            if instances and instance not in instances:
                return ""  # 非该类实例 → 查询方 missing (文档标记)
            return instance
        if len(instances) == 1:
            return instances[0]
        return ""  # 多实例歧义 → 调用方需显式 instance (文档)

    # =========================================================================
    # Q1: 采样链 (cp → 信号 → fanin)
    # =========================================================================

    def trace_sampling_chain(self, cg_name: str, cp_name: str | None = None,
                             instance: str | None = None) -> list[SamplingInfo]:
        """cg 的每个 cp: 采样信号 (图 id) + 各信号 fanin 驱动 (并集).

        instance: class cg 的实例路径 (top.p) — D3 数据端点在实例;
        缺省单实例自动取, 多实例歧义返回空 (须显式)。
        """
        out: list[SamplingInfo] = []
        for cg in self._cgs:
            if cg.name != cg_name:
                continue
            inst = ""
            if cg.in_class:
                inst = self._resolve_instance(
                    cg, instance, self._class_instances(cg.in_class))
            for cp in cg.coverpoints:
                if cp_name and cp.name != cp_name:
                    continue
                info = SamplingInfo(cp_name=cp.name, signal_raw=cp.signal)
                for s in cp.sampled:
                    if s.kind == "module":
                        if not cg.host_module:
                            info.missing.append(s.name)  # 无宿主锚 (边界)
                            continue
                        sid = f"{cg.host_module}.{s.name}"
                    elif s.kind == "class_prop":
                        if not inst:
                            info.missing.append(s.name)  # 类型级无数据端点
                            continue
                        sid = f"{inst}.{s.name}"
                    else:
                        continue  # instance_prop (G2 绑定产物) 非本层输入
                    info.sampled.append(sid)
                    try:
                        info.drivers.extend(r.id for r in self._tr.trace_fanin(sid))
                    except Exception:
                        continue
                # 驱动去重保序
                seen = set()
                dedup = []
                for d in info.drivers:
                    if d not in seen:
                        seen.add(d)
                        dedup.append(d)
                info.drivers = dedup
                out.append(info)
        return out

    # =========================================================================
    # Q2: 反向 (谁采样 X)
    # =========================================================================

    def trace_coverpoints(self, signal_id: str) -> list[CoverpointRef]:
        """哪些 covergroup/coverpoint 采样 signal_id.

        匹配域: module 顶层 (top.din, 宿主锚) / class 类型级 (packet.addr) /
        实例级 (top.p.addr — 经该类实例展开)。
        """
        matches: list[CoverpointRef] = []
        for cg in self._cgs:
            for cp in cg.coverpoints:
                for s in cp.sampled:
                    if s.kind == "module":
                        if (cg.host_module
                                and f"{cg.host_module}.{s.name}" == signal_id):
                            matches.append(CoverpointRef(
                                cg_name=cg.name, cp_name=cp.name,
                                in_class="", host_module=cg.host_module,
                                ref_name=s.name, select=s.select))
                    elif s.kind == "class_prop":
                        # 类型级
                        if (cg.in_class
                                and f"{cg.in_class}.{s.name}" == signal_id):
                            matches.append(CoverpointRef(
                                cg_name=cg.name, cp_name=cp.name,
                                in_class=cg.in_class, host_module="",
                                ref_name=s.name, select=s.select))
                        # 实例级 (该类实例展开)
                        for inst in self._class_instances(cg.in_class):
                            if f"{inst}.{s.name}" == signal_id:
                                matches.append(CoverpointRef(
                                    cg_name=cg.name, cp_name=cp.name,
                                    in_class=cg.in_class, host_module="",
                                    ref_name=s.name, select=s.select,
                                    instance=inst))
        return matches

    # =========================================================================
    # Q3: rand 属性 → 约束
    # =========================================================================

    def trace_rand_linkage(self, cg_name: str, cp_name: str | None = None,
                           instance: str | None = None) -> list[RandLinkage]:
        """class cg 采样的属性 → 受哪些约束 (ConstraintTracer D4 委托).

        module cg 不适用 (module 信号无随机化 — 返回空)。
        prop_id: instance 给出 → 实例 (top.p.addr, 自动解析类型级);
        否则类型级 (packet.addr)。
        """
        out: list[RandLinkage] = []
        for cg in self._cgs:
            if cg.name != cg_name or not cg.in_class:
                continue
            inst = ""
            if cg.in_class:
                inst = self._resolve_instance(
                    cg, instance, self._class_instances(cg.in_class))
            for cp in cg.coverpoints:
                if cp_name and cp.name != cp_name:
                    continue
                for s in cp.sampled:
                    if s.kind != "class_prop":
                        continue
                    prop_id = f"{inst}.{s.name}" if inst else f"{cg.in_class}.{s.name}"
                    try:
                        cons = self._tr.trace_constraints(prop_id)
                    except Exception:
                        cons = []
                    out.append(RandLinkage(
                        cg_name=cg.name, cp_name=cp.name,
                        prop_id=prop_id, constraints=cons))
        return out
