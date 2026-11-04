"""[iter_367 / PLAN P65] UVM sequence/factory 静态关系。

只做源码级可证明的类角色 / registration / macro/call 关系：
- 角色由继承链判定 (uvm_sequence/uvm_component/...);
- factory registration 从类源码的 `uvm_*_utils 宏提取;
- sequence/factory call 从类源码文本提取，标注 syntactic。
不解析 UVM 运行时/factory override 语义。
"""
from __future__ import annotations

import re


_ROLE_BASES = (
    ("sequence", ("uvm_sequence",)),
    ("sequence_item", ("uvm_sequence_item", "uvm_transaction")),
    ("component", ("uvm_component", "uvm_test", "uvm_env", "uvm_agent",
                   "uvm_driver", "uvm_monitor", "uvm_scoreboard",
                   "uvm_sequencer", "uvm_subscriber")),
    ("object", ("uvm_object",)),
)

_REG_RE = re.compile(
    r"`uvm_(object|component)(?:_param)?_utils(?:_begin)?\s*\(\s*([A-Za-z_]\w*)"
)
_CREATE_RE = re.compile(
    r"\b([A-Za-z_]\w*)::type_id::create\s*\(\s*(?:\"([^\"]*)\"|([^),]+))"
)
_FACTORY_RE = re.compile(
    r"\bfactory\.(create_by_name|create_component_by_name)\s*\(\s*\"([^\"]*)\""
)
_SEQ_MACRO_RE = re.compile(r"`(uvm_do(?:_with|_pri|_item|_sequence)?)\s*\(\s*([^)]+)")
_SEQ_CALL_RE = re.compile(r"\b(start_item|finish_item)\s*\(")
_P_SEQ_RE = re.compile(r"`uvm_declare_p_sequencer\s*\(\s*([A-Za-z_]\w*)")


def _source(adapter, cls) -> str:
    try:
        return adapter.get_source_text(cls) or ""
    except Exception:
        return ""


def _line_of(text: str, offset: int, base_line: int) -> int:
    return base_line + text[:offset].count("\n")


def _role(name: str, ancestors: list[str]) -> tuple[str | None, str | None]:
    names = [name] + list(ancestors)
    for role, bases in _ROLE_BASES:
        for item in names:
            for base in bases:
                if item == base:
                    return role, base
    return None, None


def _registration(text: str, base_line: int) -> dict | None:
    m = _REG_RE.search(text)
    if not m:
        return None
    return {
        "registered": True,
        "macro": f"uvm_{m.group(1)}_utils",
        "type": m.group(2),
        "line": _line_of(text, m.start(), base_line),
        "confidence": "syntactic",
    }


def _factory_creates(text: str, base_line: int) -> list[dict]:
    out = []
    for m in _CREATE_RE.finditer(text):
        out.append({
            "kind": "type_id_create",
            "target": m.group(1),
            "instance_name": m.group(2) or (m.group(3) or "").strip(),
            "line": _line_of(text, m.start(), base_line),
            "confidence": "syntactic",
        })
    for m in _FACTORY_RE.finditer(text):
        out.append({
            "kind": m.group(1),
            "target": m.group(2),
            "instance_name": "",
            "line": _line_of(text, m.start(), base_line),
            "confidence": "syntactic",
        })
    return out


def _sequence_calls(text: str, base_line: int) -> list[dict]:
    out = []
    for m in _SEQ_MACRO_RE.finditer(text):
        out.append({
            "kind": "macro",
            "macro": f"`{m.group(1)}",
            "argument": m.group(2).strip(),
            "line": _line_of(text, m.start(), base_line),
            "confidence": "syntactic",
        })
    for m in _SEQ_CALL_RE.finditer(text):
        out.append({
            "kind": "call",
            "method": m.group(1),
            "line": _line_of(text, m.start(), base_line),
            "confidence": "syntactic",
        })
    return out


def uvm_class_info(adapter, cls, class_name: str, hierarchy) -> dict:
    ancestors = list(hierarchy.get_ancestors(class_name)) if hierarchy is not None else []
    role, base_kind = _role(class_name, ancestors)
    text = _source(adapter, cls)
    try:
        file_name, line, _, _ = adapter.get_source_location(cls)
    except Exception:
        file_name, line = "", 0
    pseq = _P_SEQ_RE.search(text)
    return {
        "role": role,
        "base_kind": base_kind,
        "is_uvm": role is not None,
        "factory_registration": _registration(text, line),
        "factory_creates": _factory_creates(text, line),
        "sequence_calls": _sequence_calls(text, line),
        "p_sequencer": pseq.group(1) if pseq else None,
        "source": {"file": file_name, "line": line},
    }
