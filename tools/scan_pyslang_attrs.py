#!/usr/bin/env python3
"""scan_pyslang_attrs.py — pyslang 属性读取清单 + 分类棘轮 (P184.1)

背景: pyslang 的 **属性 getter** 在非 UTF-8 identifier 下会抛
UnicodeDecodeError (不是 str() 转换阶段) — 必须用 `safe_attr(obj, "name", d)`
防护; `safe_str(x.name)` 无效 (实参求值即炸)。见 docs/BENCH_BASELINE.md。

本工具把"高风险属性读取"按 **receiver 类型证据** 分成三类:

  pyslang — receiver 明确是 pyslang 对象 (参数/变量 annotation、`pyslang.X()`
            构造、pyslang 返回值的字段/调用传播)。这类读取会真实触发 getter。
  wrapper — receiver 明确是 Python 层对象 (本仓 class dataclass/包装器字段、
            `self`、内建标量/容器)。读 `.name` 只是普通属性访问。
  unknown — 没有任何类型证据。**unknown 不是"大概安全"**, 是"还没人判过";
            棘轮对它同样报红, 必须补证据或在 baseline 里人工 review。

分类不使用"接收者名字长得像 pyslang"这类启发式 —— iter_182 的 50 处命中里
约 40 处就是被名字启发式骗出来的 dataclass/wrapper 噪声。

用法:
    python3 tools/scan_pyslang_attrs.py                 # 人类可读清单
    python3 tools/scan_pyslang_attrs.py --json          # 结构化清单
    python3 tools/scan_pyslang_attrs.py --hot-only      # 只看抽取热路径
    python3 tools/scan_pyslang_attrs.py --ratchet       # 用默认 baseline 拦新增
    python3 tools/scan_pyslang_attrs.py --ratchet FILE  # 指定 baseline
    python3 tools/scan_pyslang_attrs.py --write-baseline [FILE]

Ratchet 规则 (exit 1 = 失败):
  - 新的 `pyslang` 命中 (baseline `known_pyslang` 里没有, 或计数变大) = 失败;
  - 任何未 review 的 `unknown` 命中 = 失败;
  - baseline 文件缺失 / 无法解析 = 失败 (不静默跳过);
  - baseline 里已 review 的 wrapper 条目命中时按 wrapper 处理, 但也必须
    在 `reviewed_wrappers` 中逐条给出理由。

baseline 只保存**已确认的真实 pyslang getter** (`known_pyslang`) 与**人工确认的
wrapper 例外** (`reviewed_wrappers`); 历史上的 50 处启发式命中不是基线。
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Iterable

REPO = Path(__file__).resolve().parents[1]
SCAN_SCHEMA = "sv_query.pyslang_attr_scan.v1"
BASELINE_SCHEMA = "sv_query.pyslang_attr_baseline.v1"
DEFAULT_BASELINE = REPO / "tools" / "pyslang_attr_baseline.json"

# 已知会在非 UTF-8 identifier 上抛异常的属性名 (iter_182 集合, 保持稳定)
RISKY = frozenset({
    "name", "type", "symbol", "baseClass", "body", "members",
    "elementType", "arrayElementType",
})
# iter_182 的候选范围: 只检查接收者名含 pyslang 常见词的读取。P184 保留该范围
# (它决定"看哪些行"), 但分类改为类型证据; 静态可证 pyslang 的读取无论叫什么
# 名字都额外纳入候选 (typed 代码不因命名而漏检)。
PYSLANG_ISH = ("sym", "node", "inst", "top", "cls", "class", "module", "defn",
               "member", "port", "decl", "expr", "rhs", "lhs", "target", "sel",
               "item", "entry")

HOT = ("core/semantic/", "core/connection_extractor", "core/graph_builder",
       "core/driver_extractor", "core/load_extractor", "core/native_adapter",
       "core/module_instance_graph", "core/class_graph_builder")

# pyslang 对象上的 getter 若返回另一 pyslang 对象, 用于链式传播 (保守集合)
PS_OBJECT_ATTRS = frozenset({
    "symbol", "body", "members", "member", "definition", "type",
    "elementType", "arrayElementType", "baseClass", "parent", "internalSymbol",
    "target", "lhs", "rhs", "expr", "syntax", "scope", "initializer",
    "defaultValue", "port", "portConnections", "declarators", "root", "top",
})

SCALAR_NAMES = frozenset({
    "str", "int", "float", "bool", "bytes", "object", "None", "NoneType",
    "complex", "bytearray",
})
CONTAINER_NAMES = {
    "list": "list", "List": "list", "Sequence": "list", "Iterable": "list",
    "MutableSequence": "list", "set": "list", "Set": "list",
    "frozenset": "list", "FrozenSet": "list",
    "dict": "dict", "Dict": "dict", "Mapping": "dict",
    "MutableMapping": "dict", "DefaultDict": "dict",
    "tuple": "tuple", "Tuple": "tuple",
}
UNION_NAMES = frozenset({"Optional", "Union"})


# ---------------------------------------------------------------------------
# 轻量类型模型
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TypeRef:
    """类型证据的抽象表示 (只关心"是不是 pyslang 对象", 不追求完整类型系统)。"""

    kind: str  # pyslang | repo | scalar | list | dict | tuple | psmodule | repomodule | unknown
    name: str = ""
    elem: TypeRef | None = None
    key: TypeRef | None = None
    items: tuple = ()
    evidence: str = ""


UNKNOWN = TypeRef("unknown", evidence="no type evidence")


def ps_ref(name: str, evidence: str) -> TypeRef:
    return TypeRef("pyslang", name=name, evidence=evidence)


def repo_ref(key: str, evidence: str) -> TypeRef:
    return TypeRef("repo", name=key, evidence=evidence)


def scalar_ref(name: str, evidence: str) -> TypeRef:
    return TypeRef("scalar", name=name, evidence=evidence)


def list_ref(elem: TypeRef, evidence: str) -> TypeRef:
    return TypeRef("list", elem=elem, evidence=evidence)


def dict_ref(key: TypeRef, value: TypeRef, evidence: str) -> TypeRef:
    return TypeRef("dict", key=key, elem=value, evidence=evidence)


def tuple_ref(items: Iterable[TypeRef], evidence: str) -> TypeRef:
    return TypeRef("tuple", items=tuple(items), evidence=evidence)


def _shape(ref: TypeRef) -> tuple:
    """比较两个 TypeRef 的"形状" (忽略证据文本)。

    repo class 只比较类别: 分类只需要知道"不是 pyslang", 具体是哪个
    dataclass 不影响 pyslang/wrapper 判定。
    """
    if ref.kind == "list":
        return ("list", _shape(ref.elem))
    if ref.kind == "dict":
        return ("dict", _shape(ref.key), _shape(ref.elem))
    if ref.kind == "tuple":
        return ("tuple", tuple(_shape(i) for i in ref.items))
    if ref.kind == "repo":
        return ("repo",)
    return (ref.kind, ref.name)


def merge_refs(refs: Iterable[TypeRef], evidence: str) -> TypeRef:
    """合并多个来源的类型: 形状一致才保留, 否则 unknown (不猜)。"""
    informative = [r for r in refs if r.kind != "unknown"]
    if not informative:
        return UNKNOWN
    first = informative[0]
    if all(_shape(r) == _shape(first) for r in informative[1:]):
        return first
    return TypeRef("unknown", evidence=f"conflicting type evidence ({evidence})")


def fmt_ref(ref: TypeRef) -> str:
    if ref.kind == "pyslang":
        return f"pyslang.{ref.name}" if ref.name not in ("", "?") else "pyslang object"
    if ref.kind == "repo":
        return f"repo class {ref.name.split('::')[-1]}"
    if ref.kind == "scalar":
        return ref.name or "builtin"
    if ref.kind == "list":
        return f"list[{fmt_ref(ref.elem)}]"
    if ref.kind == "dict":
        return f"dict[{fmt_ref(ref.key)}, {fmt_ref(ref.elem)}]"
    if ref.kind == "tuple":
        return "tuple[" + ", ".join(fmt_ref(i) for i in ref.items) + "]"
    if ref.kind in ("psmodule", "repomodule"):
        return ref.name or ref.kind
    return "unknown"


def element_ref(ref: TypeRef, evidence: str) -> TypeRef:
    """迭代/循环变量的元素类型。"""
    if ref.kind == "list":
        return ref.elem if ref.elem is not None else UNKNOWN
    if ref.kind == "dict":
        return ref.key if ref.key is not None else UNKNOWN
    if ref.kind == "tuple":
        return merge_refs(ref.items, evidence) if len(ref.items) == 1 else UNKNOWN
    if ref.kind == "pyslang":
        return ps_ref("?", evidence)
    return UNKNOWN


# ---------------------------------------------------------------------------
# 命中 / baseline 数据结构
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Hit:
    file: str  # 相对扫描根 (POSIX)
    line: int
    column: int
    receiver: str
    attr: str
    classification: str  # pyslang | wrapper | unknown
    evidence: str
    protected: bool
    guards: tuple = ()
    candidate: bool = True

    @property
    def expr(self) -> str:
        return f"{self.receiver}.{self.attr}"

    @property
    def key(self) -> str:
        return f"{self.file}::{self.receiver}.{self.attr}"

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "receiver": self.receiver,
            "attr": self.attr,
            "expr": self.expr,
            "classification": self.classification,
            "evidence": self.evidence,
            "protected": self.protected,
            "guards": list(self.guards),
            "candidate": self.candidate,
        }


@dataclass
class Baseline:
    path: Path | None
    known_pyslang: dict[str, dict] = field(default_factory=dict)
    reviewed_wrappers: dict[str, dict] = field(default_factory=dict)

    def override_for(self, key: str) -> tuple[str, str] | None:
        if key in self.known_pyslang:
            note = self.known_pyslang[key].get("reason") or self.known_pyslang[key].get("evidence", "")
            return "pyslang", f"reviewed pyslang: {note}"
        if key in self.reviewed_wrappers:
            note = self.reviewed_wrappers[key].get("reason", "")
            return "wrapper", f"reviewed wrapper: {note}"
        return None


class BaselineError(RuntimeError):
    pass


def load_baseline(path: Path) -> Baseline:
    if not path.exists():
        raise BaselineError(f"baseline 不存在: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BaselineError(f"baseline 无法解析: {path}: {exc}") from exc
    if data.get("schema") != BASELINE_SCHEMA:
        raise BaselineError(
            f"baseline schema 不匹配: {data.get('schema')!r} != {BASELINE_SCHEMA!r}"
        )
    known: dict[str, dict] = {}
    for entry in data.get("known_pyslang", []):
        key = _entry_key(entry)
        known[key] = entry
    wrappers: dict[str, dict] = {}
    for entry in data.get("reviewed_wrappers", []):
        key = _entry_key(entry)
        wrappers[key] = entry
    return Baseline(path=path, known_pyslang=known, reviewed_wrappers=wrappers)


def _entry_key(entry: dict) -> str:
    try:
        return f"{entry['file']}::{entry['receiver']}.{entry['attr']}"
    except KeyError as exc:
        raise BaselineError(f"baseline 条目缺字段 {exc}: {entry!r}") from exc


# ---------------------------------------------------------------------------
# 仓库类型索引 (class 字段 / 方法返回 / import 映射)
# ---------------------------------------------------------------------------


@dataclass
class ClassInfo:
    key: str
    rel: str
    name: str
    node: ast.ClassDef


class RepoIndex:
    def __init__(self, root: Path, baseline: Baseline | None = None):
        self.root = root
        self.baseline = baseline or Baseline(path=None)
        self.trees: dict[str, ast.Module] = {}
        self.classes: dict[str, ClassInfo] = {}
        self.file_classes: dict[str, dict[str, str]] = {}
        self.file_funcs: dict[str, dict[str, ast.FunctionDef]] = {}
        self.file_imports: dict[str, dict[str, TypeRef]] = {}
        self._global_classes: dict[str, list[str]] = {}
        self._fields_cache: dict[str, dict[str, TypeRef]] = {}
        self._method_return_cache: dict[tuple[str, str], TypeRef] = {}
        self._method_index: dict[str, set[TypeRef]] | None = None
        self._parse_errors: dict[str, str] = {}
        self._load()

    # ---- 载入 ----

    def _load(self) -> None:
        for path in sorted(self.root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            rel = path.relative_to(self.root).as_posix()
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError) as exc:
                self.trees[rel] = None  # type: ignore[assignment]
                self.file_imports.setdefault(rel, {})
                self.file_funcs.setdefault(rel, {})
                self.file_classes.setdefault(rel, {})
                self._parse_errors[rel] = str(exc)
                continue
            self.trees[rel] = tree
            self._collect(rel, tree)

    def _collect(self, rel: str, tree: ast.Module) -> None:
        classes: dict[str, str] = {}
        funcs: dict[str, ast.FunctionDef] = {}
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                key = f"{rel}::{node.name}"
                self.classes[key] = ClassInfo(key=key, rel=rel, name=node.name, node=node)
                classes[node.name] = key
                self._global_classes.setdefault(node.name, []).append(key)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                funcs[node.name] = node
        self.file_classes[rel] = classes
        self.file_funcs[rel] = funcs
        self.file_imports[rel] = self._collect_imports(rel, tree)

    def _collect_imports(self, rel: str, tree: ast.Module) -> dict[str, TypeRef]:
        imports: dict[str, TypeRef] = {}
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    local = alias.asname or root
                    if root == "pyslang":
                        imports[local] = TypeRef("psmodule", name="pyslang")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level == 0 and module.split(".")[0] == "pyslang":
                    for alias in node.names:
                        local = alias.asname or alias.name
                        if alias.name in ("ast", "syntax", "parsing", "analysis", "driver"):
                            imports[local] = TypeRef("psmodule", name=f"pyslang.{alias.name}")
                        else:
                            imports[local] = ps_ref(
                                alias.name, f"imported pyslang.{alias.name}"
                            )
                    continue
                target = self.resolve_module(rel, module, node.level)
                if target is None:
                    continue
                for alias in node.names:
                    local = alias.asname or alias.name
                    key = self.file_classes.get(target, {}).get(alias.name)
                    if key:
                        imports[local] = repo_ref(key, f"imported {alias.name} from {target}")
                    elif alias.name in self.file_funcs.get(target, {}):
                        imports[local] = TypeRef("repomodule", name=target)
        return imports

    def resolve_module(self, rel: str, module: str, level: int) -> str | None:
        """把 import 目标解析为仓库内文件的相对路径; 解析不了返回 None。"""
        if level:
            base = PurePosixPath(rel).parent
            for _ in range(level - 1):
                base = base.parent
            parts = [p for p in module.split(".") if p]
            if not parts:
                return None
            candidate = (base / "/".join(parts)).as_posix() + ".py"
            if candidate in self.trees:
                return candidate
            init = (base / "/".join(parts)).as_posix() + "/__init__.py"
            if init in self.trees:
                return init
            return None
        if not module:
            return None
        candidate = f"{module.replace('.', '/')}.py"
        if candidate in self.trees:
            return candidate
        src_candidate = f"src/{candidate}"
        if src_candidate in self.trees:
            return src_candidate
        return None

    # ---- 名称解析 ----

    def class_key_for_name(self, rel: str, name: str) -> str | None:
        if name in self.file_classes.get(rel, {}):
            return self.file_classes[rel][name]
        imported = self.file_imports.get(rel, {}).get(name)
        if imported is not None and imported.kind == "repo":
            return imported.name
        candidates = self._global_classes.get(name, [])
        if len(candidates) == 1:
            return candidates[0]
        return None

    def class_info(self, key: str) -> ClassInfo:
        return self.classes[key]

    def bases(self, key: str) -> list[TypeRef]:
        info = self.classes[key]
        out: list[TypeRef] = []
        for base in info.node.bases:
            out.append(self.annotation(info.rel, base))
        return out

    def fields(self, key: str, _seen: set | None = None) -> dict[str, TypeRef]:
        if key in self._fields_cache:
            return self._fields_cache[key]
        _seen = _seen or set()
        if key in _seen:
            return {}
        _seen.add(key)
        info = self.classes[key]
        fields: dict[str, TypeRef] = {}
        for base in info.node.bases:
            base_ref = self.annotation(info.rel, base)
            if base_ref.kind == "repo":
                fields.update(self.fields(base_ref.name, _seen))
        params: dict[str, TypeRef] = {}
        for node in info.node.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                fields[node.target.id] = self.annotation(info.rel, node.annotation)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name != "__init__":
                    continue
                for arg in node.args.args:
                    if arg.annotation is not None:
                        params[arg.arg] = self.annotation(info.rel, arg.annotation)
                for stmt in ast.walk(node):
                    if isinstance(stmt, ast.AnnAssign) and _is_self_attr(stmt.target):
                        fields[stmt.target.attr] = self.annotation(info.rel, stmt.annotation)  # type: ignore[union-attr]
                    elif isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if _is_self_attr(target) and isinstance(stmt.value, ast.Name):
                                ref = params.get(stmt.value.id)
                                if ref is not None:
                                    fields[target.attr] = ref  # type: ignore[union-attr]
        self._fields_cache[key] = fields
        return fields

    def field_ref(self, key: str, name: str) -> TypeRef:
        fields = self.fields(key)
        return fields.get(name, UNKNOWN)

    def method(self, key: str, name: str, _seen: set | None = None):
        _seen = _seen or set()
        if key in _seen:
            return None
        _seen.add(key)
        info = self.classes.get(key)
        if info is None:
            return None
        for node in info.node.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                return (info.rel, node)
        for base in info.node.bases:
            base_ref = self.annotation(info.rel, base)
            if base_ref.kind == "repo":
                found = self.method(base_ref.name, name, _seen)
                if found is not None:
                    return found
        return None

    def method_return(self, key: str, name: str) -> TypeRef:
        cached = self._method_return_cache.get((key, name))
        if cached is not None:
            return cached
        found = self.method(key, name)
        if found is None:
            ref = UNKNOWN
        else:
            rel, node = found
            ref = self.annotation(rel, node.returns) if node.returns is not None else UNKNOWN
            if ref.kind != "unknown":
                ref = _with_evidence(
                    ref, f"call return {self.classes[key].name}.{name} -> {fmt_ref(ref)}"
                )
        self._method_return_cache[(key, name)] = ref
        return ref

    def function_return(self, rel: str, name: str) -> TypeRef:
        node = self.file_funcs.get(rel, {}).get(name)
        if node is None or node.returns is None:
            return UNKNOWN
        ref = self.annotation(rel, node.returns)
        if ref.kind == "unknown":
            return ref
        return _with_evidence(ref, f"call return {name} -> {fmt_ref(ref)}")

    def module_attr(self, rel: str, name: str) -> TypeRef:
        key = self.file_classes.get(rel, {}).get(name)
        if key:
            return repo_ref(key, f"repo class {name} in {rel}")
        func = self.file_funcs.get(rel, {}).get(name)
        if func is not None and func.returns is not None:
            return self.annotation(rel, func.returns)
        return UNKNOWN

    def methods_named(self, name: str) -> set[TypeRef]:
        if self._method_index is None:
            index: dict[str, set[TypeRef]] = {}
            for _key, info in self.classes.items():
                for node in info.node.body:
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.returns is not None:
                        ref = self.annotation(info.rel, node.returns)
                        if ref.kind != "unknown":
                            index.setdefault(node.name, set()).add(ref)
            self._method_index = index
        return self._method_index.get(name, set())

    # ---- annotation 求值 ----

    def annotation(self, rel: str, node: ast.AST | None) -> TypeRef:
        if node is None:
            return UNKNOWN
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                parsed = ast.parse(node.value, mode="eval").body
            except SyntaxError:
                return UNKNOWN
            return self.annotation(rel, parsed)
        if isinstance(node, ast.Name):
            return self._name_ref(rel, node.id, "annotation")
        if isinstance(node, ast.Attribute):
            base = self._module_ref(rel, node.value)
            if base is not None and base.kind == "psmodule":
                return ps_ref(node.attr, f"annotation pyslang.{node.attr}")
            if base is not None and base.kind == "repomodule":
                return self.module_attr(base.name, node.attr)
            return UNKNOWN
        if isinstance(node, ast.Subscript):
            head = node.value
            head_name = head.id if isinstance(head, ast.Name) else (
                head.attr if isinstance(head, ast.Attribute) else "")
            slice_node = node.slice
            if head_name in CONTAINER_NAMES:
                kind = CONTAINER_NAMES[head_name]
                if kind == "dict":
                    k, v = self._pair_refs(rel, slice_node)
                    return dict_ref(k, v, f"annotation {head_name}[...]")
                if kind == "tuple":
                    return tuple_ref(self._tuple_refs(rel, slice_node), f"annotation {head_name}[...]")
                return list_ref(self.annotation(rel, slice_node), f"annotation {head_name}[...]")
            if head_name in UNION_NAMES:
                return self._union_refs(rel, [slice_node])
            if head_name == "Annotated":
                return self.annotation(rel, slice_node.elts[0]) if isinstance(slice_node, ast.Tuple) and slice_node.elts else UNKNOWN
            return UNKNOWN
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            return merge_refs([self.annotation(rel, node.left), self.annotation(rel, node.right)], "union")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in UNION_NAMES:
            return self._union_refs(rel, node.args)
        return UNKNOWN

    def _name_ref(self, rel: str, name: str, kind: str) -> TypeRef:
        if name in SCALAR_NAMES:
            return scalar_ref(name, f"{kind} {name}")
        imported = self.file_imports.get(rel, {}).get(name)
        if imported is not None:
            if imported.kind in ("pyslang", "repo", "psmodule", "repomodule"):
                return imported
        key = self.class_key_for_name(rel, name)
        if key:
            return repo_ref(key, f"{kind} {name}")
        return UNKNOWN

    def _module_ref(self, rel: str, node: ast.AST) -> TypeRef | None:
        """把 import 别名/子模块链解析为 psmodule / repomodule。"""
        if isinstance(node, ast.Name):
            ref = self.file_imports.get(rel, {}).get(node.id)
            if ref is not None and ref.kind in ("psmodule", "repomodule"):
                return ref
            return None
        if isinstance(node, ast.Attribute):
            base = self._module_ref(rel, node.value)
            if base is not None and base.kind == "psmodule":
                return TypeRef("psmodule", name=f"{base.name}.{node.attr}")
            if base is not None and base.kind == "repomodule":
                return None
        return None

    def _pair_refs(self, rel: str, slice_node: ast.AST) -> tuple[TypeRef, TypeRef]:
        if isinstance(slice_node, ast.Tuple) and len(slice_node.elts) == 2:
            return self.annotation(rel, slice_node.elts[0]), self.annotation(rel, slice_node.elts[1])
        return UNKNOWN, UNKNOWN

    def _tuple_refs(self, rel: str, slice_node: ast.AST) -> list[TypeRef]:
        if isinstance(slice_node, ast.Tuple):
            return [self.annotation(rel, e) for e in slice_node.elts]
        return [self.annotation(rel, slice_node)]

    def _union_refs(self, rel: str, nodes: list[ast.AST]) -> TypeRef:
        refs: list[TypeRef] = []
        for node in nodes:
            if isinstance(node, ast.Tuple):
                refs.extend(self.annotation(rel, e) for e in node.elts)
            else:
                refs.append(self.annotation(rel, node))
        refs = [r for r in refs if not (r.kind == "scalar" and r.name in ("None", "NoneType"))]
        return merge_refs(refs, "union") if refs else UNKNOWN


def _is_self_attr(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    )


def _with_evidence(ref: TypeRef, evidence: str) -> TypeRef:
    return TypeRef(ref.kind, ref.name, ref.elem, ref.key, ref.items, evidence)


# ---------------------------------------------------------------------------
# 作用域求值 + 命中收集
# ---------------------------------------------------------------------------


def _guards(node: ast.Try) -> tuple:
    names: list[str] = []
    for handler in node.handlers:
        t = handler.type
        if t is None:
            names.append("Exception")  # bare except 捕获一切
        elif isinstance(t, ast.Name):
            names.append(t.id)
        elif isinstance(t, ast.Tuple):
            names.extend(e.id for e in t.elts if isinstance(e, ast.Name))
    return tuple(names)


def _legacy_candidate(receiver: ast.AST) -> bool:
    """保留 iter_182 的候选范围: receiver 是 Name/Attribute 且最后一段含常见词。

    与 iter_182 一致: 调用/下标等复合 receiver 不进候选 (旧扫描器 recv=None);
    但静态可证 pyslang 的读取仍会通过 classification 进入候选。
    """
    if isinstance(receiver, ast.Name):
        last = receiver.id
    elif isinstance(receiver, ast.Attribute):
        last = receiver.attr
    else:
        return False
    return any(k in last.lower() for k in PYSLANG_ISH)


def _is_guarded(guards: tuple) -> bool:
    return any(g in ("UnicodeDecodeError", "Exception", "BaseException") for g in guards)


class ScopeWalker(ast.NodeVisitor):
    """按执行顺序维护变量类型环境, 并记录 RISKY 属性读取。"""

    def __init__(self, index: RepoIndex, rel: str, env: dict[str, TypeRef] | None = None,
                 try_stack: list[tuple] | None = None):
        self.index = index
        self.rel = rel
        self.env: dict[str, TypeRef] = dict(env or {})
        self.assigned: set[str] = set()
        self.hits: list[Hit] = []
        self._try_stack: list[tuple] = list(try_stack or [])

    # ---- 语句 ----

    def visit_Try(self, node: ast.Try) -> None:
        guards = _guards(node)
        self._try_stack.append(guards)
        for stmt in node.body:
            self.visit(stmt)
        self._try_stack.pop()
        for handler in node.handlers:
            for stmt in handler.body:
                self.visit(stmt)
        for stmt in node.orelse + node.finalbody:
            self.visit(stmt)

    def visit_Assign(self, node: ast.Assign) -> None:
        ref = self.type_of(node.value)
        for target in node.targets:
            self._bind(target, ref)
            self.visit(target)  # 下标/属性目标里也可能有读取 (ports[node.name]=...)
        self.visit(node.value)  # 记录 RHS 里的读取

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        ref = self.index.annotation(self.rel, node.annotation)
        if node.value is not None:
            value_ref = self.type_of(node.value)
            if value_ref.kind != "unknown":
                ref = value_ref
        self._bind(node.target, ref)
        self.visit(node.target)
        if node.value is not None:
            self.visit(node.value)

    def visit_For(self, node: ast.For) -> None:
        iter_ref = self.type_of(node.iter)
        self._bind(node.target, element_ref(iter_ref, f"loop over {fmt_ref(iter_ref)}"))
        self.visit(node.iter)
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            ref = self.type_of(item.context_expr)
            if item.optional_vars is not None:
                self._bind(item.optional_vars, ref)
            self.visit(item.context_expr)
        for stmt in node.body:
            self.visit(stmt)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._scan_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._scan_function(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        key = self.index.class_key_for_name(self.rel, node.name)
        if key is None:
            return
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._scan_function(item, class_key=key)

    # ---- 推导式 ----

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._scan_comp(node.generators, [node.elt])

    visit_SetComp = visit_ListComp  # type: ignore[assignment]

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._scan_comp(node.generators, [node.elt])

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._scan_comp(node.generators, [node.key, node.value])

    def _scan_comp(self, generators, values) -> None:
        saved = dict(self.env)
        for gen in generators:
            iter_ref = self.type_of(gen.iter)
            self._bind(gen.target, element_ref(iter_ref, f"comprehension over {fmt_ref(iter_ref)}"))
            self.visit(gen.iter)
            for cond in gen.ifs:
                self.visit(cond)
        for value in values:
            self.visit(value)
        self.env = saved

    # ---- 读取 ----

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.generic_visit(node)
            return
        if node.attr in RISKY:
            receiver = ast.unparse(node.value)
            ref = self.type_of(node.value)
            classification, evidence = classify_ref(ref)
            override = self.index.baseline.override_for(f"{self.rel}::{receiver}.{node.attr}")
            if override is not None:
                classification, evidence = override
            guarded = any(_is_guarded(g) for g in self._try_stack)
            self.hits.append(Hit(
                file=self.rel,
                line=node.lineno,
                column=node.col_offset,
                receiver=receiver,
                attr=node.attr,
                classification=classification,
                evidence=evidence,
                protected=guarded,
                guards=tuple(g for g in self._try_stack for g in g),
                candidate=classification == "pyslang" or _legacy_candidate(node.value),
            ))
        self.generic_visit(node)

    # ---- 辅助 ----

    def _scan_function(self, node, class_key: str | None = None) -> None:
        env = dict(self.env)
        args = node.args
        for arg in list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs):
            if arg.annotation is not None:
                env[arg.arg] = self.index.annotation(self.rel, arg.annotation)
        if args.vararg is not None and args.vararg.annotation is not None:
            env[args.vararg.arg] = self.index.annotation(self.rel, args.vararg.annotation)
        if args.kwarg is not None and args.kwarg.annotation is not None:
            env[args.kwarg.arg] = self.index.annotation(self.rel, args.kwarg.annotation)
        if class_key is not None:
            info = self.index.classes[class_key]
            bases = self.index.bases(class_key)
            if any(b.kind == "pyslang" for b in bases):
                env["self"] = UNKNOWN
            else:
                env["self"] = repo_ref(class_key, f"self of repo class {info.name}")
        walker = ScopeWalker(self.index, self.rel, env, self._try_stack)
        for stmt in node.body:
            walker.visit(stmt)
        self.hits.extend(walker.hits)

    def _bind(self, target: ast.AST, ref: TypeRef) -> None:
        if isinstance(target, ast.Name):
            existing = self.env.get(target.id)
            if target.id in self.assigned and existing is not None:
                if ref.kind != "unknown" and existing.kind != "unknown" and _shape(existing) != _shape(ref):
                    ref = TypeRef("unknown", evidence=f"conflicting reassignment of {target.id}")
                elif ref.kind == "unknown":
                    return
            self.env[target.id] = ref
            self.assigned.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            if ref.kind == "tuple" and len(ref.items) == len(target.elts):
                for elt, item in zip(target.elts, ref.items, strict=True):
                    self._bind(elt, item)
            else:
                elem = element_ref(ref, "unpack")
                for elt in target.elts:
                    self._bind(elt, elem)
        elif isinstance(target, ast.NamedExpr):
            self._bind(target.target, ref)

    # ---- 表达式类型 ----

    def type_of(self, node: ast.AST) -> TypeRef:
        if isinstance(node, ast.Name):
            if node.id in self.env:
                return self.env[node.id]
            return self.index._name_ref(self.rel, node.id, "name")
        if isinstance(node, ast.Constant):
            if node.value is None:
                return scalar_ref("None", "literal None")
            return scalar_ref(type(node.value).__name__, f"literal {type(node.value).__name__}")
        if isinstance(node, ast.Attribute):
            base = self.type_of(node.value)
            if base.kind == "repo":
                ref = self.index.field_ref(base.name, node.attr)
                if ref.kind == "unknown":
                    return UNKNOWN
                return _with_evidence(
                    ref,
                    f"field {self.index.classes[base.name].name}.{node.attr} -> {fmt_ref(ref)}",
                )
            if base.kind == "pyslang":
                if node.attr in PS_OBJECT_ATTRS:
                    return ps_ref(node.attr, f"pyslang getter {node.attr} on {fmt_ref(base)}")
                return UNKNOWN
            if base.kind == "psmodule":
                if node.attr in ("ast", "syntax", "parsing", "analysis", "driver"):
                    return TypeRef("psmodule", name=f"{base.name}.{node.attr}")
                return ps_ref(node.attr, f"annotation pyslang.{node.attr}")
            if base.kind == "repomodule":
                return self.index.module_attr(base.name, node.attr)
            return UNKNOWN
        if isinstance(node, ast.Subscript):
            base = self.type_of(node.value)
            if base.kind in ("list", "dict"):
                return base.elem or UNKNOWN
            if base.kind == "tuple" and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, int):
                return base.items[node.slice.value] if 0 <= node.slice.value < len(base.items) else UNKNOWN
            if base.kind == "pyslang":
                return ps_ref("?", "pyslang collection element")
            return UNKNOWN
        if isinstance(node, ast.Call):
            return self._call_type(node)
        if isinstance(node, ast.IfExp):
            return merge_refs([self.type_of(node.body), self.type_of(node.orelse)], "if-expression")
        if isinstance(node, ast.BoolOp):
            return scalar_ref("bool", "bool expression")
        if isinstance(node, ast.Compare):
            return scalar_ref("bool", "comparison")
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Not):
                return scalar_ref("bool", "not expression")
            return self.type_of(node.operand)
        if isinstance(node, ast.JoinedStr):
            return scalar_ref("str", "f-string")
        if isinstance(node, ast.Dict):
            keys = [self.type_of(k) for k in node.keys if k is not None]
            vals = [self.type_of(v) for v in node.values]
            return dict_ref(
                merge_refs(keys, "dict literal"),
                merge_refs(vals, "dict literal"),
                "dict literal",
            )
        if isinstance(node, (ast.List, ast.Set)):
            return list_ref(merge_refs([self.type_of(e) for e in node.elts], "sequence literal"), "sequence literal")
        if isinstance(node, ast.Tuple):
            return tuple_ref([self.type_of(e) for e in node.elts], "tuple literal")
        if isinstance(node, ast.NamedExpr):
            ref = self.type_of(node.value)
            self._bind(node.target, ref)
            return ref
        return UNKNOWN

    def _call_type(self, node: ast.Call) -> TypeRef:
        func = node.func
        if isinstance(func, ast.Name):
            name = func.id
            if name in ("list", "sorted", "reversed", "set", "frozenset"):
                elem = self.type_of(node.args[0]) if node.args else UNKNOWN
                return list_ref(element_ref(elem, "builtin sequence"), f"builtin {name}()")
            if name == "tuple":
                elem = self.type_of(node.args[0]) if node.args else UNKNOWN
                return tuple_ref([element_ref(elem, "builtin tuple")], "builtin tuple()")
            if name == "dict":
                return dict_ref(UNKNOWN, UNKNOWN, "builtin dict()")
            if name == "enumerate":
                elem = element_ref(self.type_of(node.args[0]), "enumerate") if node.args else UNKNOWN
                return list_ref(tuple_ref([scalar_ref("int", "enumerate index"), elem], "enumerate"), "builtin enumerate()")
            if name == "zip":
                items = [element_ref(self.type_of(a), "zip") for a in node.args]
                return list_ref(tuple_ref(items, "zip"), "builtin zip()")
            if name == "getattr":
                if len(node.args) >= 3:
                    return self.type_of(node.args[2])
                return UNKNOWN
            if name in SCALAR_NAMES:
                return scalar_ref(name, f"builtin {name}()")
            if name in self.index.file_funcs.get(self.rel, {}):
                return self.index.function_return(self.rel, name)
            key = self.index.class_key_for_name(self.rel, name)
            if key:
                return repo_ref(key, f"constructor {name}()")
            imported = self.index.file_imports.get(self.rel, {}).get(name)
            if imported is not None:
                if imported.kind == "pyslang":
                    return ps_ref(imported.name, f"constructor {name}()")
                if imported.kind == "repomodule":
                    return self.index.module_attr(imported.name, name)
            return UNKNOWN
        if isinstance(func, ast.Attribute):
            base = self.type_of(func.value)
            attr = func.attr
            if base.kind == "dict":
                if attr == "get":
                    return base.elem or UNKNOWN
                if attr == "items":
                    return list_ref(tuple_ref([base.key or UNKNOWN, base.elem or UNKNOWN], "dict.items()"), "dict.items()")
                if attr == "keys":
                    return list_ref(base.key or UNKNOWN, "dict.keys()")
                if attr == "values":
                    return list_ref(base.elem or UNKNOWN, "dict.values()")
                return UNKNOWN
            if base.kind == "list":
                if attr in ("copy", "sorted"):
                    return base
                return UNKNOWN
            if base.kind == "repo":
                return self.index.method_return(base.name, attr)
            if base.kind == "pyslang":
                return ps_ref("?", f"pyslang call {attr}()")
            if base.kind == "psmodule":
                return ps_ref(attr, f"constructor pyslang.{attr}()")
            if base.kind == "repomodule":
                return self.index.module_attr(base.name, attr)
            # 兜底: 仓库内同名方法返回值一致时采用 (全仓唯一证据)
            candidates = self.index.methods_named(attr)
            if candidates:
                merged = merge_refs(candidates, f"repo methods named {attr}")
                if merged.kind != "unknown":
                    return _with_evidence(merged, f"repo-wide method {attr}() -> {fmt_ref(merged)}")
            return UNKNOWN
        return UNKNOWN


def classify_ref(ref: TypeRef) -> tuple[str, str]:
    """把 receiver 类型映射到 pyslang / wrapper / unknown。"""
    if ref.kind == "pyslang":
        return "pyslang", f"{ref.evidence or 'pyslang object'} ({fmt_ref(ref)})"
    if ref.kind in ("repo", "scalar", "list", "dict", "tuple", "psmodule", "repomodule"):
        return "wrapper", f"{ref.evidence or 'non-pyslang object'} ({fmt_ref(ref)})"
    return "unknown", ref.evidence or "no type evidence"


# ---------------------------------------------------------------------------
# 扫描入口
# ---------------------------------------------------------------------------


@dataclass
class ScanResult:
    root: Path
    hits: list[Hit]
    skipped: list[tuple[str, str]]

    @property
    def unprotected(self) -> list[Hit]:
        """默认清单: 未防护 + 属于板块候选范围的命中 (分类棘轮的作用域)。"""
        return [h for h in self.hits if not h.protected and h.candidate]

    def counts(self, hits: list[Hit] | None = None) -> dict[str, int]:
        rows = self.unprotected if hits is None else hits
        counts = {"pyslang": 0, "wrapper": 0, "unknown": 0}
        for hit in rows:
            counts[hit.classification] = counts.get(hit.classification, 0) + 1
        return counts


def scan_tree(root: Path, *, hot_only: bool = False, baseline: Baseline | None = None) -> ScanResult:
    index = RepoIndex(root, baseline)
    hits: list[Hit] = []
    skipped: list[tuple[str, str]] = []
    for rel, tree in sorted(index.trees.items()):
        if hot_only and not any(k in rel for k in HOT):
            continue
        if tree is None:
            skipped.append((rel, index._parse_errors.get(rel, "parse error")))
            continue
        walker = ScopeWalker(index, rel)
        for stmt in tree.body:
            walker.visit(stmt)
        hits.extend(walker.hits)
    hits.sort(key=lambda h: (h.file, h.line, h.column))
    return ScanResult(root=root, hits=hits, skipped=skipped)


def evaluate_ratchet(result: ScanResult, baseline: Baseline) -> list[str]:
    """返回棘轮违规 (空 = 通过)。只检查未防护的 pyslang / unknown 命中。"""
    violations: list[str] = []
    seen: dict[str, int] = {}
    for hit in result.unprotected:
        if hit.classification == "unknown":
            violations.append(f"unknown 命中未 review: {hit.file}:{hit.line}  {hit.expr}")
            continue
        if hit.classification != "pyslang":
            continue
        seen[hit.key] = seen.get(hit.key, 0) + 1
    for key, count in sorted(seen.items()):
        entry = baseline.known_pyslang.get(key)
        if entry is None:
            violations.append(f"新增 pyslang 命中 (baseline 无此项): {key}  x{count}")
            continue
        base_count = int(entry.get("count", 1))
        if count > base_count:
            violations.append(
                f"新增 pyslang 命中 (baseline {base_count} → 现在 {count}): {key}"
            )
    for rel, err in result.skipped:
        violations.append(f"无法解析, 棘轮拒绝静默跳过: {rel}: {err}")
    return violations


def write_baseline(result: ScanResult, path: Path, previous: Baseline | None = None) -> None:
    unknown = [h for h in result.unprotected if h.classification == "unknown"]
    if unknown:
        lines = "\n".join(f"  {h.file}:{h.line}  {h.expr}" for h in unknown)
        raise BaselineError(
            "拒绝写 baseline: 仍有未 review 的 unknown 命中, 先补证据或人工归类:\n" + lines
        )
    counts: dict[str, int] = {}
    evidence: dict[str, str] = {}
    parts: dict[str, tuple[str, str, str]] = {}
    for hit in result.unprotected:
        if hit.classification != "pyslang":
            continue
        counts[hit.key] = counts.get(hit.key, 0) + 1
        evidence.setdefault(hit.key, hit.evidence)
        parts.setdefault(hit.key, (hit.file, hit.receiver, hit.attr))
    known = []
    for key in sorted(counts):
        file, receiver, attr = parts[key]
        entry = {
            "file": file,
            "receiver": receiver,
            "attr": attr,
            "count": counts[key],
            "evidence": evidence[key],
        }
        if previous is not None and key in previous.known_pyslang:
            old = previous.known_pyslang[key]
            for field in ("reason", "evidence"):
                if old.get(field):
                    entry[field] = old[field]
        known.append(entry)
    wrappers = []
    if previous is not None:
        for _key, entry in sorted(previous.reviewed_wrappers.items()):
            wrappers.append(entry)
    note = (
        "只登记已确认的真实 pyslang getter (known_pyslang) 与人工 review 的 wrapper 例外 "
        "(reviewed_wrappers); 不是 iter_182 的 50 处启发式命中。"
    )
    if previous is not None and previous.path is not None and previous.path.exists():
        try:
            old_note = json.loads(previous.path.read_text(encoding="utf-8")).get("note")
            if old_note:
                note = old_note
        except (OSError, json.JSONDecodeError):
            pass
    data = {
        "schema": BASELINE_SCHEMA,
        "note": note,
        "known_pyslang": known,
        "reviewed_wrappers": wrappers,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _display_path(root: Path, rel: str) -> str:
    try:
        return (root / rel).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return f"{root.as_posix()}/{rel}"


def _print_human(result: ScanResult, root: Path) -> None:
    unprotected = result.unprotected
    counts = result.counts()
    print(f"未受保护的高风险 pyslang 属性读取: {len(unprotected)} 处")
    print(
        "分类: pyslang {pyslang} / wrapper {wrapper} / unknown {unknown} "
        "(证据见 --json; 全部命中含已防护)".format(**counts)
    )
    by_file: dict[str, list[Hit]] = {}
    for hit in unprotected:
        by_file.setdefault(hit.file, []).append(hit)
    for rel, rows in sorted(by_file.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        print(f"\n## {_display_path(root, rel)} ({len(rows)})")
        for hit in rows[:40]:
            print(
                f"   {_display_path(root, rel)}:{hit.line}  {hit.expr}  [{hit.classification}]"
            )
    if result.skipped:
        print("\n## 解析失败 (未静默忽略)")
        for rel, err in result.skipped:
            print(f"   [skip] {_display_path(root, rel)}: {err}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="扫描未受保护的 pyslang 属性读取并按 receiver 类型分类")
    ap.add_argument("--hot-only", action="store_true",
                    help="只看抽取热路径文件 (semantic/ extractors/ 等)")
    ap.add_argument("--json", action="store_true", help="输出结构化清单")
    ap.add_argument("--root", default=None, help="扫描根目录 (默认 <repo>/src)")
    ap.add_argument("--ratchet", nargs="?", const=str(DEFAULT_BASELINE), default=None,
                    metavar="BASELINE", help="与 baseline 比较, 只拦新增 pyslang / unknown")
    ap.add_argument("--check", action="store_true",
                    help="等价于 --ratchet (使用默认 baseline)")
    ap.add_argument("--write-baseline", nargs="?", const=str(DEFAULT_BASELINE), default=None,
                    metavar="PATH", help="把当前已确认的 pyslang 命中写入 baseline")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve() if args.root else (REPO / "src")
    if not root.is_dir():
        print(f"扫描根目录不存在: {root}", file=sys.stderr)
        return 1

    baseline_arg = args.ratchet if args.ratchet is not None else (str(DEFAULT_BASELINE) if args.check else None)
    if baseline_arg is None and args.write_baseline:
        candidate = Path(args.write_baseline).resolve()
        if candidate.exists():
            baseline_arg = str(candidate)
    baseline: Baseline | None = None
    baseline_path = Path(baseline_arg).resolve() if baseline_arg else None
    if baseline_path is not None:
        try:
            baseline = load_baseline(baseline_path)
        except BaselineError as exc:
            print(f"[ratchet] {exc}", file=sys.stderr)
            return 1

    result = scan_tree(root, hot_only=args.hot_only, baseline=baseline)

    if args.write_baseline:
        target = Path(args.write_baseline).resolve()
        try:
            write_baseline(result, target, baseline)
        except BaselineError as exc:
            print(f"[write-baseline] {exc}", file=sys.stderr)
            return 1
        print(f"baseline 已写入: {target}")

    violations = evaluate_ratchet(result, baseline) if baseline is not None else []

    if args.json:
        payload = {
            "schema": SCAN_SCHEMA,
            "root": root.as_posix(),
            "scope": {
                "hits": "全部 RISKY 属性读取 (含已防护/非候选), 每项带 candidate 标记",
                "ratchet": "unprotected 且 (legacy 候选名 或 静态可证 pyslang) 的命中",
            },
            "total_hits": len(result.hits),
            "unprotected": len(result.unprotected),
            "by_classification": result.counts(),
            "hits": [h.to_dict() for h in result.hits],
            "skipped": [{"file": f, "error": e} for f, e in result.skipped],
            "baseline": {
                "checked": baseline is not None,
                "path": baseline_path.as_posix() if baseline_path else None,
                "violations": violations,
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_human(result, root)
        if baseline is not None:
            if violations:
                print(f"\n[ratchet] FAIL: {len(violations)} 项")
                for v in violations:
                    print(f"   - {v}")
            else:
                print(
                    f"\n[ratchet] PASS: pyslang {result.counts()['pyslang']} 处均在 baseline "
                    f"({baseline_path.as_posix() if baseline_path else '?'}); unknown 0"
                )

    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
