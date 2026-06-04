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

def evidence_summary_line(ev) -> Optional[str]:
    """生成 1 行 evidence 摘要: 'file:line: source_text_first_line'

    返回 None 时表示没有 evidence 可显示 (resolve 失败 / 不在源文件里)
    """
    if ev is None or ev.source_location is None:
        return None
    loc = ev.source_location
    text = ev.source_text or ""
    first_line = text.split("\n", 1)[0] if text else ""
    return f"{loc.file}:{loc.line_start}: {first_line}".rstrip()


def evidence_summary_indented(ev, indent: str = "  └─ ") -> Optional[str]:
    """缩进版本,适合贴在信号下方显示"""
    line = evidence_summary_line(ev)
    if line is None:
        return None
    return f"{indent}{line}"
