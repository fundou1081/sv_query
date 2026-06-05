"""
CLI 公共 evidence helpers
=========================

集中 evidence 召回的 helper 函数,供 5 个命令(trace, cdc, verify, risk,
dataflow, controlflow)复用。

设计原则:
- 每个命令入口 `build_resolver(file)` 一次,后续所有 resolve(signal) 共享同一 graph
- evidence_to_dict / snippet_to_dict 序列化,JSON 输出用
- evidence_summary_line 一行文本摘要,text 输出用
- 行为完全等价于 trace.py 中原 _evidence_to_dict / _snippet_to_dict (Stage 3A + Stage 4)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Tuple

from trace.core.trace_evidence import TraceEvidenceResolver
from trace.unified_tracer import UnifiedTracer


# ----------------------------------------------------------------------------
# 1. resolver 构建: 每个命令入口 build 一次,后续 resolve() 共享 graph + adapter
# ----------------------------------------------------------------------------

def build_resolver(file: Path, log_level: str = "ERROR") -> Tuple[TraceEvidenceResolver, Any, Any]:
    """读取 SV 源文件 → build graph + adapter + resolver

    Args:
        file: SystemVerilog 源文件路径
        log_level: 编译器日志级别,CLI 默认 ERROR 静音 WARNING

    Returns:
        (resolver, graph, adapter) - adapter 暴露 semantic API 给 resolver 内部用
    """
    with open(str(file)) as f:
        source = f.read()
    tracer = UnifiedTracer(sources={str(file): source}, log_level=log_level)
    graph = tracer.build_graph()
    adapter = tracer._get_adapter()
    resolver = TraceEvidenceResolver(graph=graph, adapter=adapter)
    return resolver, graph, adapter


def make_resolver(graph, adapter) -> TraceEvidenceResolver:
    """用已有 graph + adapter 构造 resolver (避免重复 build)

    场景: 命令本身已 build 了 graph (如 verify/risk),直接复用避免再 build 一次
    """
    return TraceEvidenceResolver(graph=graph, adapter=adapter)


# ----------------------------------------------------------------------------
# 2. 序列化: Evidence / SourceSnippet → JSON-friendly dict
# ----------------------------------------------------------------------------

def snippet_to_dict(snippet) -> Optional[dict]:
    """SourceSnippet → dict (Stage 4 offset-based slicing 输出)"""
    if snippet is None:
        return None
    return {
        "file": snippet.location.file,
        "line_start": snippet.location.line_start,
        "line_end": snippet.location.line_end,
        "column": snippet.location.column,
        "text": snippet.text,
    }


def evidence_to_dict(ev) -> Optional[dict]:
    """Evidence → dict (含 enclosing_* snippets + credibility)

    字段集对齐 trace evidence 命令 Stage 4 形态:
    - signal: 哪个信号
    - source_location: 主 source 的位置
    - source_text: 源码片段(可能是连续 assign 整行,或 expression 切片)
    - enclosing_always / always_comb / if / assign / class / constraint
    - enclosing_chain: 包络层链(从最外到最内)
    - is_verified / credibility_score: 交叉验证分数
    """
    if ev is None:
        return None
    return {
        "signal": ev.signal,
        "source_location": (
            {
                "file": ev.source_location.file,
                "line_start": ev.source_location.line_start,
                "line_end": ev.source_location.line_end,
                "column": ev.source_location.column,
            }
            if ev.source_location is not None
            else None
        ),
        "source_text": ev.source_text,
        "enclosing_always": snippet_to_dict(ev.enclosing_always),
        "enclosing_always_comb": snippet_to_dict(ev.enclosing_always_comb),
        "enclosing_if": snippet_to_dict(ev.enclosing_if),
        "enclosing_assign": snippet_to_dict(ev.enclosing_assign),
        "enclosing_class": snippet_to_dict(ev.enclosing_class),
        "enclosing_constraint": snippet_to_dict(ev.enclosing_constraint),
        "enclosing_chain": [snippet_to_dict(s) for s in ev.enclosing_chain],
        "is_verified": ev.is_verified,
        "credibility_score": ev.credibility_score,
    }


# ----------------------------------------------------------------------------
# 3. 文本输出: 一行 summary (text 模式 --evidence 用)
# ----------------------------------------------------------------------------

def _ev_to_inputs(ev) -> Optional[Tuple[Optional[dict], str]]:
    """抽取 evidence summary 需要的两个字段: (source_location_dict, source_text)

    同时支持 Evidence 对象 (刚 resolve 出来的) 和 dict (已经 evidence_to_dict 过)
    """
    if ev is None:
        return None
    if isinstance(ev, dict):
        return (ev.get("source_location"), ev.get("source_text") or "")
    # Evidence 对象: 取属性
    loc = ev.source_location
    text = ev.source_text or ""
    if loc is None:
        return (None, text)
    return ({"file": loc.file, "line_start": loc.line_start}, text)


def evidence_summary_line(ev) -> Optional[str]:
    """生成 1 行 evidence 摘要: 'file:line: source_text_first_line'

    返回 None 时表示没有 evidence 可显示 (resolve 失败 / 不在源文件里)

    同时接受 Evidence 对象和 dict (Stage 5: 命令层经常先 evidence_to_dict
    再传给 summary,避免再次访问 Evidence 对象)
    """
    inputs = _ev_to_inputs(ev)
    if inputs is None:
        return None
    loc, text = inputs
    if loc is None:
        return None
    first_line = text.split("\n", 1)[0] if text else ""
    return f"{loc['file']}:{loc['line_start']}: {first_line}".rstrip()


def evidence_summary_indented(ev, indent: str = "  └─ ") -> Optional[str]:
    """缩进版本,适合贴在信号下方显示"""
    line = evidence_summary_line(ev)
    if line is None:
        return None
    return f"{indent}{line}"


# ----------------------------------------------------------------------------
# 4. Human-friendly output (--human flag, Stage 6: arrow-based, 人类可读)
# ----------------------------------------------------------------------------
#
# 设计原则:
# - 一行 = 一条信号链,用 → 箭头连接
# - 条件用 [when ...] 包裹
# - 风险用 [RISK] / [NO SYNC] 标
# - evidence 可选 (--human + --evidence 同时给)
# - 跟现有 text / json 输出平行, 互不覆盖

import re

_ARROW = "→"      # 驱动关系
_ARROW_COND = "⇢" # 条件驱动
_ARROW_BRANCH = "⤷"  # 分支
_ANSI_BOLD = "\033[1m"
_ANSI_DIM = "\033[2m"
_ANSI_RESET = "\033[0m"
_ANSI_YELLOW = "\033[33m"
_ANSI_RED = "\033[31m"
_ANSI_GREEN = "\033[32m"
_ANSI_CYAN = "\033[36m"
_ANSI_MAGENTA = "\033[35m"

_USE_COLOR = True  # 可用 NO_COLOR 环境变量关


def _color(s: str, code: str) -> str:
    if not _USE_COLOR:
        return s
    return f"{code}{s}{_ANSI_RESET}"


def _risk_color(level: str) -> str:
    level = (level or "").upper()
    if level in ("CRITICAL", "HIGH"):
        return _color(level, _ANSI_RED)
    if level == "MEDIUM":
        return _color(level, _ANSI_YELLOW)
    if level in ("LOW", "SAFE"):
        return _color(level, _ANSI_GREEN)
    return level


def format_signal_arrow_chain(
    signals: list,
    conditions: list = None,
    arrows: str = "default",
    risk_marker: str = None,
) -> str:
    """格式化信号链: ['A', 'B', 'C'] → 'A → B → C'

    Args:
        signals: 信号名列表 (in order)
        conditions: 可选, 与 signals 等长或 None
        arrows: 'default' (→) / 'cond' (⇢) / 'branch' (⤷)
        risk_marker: 可选, 在链尾加 [RISK=HIGH] 之类
    """
    if not signals:
        return ""
    if arrows == "cond":
        sep = f" {_ARROW_COND} "
    elif arrows == "branch":
        sep = f" {_ARROW_BRANCH} "
    else:
        sep = f" {_ARROW} "

    parts = []
    for i, s in enumerate(signals):
        parts.append(_color(str(s), _ANSI_BOLD if i == 0 or i == len(signals) - 1 else _ANSI_CYAN))
    chain = sep.join(parts)

    if conditions:
        # 在每对信号之间插条件: A [when X] B
        # conditions[i] 是 A→B 的条件
        if len(conditions) == len(signals) - 1:
            for i, cond in enumerate(conditions):
                if cond:
                    cond_str = f" [{_color('when ' + str(cond), _ANSI_MAGENTA)}] "
                    # 重组成 'A [when X] B' 这种
                    # 拆开 parts 重拼
                    new_parts = []
                    for j, p in enumerate(parts):
                        new_parts.append(p)
                        if j == i:
                            new_parts.append(cond_str)
                    parts = new_parts
                    chain = sep.join(parts)

    if risk_marker:
        chain += "  " + _risk_color(risk_marker)
    return chain


def format_fanin_human(
    signal: str,
    drivers: list,
    evidence_map: dict = None,
) -> str:
    """trace fanin human 输出: 反向链, 从 source 到 signal

    drivers: [{id, kind, distance, evidence?}, ...]
    evidence_map: {signal_id: evidence_dict} 可选
    """
    if not drivers:
        return f"{_color(signal, _ANSI_BOLD)} ← (no drivers)"

    # 按 distance 升序排序 (最远的源头在前)
    sorted_drvs = sorted(drivers, key=lambda d: d.get("distance", 0), reverse=True)

    chain = [str(signal)]
    chain.extend([d["id"] for d in sorted_drvs])
    chain.reverse()  # 现在是 [源头, ..., signal]

    # 拼主体
    parts = []
    for i, s in enumerate(chain):
        if i == 0:
            parts.append(_color(s, _ANSI_DIM))  # 源头 dim
        elif i == len(chain) - 1:
            parts.append(_color(s, _ANSI_BOLD))  # 终点 bold
        else:
            parts.append(_color(s, _ANSI_CYAN))
    main = f" {_ARROW} ".join(parts)

    lines = [f"Fanin of {_color(signal, _ANSI_BOLD)}", f"  {main}"]

    if evidence_map:
        # 末尾 evidence (仅 signal 自己的, 跟现有 _output_text 兼容)
        sig_ev = evidence_map.get(signal)
        if sig_ev:
            loc = sig_ev.get("source_location", {})
            text = sig_ev.get("source_text", "")
            if loc and text:
                first = text.split("\n", 1)[0]
                lines.append(
                    f"  {_color('└─', _ANSI_DIM)} "
                    f"{loc['file']}:{loc['line_start']}: "
                    f"{_color(first, _ANSI_DIM)}"
                )

    return "\n".join(lines)


def format_fanout_human(
    signal: str,
    loads: list,
    evidence_map: dict = None,
) -> str:
    """trace fanout human 输出: 正向链, 从 signal 到 leaves"""
    if not loads:
        return f"{_color(signal, _ANSI_BOLD)} → (no loads)"

    sorted_loads = sorted(loads, key=lambda d: d.get("distance", 0), reverse=True)

    chain = [str(signal)]
    chain.extend([d["id"] for d in sorted_loads])

    parts = []
    for i, s in enumerate(chain):
        if i == 0:
            parts.append(_color(s, _ANSI_BOLD))
        elif i == len(chain) - 1:
            parts.append(_color(s, _ANSI_DIM))  # 叶 dim
        else:
            parts.append(_color(s, _ANSI_CYAN))
    main = f" {_ARROW} ".join(parts)

    lines = [f"Fanout of {_color(signal, _ANSI_BOLD)}", f"  {main}"]

    if evidence_map:
        sig_ev = evidence_map.get(signal)
        if sig_ev:
            loc = sig_ev.get("source_location", {})
            text = sig_ev.get("source_text", "")
            if loc and text:
                first = text.split("\n", 1)[0]
                lines.append(
                    f"  {_color('└─', _ANSI_DIM)} "
                    f"{loc['file']}:{loc['line_start']}: "
                    f"{_color(first, _ANSI_DIM)}"
                )

    return "\n".join(lines)


def format_dataflow_human(
    from_signal: str,
    to_signal: str,
    paths: list,
) -> str:
    """dataflow analyze human 输出: from → ... → to, 多 path 竖排

    paths: [{segments: [{from_signal, to_signal, assign_type, condition?, evidence?}], ...}, ...]
    """
    if not paths:
        return (
            f"{_color(from_signal, _ANSI_BOLD)} {_ARROW} {_color(to_signal, _ANSI_BOLD)}: "
            f"{_color('no path found', _ANSI_RED)}"
        )

    lines = [
        f"DataFlow: "
        f"{_color(from_signal, _ANSI_BOLD)} {_ARROW} {_color(to_signal, _ANSI_BOLD)}",
        f"  paths: {_color(str(len(paths)), _ANSI_CYAN)}",
        "",
    ]

    for pi, path in enumerate(paths):
        segs = path.get("segments", [])
        if not segs:
            continue
        lines.append(f"  Path {pi}:")
        # 主链: from → [when cond] s1.to → [when cond] s2.to → ... → to_signal
        chain = [_color(from_signal, _ANSI_BOLD)]
        for seg in segs:
            cond = seg.get("condition", "").strip()
            chain.append(_ARROW)
            if cond:
                chain.append(f"[{_color('when ' + cond, _ANSI_MAGENTA)}]")
            chain.append(_color(seg["to_signal"], _ANSI_CYAN))
        # 末尾如果不是真正的 to_signal, 补上
        if (
            from_signal != to_signal
            and chain[-1] != _color(to_signal, _ANSI_BOLD)
            and segs[-1].get("to_signal") != to_signal
        ):
            chain.append(_ARROW)
            chain.append(_color(to_signal, _ANSI_BOLD))
        lines.append("    " + " ".join(chain))
        # 段 metadata (assign_type + line + score) 贴下面
        for j, seg in enumerate(segs):
            atype = seg.get("assign_type", "")
            ev = seg.get("evidence", {}) or {}
            loc = ev.get("source_location", {}) if ev else {}
            line_no = loc.get("line_start", "?") if loc else "?"
            score = ev.get("credibility_score", "?")
            ev_note = ""
            if loc:
                first = (ev.get("source_text") or "").split("\n", 1)[0]
                ev_note = f"  evidence: {first!r}"
            lines.append(
                f"      {_color('└─ seg' + str(j) + ':', _ANSI_DIM)} "
                f"{atype} @L{line_no}, score={score}{ev_note}"
            )
        lines.append("")

    return "\n".join(lines)


def format_controlflow_human(signal: str, conditioned_drivers: list) -> str:
    """controlflow analyze human 输出: 条件 + 箭头

    支持两种数据格式 (兼容):
    - v1: [{condition, drivers: [signals], evidence?}, ...]
    - v2: [{to_node, conditions: [{expr, edge: {src, dst, kind, condition?}}]}, ...]

    输出统一: 'when EXPR: src → dst'
    """
    if not conditioned_drivers:
        return f"{_color(signal, _ANSI_BOLD)}: {_color('no conditional drivers', _ANSI_DIM)}"

    lines = [f"ControlFlow: {_color(signal, _ANSI_BOLD)}", ""]
    # 拉平所有 conditions
    flat = []
    for cd in conditioned_drivers:
        if "conditions" in cd and isinstance(cd["conditions"], list):
            # v2 格式
            for c in cd["conditions"]:
                expr = c.get("expr") or c.get("edge", {}).get("condition") or "always"
                src = c.get("edge", {}).get("src", "?")
                dst = c.get("edge", {}).get("dst", signal)
                flat.append({"cond": expr, "src": src, "dst": dst})
        else:
            # v1 格式
            cond = cd.get("condition") or cd.get("predicate") or "always"
            drivers = cd.get("drivers", [])
            for d in drivers:
                flat.append({"cond": cond, "src": d, "dst": signal})

    if not flat:
        return f"{_color(signal, _ANSI_BOLD)}: {_color('no conditional drivers', _ANSI_DIM)}"

    for f in flat:
        cond = f["cond"]
        src = f["src"]
        dst = f["dst"]
        chain = f"{_color(src, _ANSI_CYAN)} {_ARROW} {_color(dst, _ANSI_BOLD)}"
        lines.append(f"  when {_color(cond, _ANSI_MAGENTA)}: {chain}")

    return "\n".join(lines)


def format_cdc_human(cdc_paths: list) -> str:
    """cdc analyze human 输出: clk_a: A → B (NO SYNC, HIGH risk)"""
    if not cdc_paths:
        return _color("no CDC paths found", _ANSI_GREEN)

    lines = ["CDC Paths:", ""]
    for p in cdc_paths:
        src_clk = p.get("source_domain_short", "?")
        dst_clk = p.get("target_domain_short", "?")
        src = p.get("source", "?")
        dst = p.get("target", "?")
        sync = "SYNC" if p.get("has_synchronizer") else "NO SYNC"
        risk = p.get("risk", "?").upper()
        sync_color = _ANSI_GREEN if sync == "SYNC" else _ANSI_RED

        chain = (
            f"{_color(src_clk + ':', _ANSI_DIM)} "
            f"{_color(src, _ANSI_BOLD)} {_ARROW} "
            f"{_color(dst, _ANSI_BOLD)}"
        )
        tags = (
            f" [{_color(sync, sync_color)}] "
            f"[{_risk_color(risk)}]"
        )
        lines.append(f"  {chain}{tags}")

        # evidence hint
        for field in ("source_evidence", "target_evidence"):
            ev = p.get(field) or {}
            loc = ev.get("source_location", {}) if ev else {}
            if loc:
                lines.append(
                    f"    {_color('└─ ' + field.replace('_evidence', ''), _ANSI_DIM)} "
                    f"{loc.get('file', '?')}:{loc.get('line_start', '?')}"
                )
    return "\n".join(lines)


# 环境变量: NO_COLOR / SV_QUERY_NO_COLOR 关闭颜色
import os as _os
if _os.environ.get("NO_COLOR") or _os.environ.get("SV_QUERY_NO_COLOR"):
    _USE_COLOR = False
