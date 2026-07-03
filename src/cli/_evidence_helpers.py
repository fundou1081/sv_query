# -*- coding: utf-8 -*-
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

def build_resolver(file: Path = None, log_level: str = "ERROR", filelist: str = None, strict: bool = False, preprocess_macros: bool = True, from_snapshot: str = None) -> tuple[TraceEvidenceResolver, Any, Any]:
    """读取 SV 源文件 -> build graph + adapter + resolver

    Args:
        file: SystemVerilog 源文件路径 (与 filelist 二选一)
        filelist: filelist 路径,用于多文件项目
        from_snapshot: [B4 2026-07-03] snapshot tag (跳过 SV parse, 跟 file/filelist 互斥)
        log_level: 编译器日志级别,CLI 默认 ERROR 静音 WARNING
        strict: True = elaboration error 立即 raise; False = 优雅降级 (默认 False, 供 evidence 走部分图)
        preprocess_macros: [Req-20 2026-06-12] 跨文件 `MACRO 展开, 避免 TooFewArguments

    Returns:
        (resolver, graph, adapter) - adapter 暴露 semantic API 给 resolver 内部用
    """
    if from_snapshot and (file or filelist):
        raise ValueError("from_snapshot is mutually exclusive with file/filelist")
    if from_snapshot:
        # [B4 2026-07-03] Build tracer from snapshot (no SV parse, no real adapter)
        from src.cli.commands.trace import _load_tracer_from_snapshot
        tracer = _load_tracer_from_snapshot(from_snapshot, log_level=log_level, strict=strict, preprocess_macros=preprocess_macros)
        graph = tracer.build_graph()
        # Snapshot 没有真 semantic adapter; 构造一个空 adapter (resolver 走 fallback)
        class _NullAdapter:
            def get_child_modules(self, *a, **kw): return []
            def get_root(self, *a, **kw): return None
        adapter = _NullAdapter()
    elif filelist:
        tracer = UnifiedTracer(filelist=filelist, log_level=log_level, strict=strict, preprocess_macros=preprocess_macros)
        graph = tracer.build_graph()
        adapter = tracer._get_adapter()
    elif file:
        with open(str(file)) as f:
            source = f.read()
        tracer = UnifiedTracer(sources={str(file): source}, log_level=log_level, strict=strict, preprocess_macros=preprocess_macros)
        graph = tracer.build_graph()
        adapter = tracer._get_adapter()
    else:
        raise ValueError("Either file, filelist, or from_snapshot must be provided")
    resolver = TraceEvidenceResolver(graph=graph, adapter=adapter)
    return resolver, graph, adapter


def make_resolver(graph, adapter) -> TraceEvidenceResolver:
    """用已有 graph + adapter 构造 resolver (避免重复 build)

    场景: 命令本身已 build 了 graph (如 verify/risk),直接复用避免再 build 一次
    """
    return TraceEvidenceResolver(graph=graph, adapter=adapter)


# ----------------------------------------------------------------------------
# 2. 序列化: Evidence / SourceSnippet -> JSON-friendly dict
# ----------------------------------------------------------------------------

def snippet_to_dict(snippet) -> dict | None:
    """SourceSnippet -> dict (Stage 4 offset-based slicing 输出)"""
    if snippet is None:
        return None
    return {
        "file": snippet.location.file,
        "line_start": snippet.location.line_start,
        "line_end": snippet.location.line_end,
        "column": snippet.location.column,
        "text": snippet.text,
    }


