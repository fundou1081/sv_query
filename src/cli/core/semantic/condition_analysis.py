"""[iter_349 / PLAN P48] 条件局部布尔化简（L1）。

原则：
- 不改写原始 condition/conditions/condition_paths；
- 只加派生字段；解析失败/无法证明 -> unknown/incomplete；
- 不假设 4-state 下的补元律（a && !a 不化简为 0）。
"""
from __future__ import annotations


class _ParseError(ValueError):
    pass


def _tokenize(text: str) -> list[tuple[str, str]]:
    toks: list[tuple[str, str]] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if text.startswith("&&", i):
            toks.append(("op", "&&")); i += 2; continue
        if text.startswith("||", i):
            toks.append(("op", "||")); i += 2; continue
        if ch == "!" and not text.startswith("!=", i):
            toks.append(("not", "!")); i += 1; continue
        if ch == "(":
            toks.append(("lp", "(")); i += 1; continue
        if ch == ")":
            toks.append(("rp", ")")); i += 1; continue
        start = i
        while i < n:
            if text[i] in "()":
                break
            if text.startswith("&&", i) or text.startswith("||", i):
                break
            if text[i] == "!" and not text.startswith("!=", i):
                break
            i += 1
        atom = text[start:i].strip()
        if atom:
            toks.append(("atom", atom))
    return toks


class _Parser:
    def __init__(self, text: str):
        self.toks = _tokenize(text)
        self.i = 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, None)

    def take(self):
        t = self.peek()
        self.i += 1
        return t

    def parse(self):
        if not self.toks:
            raise _ParseError("empty condition")
        node = self.parse_or()
        if self.i != len(self.toks):
            raise _ParseError(f"unexpected token {self.peek()[1]!r}")
        return node

    def parse_or(self):
        node = self.parse_and()
        parts = [node]
        while self.peek() == ("op", "||"):
            self.take()
            parts.append(self.parse_and())
        return parts[0] if len(parts) == 1 else ("or", parts)

    def parse_and(self):
        node = self.parse_unary()
        parts = [node]
        while self.peek() == ("op", "&&"):
            self.take()
            parts.append(self.parse_unary())
        return parts[0] if len(parts) == 1 else ("and", parts)

    def parse_unary(self):
        if self.peek()[0] == "not":
            self.take()
            return ("not", self.parse_unary())
        if self.peek()[0] == "lp":
            self.take()
            node = self.parse_or()
            if self.peek()[0] != "rp":
                raise _ParseError("missing )")
            self.take()
            return node
        if self.peek()[0] == "atom":
            return ("atom", self.take()[1])
        raise _ParseError(f"unexpected token {self.peek()[1]!r}")


def _is_true(node) -> bool:
    return node[0] == "atom" and node[1] in ("1'b1", "1", "1'b1 ")  # normalized later


def _is_false(node) -> bool:
    return node[0] == "atom" and node[1] in ("1'b0", "0")


def _key(node):
    return _render(node)


def _simplify(node):
    kind = node[0]
    if kind == "atom":
        return node
    if kind == "not":
        child = _simplify(node[1])
        if child[0] == "not":
            return _simplify(child[1])
        if _is_true(child):
            return ("atom", "1'b0")
        if _is_false(child):
            return ("atom", "1'b1")
        return ("not", child)
    if kind == "and":
        parts = []
        for child in node[1]:
            s = _simplify(child)
            if _is_false(s):
                return ("atom", "1'b0")
            if _is_true(s):
                continue
            if s[0] == "and":
                parts.extend(s[1])
            else:
                parts.append(s)
        # dedup + absorption
        uniq = []
        seen = set()
        for p in parts:
            k = _key(p)
            if k not in seen:
                seen.add(k); uniq.append(p)
        keys = {_key(p) for p in uniq}
        kept = []
        for p in uniq:
            if p[0] == "or" and any(_key(x) in keys for x in p[1]):
                continue  # a && (a || b) -> a
            kept.append(p)
        if not kept:
            return ("atom", "1'b1")
        return kept[0] if len(kept) == 1 else ("and", kept)
    if kind == "or":
        parts = []
        for child in node[1]:
            s = _simplify(child)
            if _is_true(s):
                return ("atom", "1'b1")
            if _is_false(s):
                continue
            if s[0] == "or":
                parts.extend(s[1])
            else:
                parts.append(s)
        uniq = []
        seen = set()
        for p in parts:
            k = _key(p)
            if k not in seen:
                seen.add(k); uniq.append(p)
        keys = {_key(p) for p in uniq}
        kept = []
        for p in uniq:
            if p[0] == "and" and any(_key(x) in keys for x in p[1]):
                continue  # a || (a && b) -> a
            kept.append(p)
        if not kept:
            return ("atom", "1'b0")
        return kept[0] if len(kept) == 1 else ("or", kept)
    return node


