"""
trace.core.protocol.detector - 协议检测评分引擎

Phase A Session 4: 协议检测主框架

设计要点
========

1. **4 项置信度融合**:
   - name_score (0.30)        : 标准化后名字 vs schema.signal_roles
   - structural_score (0.30)  : 结构性 hints vs schema 角色期望
   - pattern_score (0.25)     : PatternLearner 通道分组 vs schema 通道
   - handshake_score (0.15)   : Phase B handshake 类型 (TODO: 集成)

2. **算法流程**:
   1. 找 anchors (valid+ready 对) — PatternLearner
   2. 用 anchors 分组到通道
   3. 对每个 schema 通道, 计算 4 项分数
   4. 跨通道聚合, 得到协议总置信度
   5. 选 top-1 协议, 检测变体

3. **变体检测**: needs_signals / needs_absent_signals 全匹配

4. **可扩展**: 加新协议 = 加 YAML, 不动 Python

使用
====

    from trace.core.protocol.schema import load_protocols
    from trace.core.protocol.detector import ProtocolDetector
    from trace.core.protocol.structural import SignalContext

    sigs = [
        SignalContext("awvalid", 1, "output", "register", ["awready"]),
        SignalContext("awready", 1, "input", "port", ["awvalid"]),
        SignalContext("awaddr", 32, "output", "port", ["awvalid"]),
        # ... 更多
    ]
    schemas = load_protocols("config/protocols")
    detector = ProtocolDetector(schemas)
    match = detector.detect(sigs)
    print(f"{match.protocol} ({match.variant}): {match.confidence:.2f}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .schema import ProtocolSchema, SignalRoleSpec, ChannelSpec, VariantSpec
from .normalize import SignalNormalizer, NormalizeConfig
from .structural import SignalContext, StructuralRoleDetector, StructuralHints
from .pattern_learner import PatternLearner, ChannelGroup


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class SignalMapping:
    """一个信号的映射结果.

    Attributes:
        original: 原始信号名 (e.g., "io_aw_valid")
        canonical: 标准化 + 匹配到 schema 后的 canonical 名 (e.g., "awvalid")
        channel: 匹配到的通道 (e.g., "AW")
        role: 匹配到的角色 (e.g., "valid")
        match_type: "exact" / "normalized" / "structural_only" / "none"
        score: 0.0-1.0
    """

    original: str
    canonical: str
    channel: str
    role: str
    match_type: str
    score: float

    def __repr__(self) -> str:
        return (
            f"SignalMapping({self.original!r} → {self.channel}.{self.role}, "
            f"match={self.match_type}, score={self.score:.2f})"
        )


@dataclass
class ChannelMatch:
    """一个通道的匹配结果.

    Attributes:
        name: 通道名
        present: 该通道是否完整 (所有 required 都匹配)
        matched_required: 匹配上的必选信号
        matched_optional: 匹配上的可选信号
        missing_required: 缺失的必选信号
        score: 0.0-1.0
        name_score / structural_score / pattern_score: 4 项分项
    """

    name: str
    present: bool
    matched_required: List[str] = field(default_factory=list)
    matched_optional: List[str] = field(default_factory=list)
    missing_required: List[str] = field(default_factory=list)
    score: float = 0.0
    name_score: float = 0.0
    structural_score: float = 0.0
    pattern_score: float = 0.0

    def __repr__(self) -> str:
        return (
            f"ChannelMatch({self.name}, present={self.present}, "
            f"score={self.score:.2f})"
        )


@dataclass
class ProtocolMatch:
    """协议匹配结果.

    Attributes:
        protocol: 协议名 (e.g., "AXI4")
        variant: 变体 (e.g., "AXI4_FULL" or None)
        confidence: 0.0-1.0 总置信度
        channels: {channel_name: ChannelMatch}
        signal_mappings: List[SignalMapping]
        warnings: List[str]
        name_score / structural_score / pattern_score / handshake_score: 4 项分项
    """

    protocol: str
    variant: Optional[str] = None
    confidence: float = 0.0
    channels: Dict[str, ChannelMatch] = field(default_factory=dict)
    signal_mappings: List[SignalMapping] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    name_score: float = 0.0
    structural_score: float = 0.0
    pattern_score: float = 0.0
    handshake_score: float = 0.0

    def __repr__(self) -> str:
        return (
            f"ProtocolMatch({self.protocol}"
            f"{f' ({self.variant})' if self.variant else ''}, "
            f"conf={self.confidence:.2f}, channels={list(self.channels.keys())})"
        )


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class ProtocolDetector:
    """协议检测评分引擎.

    集成 Session 1 (normalize) + Session 2 (structural) + Session 3 (pattern) +
    Phase B (handshake, TODO).
    """

    # 4 项权重 — 符合设计原则
    WEIGHT_NAME = 0.30
    WEIGHT_STRUCTURAL = 0.30
    WEIGHT_PATTERN = 0.25
    WEIGHT_HANDSHAKE = 0.15

    # 置信度阈值
    CONFIDENCE_THRESHOLD = 0.5

    def __init__(
        self,
        schemas: Optional[Dict[str, ProtocolSchema]] = None,
        registry: Optional["ProtocolSchemaRegistry"] = None,  # type: ignore
        normalizer: Optional[SignalNormalizer] = None,
        structural_detector: Optional[StructuralRoleDetector] = None,
        pattern_learner: Optional[PatternLearner] = None,
    ):
        # 接受 schemas dict 或 registry
        if registry is not None:
            self.schemas = registry.protocols
        elif schemas is not None:
            self.schemas = schemas
        else:
            self.schemas = {}

        self.norm = normalizer or SignalNormalizer(NormalizeConfig.default())
        self.struct_det = structural_detector or StructuralRoleDetector()
        self.pattern_learner = pattern_learner or PatternLearner(self.norm)

    def detect(self, signals: List[SignalContext]) -> ProtocolMatch:
        """检测协议, 返回 top-1 ProtocolMatch."""
        if not signals:
            return ProtocolMatch(
                protocol="UNKNOWN",
                confidence=0.0,
                warnings=["no signals provided"],
            )

        # 1) 用 PatternLearner 找 anchors + 分组
        anchors = self._find_anchors(signals)
        groups = self.pattern_learner.learn(
            anchors=[(a[0], a[1]) for a in anchors],
            all_signals=[s.name for s in signals],
        )

        # 2) 对每个 schema 协议评分
        candidates: List[ProtocolMatch] = []
        for protocol_name, schema in self.schemas.items():
            match = self._score_protocol(schema, signals, groups)
            candidates.append(match)

        # 3) 选 top-1
        if not candidates:
            return ProtocolMatch(
                protocol="UNKNOWN",
                confidence=0.0,
                warnings=["no protocols in registry"],
            )

        best = max(candidates, key=lambda m: m.confidence)
        return best

    # ----- 协议评分 -----

    def _score_protocol(
        self,
        schema: ProtocolSchema,
        signals: List[SignalContext],
        groups: List[ChannelGroup],
    ) -> ProtocolMatch:
        """对单个协议评分."""
        channel_matches: Dict[str, ChannelMatch] = {}
        all_mappings: List[SignalMapping] = []

        for ch_name, ch_spec in schema.channels.items():
            ch_match, mappings = self._score_channel(
                ch_name, ch_spec, schema, signals, groups,
            )
            channel_matches[ch_name] = ch_match
            all_mappings.extend(mappings)

        # 4 项分数
        name_score = self._aggregate_name_score(channel_matches, schema)
        structural_score = self._aggregate_structural_score(channel_matches, schema)
        pattern_score = self._aggregate_pattern_score(channel_matches, groups, schema)
        handshake_score = 0.0  # TODO: 集成 Phase B

        confidence = (
            self.WEIGHT_NAME * name_score
            + self.WEIGHT_STRUCTURAL * structural_score
            + self.WEIGHT_PATTERN * pattern_score
            + self.WEIGHT_HANDSHAKE * handshake_score
        )

        # 变体检测
        variant = self._detect_variant(schema, signals)

        warnings: List[str] = []
        for ch_name, ch_match in channel_matches.items():
            if not ch_match.present:
                warnings.append(
                    f"channel {ch_name} missing required: {ch_match.missing_required}"
                )

        return ProtocolMatch(
            protocol=schema.protocol,
            variant=variant,
            confidence=confidence,
            channels=channel_matches,
            signal_mappings=all_mappings,
            warnings=warnings,
            name_score=name_score,
            structural_score=structural_score,
            pattern_score=pattern_score,
            handshake_score=handshake_score,
        )

    def _score_channel(
        self,
        ch_name: str,
        ch_spec: ChannelSpec,
        schema: ProtocolSchema,
        signals: List[SignalContext],
        groups: List[ChannelGroup],
    ) -> Tuple[ChannelMatch, List[SignalMapping]]:
        """对单个通道评分."""
        # 标准化所有信号名
        sig_norms = {s.name: self.norm.normalize(s.name).normalized for s in signals}
        sig_by_norm = {}  # 反向: 标准化名 → 原始 SignalContext
        for s in signals:
            norm = sig_norms[s.name]
            sig_by_norm.setdefault(norm, []).append(s)

        matched_req: List[str] = []
        matched_opt: List[str] = []
        missing_req: List[str] = []
        mappings: List[SignalMapping] = []

        # 检查 required
        for req_sig in ch_spec.required:
            if req_sig in sig_by_norm:
                matched_req.append(req_sig)
                # 找对应的原始信号
                for s in sig_by_norm[req_sig]:
                    mappings.append(SignalMapping(
                        original=s.name,
                        canonical=req_sig,
                        channel=ch_name,
                        role=schema.signal_roles[req_sig].role if req_sig in schema.signal_roles else "unknown",
                        match_type="exact" if req_sig in sig_norms.values() else "normalized",
                        score=1.0,
                    ))
            else:
                missing_req.append(req_sig)

        # 检查 optional (加分, 不影响 required)
        for opt_sig in ch_spec.optional:
            if opt_sig in sig_by_norm:
                matched_opt.append(opt_sig)
                for s in sig_by_norm[opt_sig]:
                    mappings.append(SignalMapping(
                        original=s.name,
                        canonical=opt_sig,
                        channel=ch_name,
                        role=schema.signal_roles[opt_sig].role if opt_sig in schema.signal_roles else "unknown",
                        match_type="normalized",
                        score=0.6,
                    ))

        # 通道完整性
        present = len(missing_req) == 0

        # 通道分数: name + structural + pattern
        # name 分数: required 全部匹配 = 1.0, 否则按比例
        if ch_spec.required_count() > 0:
            name_score = len(matched_req) / ch_spec.required_count()
        else:
            name_score = 1.0 if matched_opt else 0.0

        # structural 分数: required 信号的结构特征是否一致
        structural_score = self._channel_structural_score(
            ch_spec, schema, sig_by_norm,
        )

        # pattern 分数: 是否有一个 PatternLearner group 对应这个 channel
        pattern_score = self._channel_pattern_score(
            ch_name, ch_spec, groups,
        )

        # 通道总分 (3 项加权, 内部)
        score = 0.4 * name_score + 0.3 * structural_score + 0.3 * pattern_score

        ch_match = ChannelMatch(
            name=ch_name,
            present=present,
            matched_required=matched_req,
            matched_optional=matched_opt,
            missing_required=missing_req,
            score=score,
            name_score=name_score,
            structural_score=structural_score,
            pattern_score=pattern_score,
        )
        return ch_match, mappings

    def _channel_structural_score(
        self,
        ch_spec: ChannelSpec,
        schema: ProtocolSchema,
        sig_by_norm: Dict[str, List[SignalContext]],
    ) -> float:
        """通道内 required 信号的结构一致性分数."""
        if not ch_spec.required:
            return 1.0

        correct = 0
        for req_sig in ch_spec.required:
            if req_sig not in sig_by_norm:
                continue  # required 但不存在, 不算分
            role_spec = schema.signal_roles.get(req_sig)
            if not role_spec:
                correct += 0.5
                continue
            for sig in sig_by_norm[req_sig]:
                hints = self.struct_det.detect(sig)
                if hints.is_valid_like >= 0.3 and role_spec.role == "valid":
                    correct += 1
                elif hints.is_ready_like >= 0.3 and role_spec.role == "ready":
                    correct += 1
                elif hints.is_data_like >= 0.3 and role_spec.role == "data":
                    correct += 1
                elif hints.is_addr_like >= 0.3 and role_spec.role == "addr":
                    correct += 1
                elif hints.is_resp_like >= 0.3 and role_spec.role == "resp":
                    correct += 1
                elif hints.is_ctrl_like >= 0.3 and role_spec.role == "ctrl":
                    correct += 1
                elif hints.is_strb_like >= 0.3 and role_spec.role == "strb":
                    correct += 1
                elif hints.is_last_like >= 0.3 and role_spec.role == "last":
                    correct += 1
                else:
                    correct += 0.3  # 角色不匹配但有结构

        return correct / len(ch_spec.required)

    def _channel_pattern_score(
        self,
        ch_name: str,
        ch_spec: ChannelSpec,
        groups: List[ChannelGroup],
    ) -> float:
        """通道是否被 PatternLearner 识别为独立 group."""
        # 找 ch_name 对应的 group
        for g in groups:
            # ch_name "AW" → group.name "AW" (uppercase)
            if g.name.upper() == ch_name.upper():
                # 检查这个 group 是否包含 ch_spec 的 required 信号
                sig_norms = {
                    self.norm.normalize(s).normalized for s in g.signals
                }
                req_matched = sum(1 for r in ch_spec.required if r in sig_norms)
                if ch_spec.required_count() > 0:
                    return req_matched / ch_spec.required_count()
                return 1.0 if g.signals else 0.0

        # 如果 schema 通道名 = "AW", 但 group 叫 "W" (无前缀冲突)
        # 也接受: group 包含 ch_spec.required
        for g in groups:
            sig_norms = {
                self.norm.normalize(s).normalized for s in g.signals
            }
            if all(req in sig_norms for req in ch_spec.required):
                return 0.8  # 部分匹配, 没明确 channel 名字

        return 0.5  # 没找到对应 group, 中性分数

    def _aggregate_name_score(
        self,
        channel_matches: Dict[str, ChannelMatch],
        schema: ProtocolSchema,
    ) -> float:
        """所有通道 name_score 平均."""
        if not channel_matches:
            return 0.0
        return sum(cm.name_score for cm in channel_matches.values()) / len(channel_matches)

    def _aggregate_structural_score(
        self,
        channel_matches: Dict[str, ChannelMatch],
        schema: ProtocolSchema,
    ) -> float:
        return sum(cm.structural_score for cm in channel_matches.values()) / max(1, len(channel_matches))

    def _aggregate_pattern_score(
        self,
        channel_matches: Dict[str, ChannelMatch],
        groups: List[ChannelGroup],
        schema: ProtocolSchema,
    ) -> float:
        return sum(cm.pattern_score for cm in channel_matches.values()) / max(1, len(channel_matches))

    def _detect_variant(
        self,
        schema: ProtocolSchema,
        signals: List[SignalContext],
    ) -> Optional[str]:
        """检测协议变体."""
        sig_norms = {self.norm.normalize(s.name).normalized for s in signals}

        # 选第一个完全匹配的变体
        for variant in schema.variants:
            ok = True
            for needed in variant.needs_signals:
                if needed not in sig_norms:
                    ok = False
                    break
            if not ok:
                continue
            for absent in variant.needs_absent_signals:
                if absent in sig_norms:
                    ok = False
                    break
            if ok:
                return variant.name

        return None

    def _find_anchors(
        self,
        signals: List[SignalContext],
    ) -> List[Tuple[str, str]]:
        """从信号中找 valid+ready 锚点对.

        规则: 1-bit output register + 1-bit input, 名字共享前缀.
        """
        anchors: List[Tuple[str, str]] = []
        outputs = [s for s in signals if s.direction == "output" and s.width == 1]
        inputs = [s for s in signals if s.direction == "input" and s.width == 1]

        for out_sig in outputs:
            out_norm = self.norm.normalize(out_sig.name).normalized
            for in_sig in inputs:
                in_norm = self.norm.normalize(in_sig.name).normalized
                # 找共享前缀 (去掉 valid/ready 后缀)
                # 简化: 只要 out_norm 是 in_norm 子串或反之
                if out_norm in in_norm or in_norm in out_norm:
                    anchors.append((out_sig.name, in_sig.name))
                    break
        return anchors