def evidence_to_dict(ev) -> dict | None:
    """Evidence -> dict (含 enclosing_* snippets + credibility)

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

def _ev_to_inputs(ev) -> tuple[dict | None, str] | None:
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


def evidence_summary_line(ev) -> str | None:
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


def evidence_summary_indented(ev, indent: str = "  └─ ") -> str | None:
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
# - 一行 = 一条信号链,用 -> 箭头连接
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
    """格式化信号链: ['A', 'B', 'C'] -> 'A -> B -> C'

    Args:
        signals: 信号名列表 (in order)
        conditions: 可选, 与 signals 等长或 None
        arrows: 'default' (->) / 'cond' (=>) / 'branch' (>>)
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
        # conditions[i] 是 A->B 的条件
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
    tree: bool = False,
) -> str:
    """trace fanin human 输出: 反向链, 从 source 到 signal

    drivers: [{id, kind, distance, evidence?}, ...]
    evidence_map: {signal_id: evidence_dict} 可选
    tree: True 强制竖向 tree, 链 > 6 自动转 tree
    """
    if not drivers:
        return f"{_color(signal, _ANSI_BOLD)} ← (no drivers)"

    # 按 distance 升序排序 (最远的源头在前)
    sorted_drvs = sorted(drivers, key=lambda d: d.get("distance", 0), reverse=True)

    chain = [str(signal)]
    chain.extend([d["id"] for d in sorted_drvs])
    chain.reverse()  # 现在是 [源头, ..., signal]

    # Auto tree: 链 > 6 自动转
    if should_use_tree(len(chain), tree):
        ev_text = ""
        if evidence_map:
            sig_ev = evidence_map.get(signal)
            if sig_ev:
                loc = sig_ev.get("source_location", {})
                text = sig_ev.get("source_text", "")
                if loc and text:
                    first = text.split("\n", 1)[0]
                    ev_text = f"{loc['file']}:{loc['line_start']}: {first}"
        out = render_signal_tree(
            chain,
            title=f"Fanin of {signal}",
            terminal_meta=ev_text if ev_text else None,
        )
        return out

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
                    f"  {_color('+-', _ANSI_DIM)} "
                    f"{loc['file']}:{loc['line_start']}: "
                    f"{_color(first, _ANSI_DIM)}"
                )

    return "\n".join(lines)


def format_fanout_human(
    signal: str,
    loads: list,
    evidence_map: dict = None,
    tree: bool = False,
) -> str:
    """trace fanout human 输出: 正向链, 从 signal 到 leaves"""
    if not loads:
        return f"{_color(signal, _ANSI_BOLD)} -> (no loads)"

    sorted_loads = sorted(loads, key=lambda d: d.get("distance", 0), reverse=True)

    chain = [str(signal)]
    chain.extend([d["id"] for d in sorted_loads])

    # Auto tree
    if should_use_tree(len(chain), tree):
        ev_text = ""
        if evidence_map:
            sig_ev = evidence_map.get(signal)
            if sig_ev:
                loc = sig_ev.get("source_location", {})
                text = sig_ev.get("source_text", "")
                if loc and text:
                    first = text.split("\n", 1)[0]
                    ev_text = f"{loc['file']}:{loc['line_start']}: {first}"
        out = render_signal_tree(
            chain,
            title=f"Fanout of {signal}",
            terminal_meta=ev_text if ev_text else None,
        )
        return out

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
                    f"  {_color('+-', _ANSI_DIM)} "
                    f"{loc['file']}:{loc['line_start']}: "
                    f"{_color(first, _ANSI_DIM)}"
                )

    return "\n".join(lines)


