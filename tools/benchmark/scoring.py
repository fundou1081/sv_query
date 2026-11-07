#!/usr/bin/env python3
"""[P86] Shared scoring for structural benchmarks.

canonical: exact IDs/paths/counts.
semantic: only for neighborhood tasks, where instance/signal aliases are
accepted; direct ID-only tasks return semantic=None instead of pretending.
"""
from __future__ import annotations

import json
import re
from typing import Any


def _as_list(v: Any) -> list:
    return list(v) if isinstance(v, (list, tuple, set)) else []


def _block_ids(v: Any) -> set[str]:
    out: set[str] = set()
    for x in _as_list(v):
        if isinstance(x, str):
            out.add(x)
        elif isinstance(x, dict):
            for k in ("block", "block_id", "id", "name"):
                if isinstance(x.get(k), str):
                    out.add(x[k])
    return out


def _id_set(v: Any) -> set[str]:
    out: set[str] = set()
    for x in _as_list(v):
        if isinstance(x, str):
            out.add(x)
        elif isinstance(x, dict):
            for k in ("id", "name", "block", "block_id"):
                if isinstance(x.get(k), str):
                    out.add(x[k])
    return out


def _strings(v: Any) -> list[str]:
    out: list[str] = []
    if isinstance(v, str):
        out.append(v)
    elif isinstance(v, dict):
        for x in v.values():
            out.extend(_strings(x))
    elif isinstance(v, (list, tuple, set)):
        for x in v:
            out.extend(_strings(x))
    return out


def _canonical_value(field: str, got: Any, want: Any) -> bool:
    if field in ("path", "count"):
        return got == want
    if field in ("drivers", "loads", "mux_nodes", "selects",
                 "data_sources", "rand_vars", "condition_vars", "inherited"):
        return _id_set(got) == _id_set(want)
    if field == "constraints":
        return _block_ids(got) == _block_ids(want)
    if field == "both_addr_len_block":
        g = _strings(got)
        return bool(g) and g[0].endswith(str(want).split(".")[-1])
    return got == want


def canonical_score(task: dict, answer: dict) -> tuple[bool, dict]:
    truth = task.get("ground_truth", {})
    checks = {k: _canonical_value(k, answer.get(k), v) for k, v in truth.items()}
    return all(checks.values()), checks


def _member(s: str) -> str:
    s = s.replace("::", ".").strip()
    s = s.split(".")[-1]
    return s


def _mux_base(s: str) -> str:
    s = re.sub(r"\.ternary_sel\[[^]]*\]$", "", s)
    s = s.replace("::", ".")
    return s.split(".")[-1]


def semantic_score(task: dict, answer: dict) -> tuple[bool | None, dict | None]:
    tid = task.get("id", "")
    if tid == "complex_constraints":
        rand = {_member(x) for x in _id_set(answer.get("rand_vars"))}
        cons = {_member(x) for x in _block_ids(answer.get("constraints"))}
        conds = {_member(x) for x in _id_set(answer.get("condition_vars"))}
        conds |= {_member(x) for x in _strings(answer.get("condition_vars"))}
        inherited = {_member(x) for x in _id_set(answer.get("inherited"))}
        both = _strings(answer.get("both_addr_len_block"))
        checks = {
            "rand_vars": {"addr", "len", "mode", "payload"} <= rand,
            "constraints": {"c_len", "c_mode", "c_order"} <= cons,
            "condition": "mode" in conds,
            "coupling": bool(both) and _member(both[0]) == "c_order",
            "inherited": "c_len" in inherited,
        }
        return all(checks.values()), checks
    if tid == "mux_neighborhood":
        mux = {_mux_base(x) for x in _id_set(answer.get("mux_nodes"))}
        sel_blob = " ".join(_strings(answer.get("selects")))
        sels = set(re.findall(r"sel\[(\d+)\]", sel_blob))
        src = {_member(x) for x in _id_set(answer.get("data_sources"))}
        checks = {
            "mux_nodes": {"lo", "hi", "y"} <= mux,
            "selects": {"0", "1"} <= sels,
            "sources": {"a", "b", "c", "d"} <= src,
            "register": str(answer.get("register", "")).split(".")[-1] == "q",
        }
        return all(checks.values()), checks
    return None, None


def score_answer(task: dict, answer: dict) -> dict:
    canon, cchecks = canonical_score(task, answer)
    sem, schecks = semantic_score(task, answer)
    return {"canonical": canon, "canonical_checks": cchecks,
            "semantic": sem, "semantic_checks": schecks}