def _prec(node) -> int:
    return {"or": 1, "and": 2, "not": 3, "atom": 4}[node[0]]


def _render(node, parent: int = 0) -> str:
    kind = node[0]
    if kind == "atom":
        text = node[1]
    elif kind == "not":
        child = node[1]
        text = "!" + _render(child, 3)
    elif kind == "and":
        text = " && ".join(_render(x, 2) for x in node[1])
    else:
        text = " || ".join(_render(x, 1) for x in node[1])
    if _prec(node) < parent:
        return f"({text})"
    return text


def analyze_condition(text: str) -> dict:
    """单条件化简。原始文本始终保留在调用方。"""
    original = text or ""
    if not original.strip():
        return {"simplified": "", "changed": False, "method": "empty",
                "confidence": "atom_identity", "four_state_safe": True,
                "tautology": False, "unsat": False,
                "analysis_incomplete": False, "error": None}
    try:
        ast = _Parser(original).parse()
        canonical = _render(ast)
        simplified = _render(_simplify(ast))
        return {"simplified": simplified,
                "changed": simplified != canonical,
                "method": "local_bool_v1", "confidence": "atom_identity",
                "four_state_safe": True,
                "tautology": simplified in ("1'b1", "1"),
                "unsat": simplified in ("1'b0", "0"),
                "analysis_incomplete": False, "error": None}
    except _ParseError as e:
        return {"simplified": original, "changed": False,
                "method": "parse_failed", "confidence": "unknown",
                "four_state_safe": False, "tautology": False, "unsat": False,
                "analysis_incomplete": True, "error": str(e)}


def _negated_pair(a: str, b: str) -> bool:
    try:
        na = _simplify(_Parser(a).parse())
        nb = _simplify(_Parser(b).parse())
    except _ParseError:
        return False

    def strip(node):
        neg = False
        while node[0] == "not":
            neg = not neg
            node = node[1]
        return node, neg

    sa, na_neg = strip(na)
    sb, nb_neg = strip(nb)
    return _key(sa) == _key(sb) and na_neg != nb_neg


def conditions_mutex(a: str, b: str) -> dict:
    """[iter_349 / PLAN P48] 语法级互斥判断。

    只证明 `a` 与 `!a` 形态；四态下 else != !cond，故 confidence 标 2state。
    """
    if _negated_pair(a, b):
        return {"mutex": True, "method": "syntactic_complement",
                "confidence": "syntactic_2state", "four_state_safe": False}
    return {"mutex": False, "method": "syntactic_complement",
            "confidence": "unknown", "four_state_safe": False}


def driver_conflict_analysis(drivers: list[dict]) -> dict:
    """多 driver 互斥状态（保守：只证明两两语法互补）。"""
    if len(drivers) <= 1:
        return {"status": "none", "method": "count", "confidence": "exact",
                "four_state_safe": True}
    conds = [d.get("condition") or "" for d in drivers]
    if any(not c for c in conds):
        return {"status": "possible", "method": "unconditional_driver",
                "confidence": "exact", "four_state_safe": True}
    for i in range(len(conds)):
        for j in range(i + 1, len(conds)):
            r = conditions_mutex(conds[i], conds[j])
            if not r["mutex"]:
                return {"status": "possible", "method": "pairwise",
                        "confidence": "unknown", "four_state_safe": False}
    return {"status": "proven_exclusive_2state",
            "method": "syntactic_complement",
            "confidence": "syntactic_2state", "four_state_safe": False}


def analyze_conditions(conditions: list[str]) -> dict:
    """多条件汇总（保留每个原始条件）。"""
    results = [analyze_condition(c) for c in conditions]
    return {
        "conditions_simplified": [r["simplified"] for r in results],
        "condition_analysis": {
            "changed": any(r["changed"] for r in results),
            "method": "local_bool_v1",
            "confidence": ("unknown" if any(r["analysis_incomplete"] for r in results)
                           else "atom_identity"),
            "four_state_safe": all(r["four_state_safe"] for r in results),
            "tautology": any(r["tautology"] for r in results),
            "unsat": bool(results) and all(r["unsat"] for r in results),
            "analysis_incomplete": any(r["analysis_incomplete"] for r in results),
        },
        "per_condition": results,
    }