def format_dataflow_human(
    from_signal: str,
    to_signal: str,
    paths: list,
    tree: bool = False,
) -> str:
    """dataflow analyze human 输出: from -> ... -> to, 多 path 竖排

    paths: [{segments: [{from_signal, to_signal, assign_type, condition?, evidence?}], ...}, ...]

    tree: True 强制 tree, 链 > 6 自动转 tree (per path 独立判断)
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
        # 构造信号链 + 条件
        chain = [from_signal] + [seg["to_signal"] for seg in segs]
        conditions = [seg.get("condition", "").strip() for seg in segs]

        # Auto tree: 链 > 6 自动转
        if should_use_tree(len(chain), tree):
            lines.append(f"  Path {pi} (tree):")
            lines.append("    " + render_signal_tree(
                chain, conditions=conditions,
                title=None,
            ).replace("\n", "\n    "))
            lines.append("")
            continue

        # inline 模式
        lines.append(f"  Path {pi}:")
        chain_parts = [_color(from_signal, _ANSI_BOLD)]
        for seg in segs:
            cond = seg.get("condition", "").strip()
            chain_parts.append(_ARROW)
            if cond:
                chain_parts.append(f"[{_color('when ' + cond, _ANSI_MAGENTA)}]")
            chain_parts.append(_color(seg["to_signal"], _ANSI_CYAN))
        if (
            from_signal != to_signal
            and segs[-1].get("to_signal") != to_signal
        ):
            chain_parts.append(_ARROW)
            chain_parts.append(_color(to_signal, _ANSI_BOLD))
        lines.append("    " + " ".join(chain_parts))
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


def format_controlflow_human(signal: str, conditioned_drivers: list, tree: bool = False) -> str:
    """controlflow analyze human 输出: 条件 + 箭头

    支持两种数据格式 (兼容):
    - v1: [{condition, drivers: [signals], evidence?}, ...]
    - v2: [{to_node, conditions: [{expr, edge: {src, dst, kind, condition?}}]}, ...]

    输出统一: 'when EXPR: src -> dst'
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

    # Auto tree: 条件多 +6 条自动转 tree
    if should_use_tree(len(flat) + 1, tree):
        # 用 tree 渲染: 根 = signal, 子 = 每个条件 (带 [when X] 前缀)
        # 构造 children_by_node: {signal: [src1, src2, ...]}
        # 每个 src 节点染 magenta
        # children_dict: {signal: flat 中所有 src (去重保持顺序)}
        # 但条件标签需附在 src 节点后面, 不能用纯 tree
        # 所以这里用手工连线
        for f in flat:
            cond = f["cond"]
            src = f["src"]
            dst = f["dst"]
            # 用单链树 (含 when 在 terminal meta)
            chain = [src, dst]
            out = render_signal_tree(
                chain,
                title=None,
                terminal_meta=f"when {cond}",
            )
            # 缩进 + 缩进块
            for ln in out.split("\n"):
                lines.append("  " + ln)
        return "\n".join(lines)

    for f in flat:
        cond = f["cond"]
        src = f["src"]
        dst = f["dst"]
        chain = f"{_color(src, _ANSI_CYAN)} {_ARROW} {_color(dst, _ANSI_BOLD)}"
        lines.append(f"  when {_color(cond, _ANSI_MAGENTA)}: {chain}")

    return "\n".join(lines)


def format_cdc_human(cdc_paths: list, tree: bool = False) -> str:
    """cdc analyze human 输出: clk_a: A -> B (NO SYNC, HIGH risk)

    CDC 路径是 2-节点, 不会变长, tree 参数只作为一致接口 (保留扩展性)
    """
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


# ----------------------------------------------------------------------------
# 5. Tree output (--tree flag, Stage 6 part 4: 横向太长自动转竖向 tree)
# ----------------------------------------------------------------------------
#
# Tree 字符 (类 Unix 'tree' 命令):
#   |--  中间节点, 有兄弟
#   +--  未节点
#   |   纵向连接中间节点的缩进
#       (4 spaces) 未节点之后占位
#
# 示例输入: root + children = [a, b, c] (b 有子节点 [b1, b2])
#   root
#   |-- a
#   |-- b
#   |   |-- b1
#   |   +-- b2
#   +-- c

_TREE_BRANCH = "|-- "
_TREE_LAST = "+-- "
_TREE_VERTICAL = "|   "
_TREE_BLANK = "    "


def _colorize_label(label: str, kind: str = "default") -> str:
    """根据节点 role 染颜色"""
    if kind == "root":
        return _color(label, _ANSI_BOLD)
    if kind == "end":
        return _color(label, _ANSI_BOLD)
    if kind == "leaf":
        return _color(label, _ANSI_DIM)
    if kind == "middle":
        return _color(label, _ANSI_CYAN)
    if kind == "cond":
        return _color(label, _ANSI_MAGENTA)
    return label


def format_tree(
    root: str,
    children_by_node: dict = None,
    root_meta: str = None,
    leaf_meta: dict = None,
    root_kind: str = "default",
    use_color: bool = True,
) -> str:
    """渲染 tree

    Args:
        root: 根节点名
        children_by_node: {node_name: [child_names]} - 如果是单链, 可不传
        root_meta: 根节点后面的 metadata (如 '[HIGH]')
        leaf_meta: {node_name: 'meta string'} - 节点后的 metadata
        root_kind: root color hint
        use_color: False 强制关颜色 (NO_COLOR)

    Returns:
        多行 tree 字符串

    单链模式 (children_by_node=None):  root + [c1, c2, ...] 走单链
    多链模式 (children_by_node={root: [c1, c2, ...]}):  走 tree
    """
    # 单链 vs 多链 判断
    if children_by_node is None:
        # 默认单链模式:  4 个參数在调用方应该传进来, 这里只处理 root + 隐含链
        # (实测: 这个函数主要被 _render_chain 包装调用, 本身不常用)
        if root_meta:
            return f"{_colorize_label(root, root_kind)} {root_meta}"
        return _colorize_label(root, root_kind)

    def _render(node: str, prefix: str, is_last: bool, depth: int = 0, lines: list = None) -> list:
        if lines is None:
            lines = []
        connector = _TREE_LAST if is_last else _TREE_BRANCH
        # 节点 + meta
        meta_str = ""
        if depth == 0 and root_meta:
            meta_str = f"  {root_meta}"
        elif leaf_meta and node in leaf_meta and leaf_meta[node]:
            meta_str = f"  {leaf_meta[node]}"
        if depth == 0:
            kind = root_kind
        elif is_last and (node not in children_by_node or not children_by_node[node]):
            kind = "leaf"
        else:
            kind = "middle"
        label = _colorize_label(node, kind) if use_color else node
        lines.append(f"{prefix}{connector}{label}{meta_str}")
        # 子节点
        kids = children_by_node.get(node, [])
        for i, kid in enumerate(kids):
            is_last_kid = (i == len(kids) - 1)
            if is_last:
                new_prefix = prefix + _TREE_BLANK
            else:
                new_prefix = prefix + _TREE_VERTICAL
            _render(kid, new_prefix, is_last_kid, depth + 1, lines)
        return lines

    # 起始: root
    out = []
    if root_meta:
        out.append(f"{_colorize_label(root, root_kind)}  {root_meta}")
    else:
        out.append(_colorize_label(root, root_kind))
    # 渲染子节点 (不画 connector)
    kids = children_by_node.get(root, [])
    for i, kid in enumerate(kids):
        is_last = (i == len(kids) - 1)
        prefix = ""  # root 不画缩进
        # 但 connector 还是要画
        sub_lines = _render(kid, prefix, is_last, depth=1)
        out.extend(sub_lines)
    return "\n".join(out)


def render_signal_tree(
    chain: list,
    conditions: list = None,
    risk_marker: str = None,
    terminal_meta: str = None,
    title: str = None,
    use_color: bool = None,
) -> str:
    """渲染单链 tree: chain = [A, B, C] ->

    A
    |-- B
    +-- C  [HIGH]

    Args:
        chain: 信号名列表
        conditions: 可选, 与 chain-1 等长, 在 transition 处插 [when X]
        risk_marker: 尾部 risk tag (e.g. '[HIGH]')
        terminal_meta: 末尾其他 meta
        title: 可选标题 (e.g. 'Fanin of top.dout')
    """
    if not chain:
        return ""
    if use_color is None:
        use_color = _USE_COLOR

    lines = []
    if title:
        lines.append(_color(title, _ANSI_BOLD))

    # 画根 (chain[0])
    root = chain[0]
    lines.append(_colorize_label(root, "root") if use_color else root)

    # 中间 / 末尾节点
    for i, node in enumerate(chain[1:], start=1):
        is_last = (i == len(chain) - 1)
        connector = _TREE_LAST if is_last else _TREE_BRANCH
        kind = "leaf" if is_last else "middle"
        label = _colorize_label(node, kind) if use_color else node
        # meta 拼接
        meta_parts = []
        # 条件 (上一个过渡)
        if conditions and i - 1 < len(conditions) and conditions[i - 1]:
            meta_parts.append(f"[when {_color(conditions[i-1], _ANSI_MAGENTA) if use_color else conditions[i-1]}]")
        # risk / terminal meta
        if is_last and risk_marker:
            meta_parts.append(f"[{_color(risk_marker, _ANSI_RED) if use_color else risk_marker}]")
        if is_last and terminal_meta:
            meta_parts.append(terminal_meta)
        meta_str = ("  " + " ".join(meta_parts)) if meta_parts else ""
        lines.append(f"{connector}{label}{meta_str}")
    return "\n".join(lines)


# 阈值: 链 > N 节点自动转 tree
_AUTO_TREE_THRESHOLD = 6


def should_use_tree(chain_len: int, tree_flag: bool = False) -> bool:
    """是否使用 tree 格式

    Args:
        chain_len: 链节点数
        tree_flag: --tree 强制开
    """
    if tree_flag:
        return True
    return chain_len > _AUTO_TREE_THRESHOLD


# 环境变量: NO_COLOR / SV_QUERY_NO_COLOR 关闭颜色
import os as _os
if _os.environ.get("NO_COLOR") or _os.environ.get("SV_QUERY_NO_COLOR"):
    _USE_COLOR = False
