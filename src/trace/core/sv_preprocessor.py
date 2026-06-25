"""SV Preprocessor - 跨文件宏展开

[Req-20 2026-06-12] 用户洞察: "应该把宏替换后再用语义解析"

为什么需要这个 module:
  SystemVerilog 的 macro (e.g. `define FOO 4) 在 preprocessor 层处理, 跟 semantic AST
  解耦. 但 NaplesPU 项目的 macro 引用是跨文件的 (e.g. coherence:49 用
  `DCACHE_WAY, 定义在 npu_defines.sv), 顺序敏感, 而且很多是间接宏
  (`define DCACHE_WAY `USER_DCACHE_WAY).

  pyslang 自身的 macro 展开受 include 顺序影响, 失败时报 TooFewArguments
  (e.g. $clog2(`DCACHE_WAY) → args: ['$clog2', 1, 0] 因为 `DCACHE_WAY 没展开)

  解决方案: preprocessor 跑在 pyslang 之前
    1. 跨文件收集所有 `define (resolved indirect)
    2. 在每个 .sv source 里替换 `MACRO → literal value
    3. 交给 pyslang 做完整 semantic 解析

  优势 vs 旧 syntax tree + pyslang.clog2 hack (Req-19):
    - 处理所有 system functions ($bits, $signed, $clog2 + 1, ...)
    - 处理 struct/array widths
    - elaboration 真正成功 (vs 部分 AST)
    - 复用 pyslang 而不是重新实现

  不处理:
    - `define FOO(x) (x+1) 函数式宏
    - 多行 `define (需 `define A \
                                    +1)
    - `ifdef 条件编译
    - `include 指令 (pyslang 自己处理)
    - 嵌套太深的递归 (visited set 保护)
"""

import re
from typing import Optional


# 行尾单行注释剥离
def _strip_comment(val: str) -> str:
    """strip 行尾 // 注释 (但保留 /* ... */ 跨行注释)"""
    # 简单方案: 只剥 // 行尾, 不处理 /* ... */
    return re.sub(r"\s*//.*$", "", val).strip()


# Macro value 里的 backtick 递归解析
def _resolve_macro_recursive(
    name: str,
    all_macros: dict[str, str],
    visited: Optional[set] = None,
) -> Optional[str]:
    """递归解析宏, 防止循环引用

    Returns:
        解析后的字面值 (str), 或 None (未定义/循环)
    """
    if visited is None:
        visited = set()
    if name in visited:
        return None  # 循环引用保护
    visited = visited | {name}  # 不可变 copy, 透传给递归

    if name not in all_macros:
        return None

    val = all_macros[name].strip()

    # 递归替换内部的 backtick 引用
    def replace_backtick(text: str) -> Optional[str]:
        """递归替换 `NAME, 循环/未定义 返回 None"""
        any_unresolved = False

        def _repl(m: re.Match) -> str:
            nonlocal any_unresolved
            inner = m.group(1)
            r = _resolve_macro_recursive(inner, all_macros, visited)
            if r is None:
                any_unresolved = True
                return ""  # 删掉这个 token
            return r

        out = re.sub(r"`(\w+)", _repl, text)
        if any_unresolved:
            return None
        return out

    result = replace_backtick(val)
    if result is None:
        return None
    return _strip_comment(result)


def preprocess_macros(sources: dict[str, str]) -> dict[str, str]:
    """跨文件宏展开

    Args:
        sources: {filename: source_code} 字典

    Returns:
        替换后的新 sources dict (原 dict 不变)

    Algorithm:
        1. 从所有 sources 收集 `define NAME VALUE
        2. 递归解析每个 macro (支持 indirect)
        3. 跨文件替换 `MACRO → literal value (跳过 `define 行)
    """
    # 1. 跨文件收集 macro 定义
    all_macros: dict[str, str] = {}
    for content in sources.values():
        for m in re.finditer(r"`define\s+(\w+)\s+(.+)", content):
            name, val = m.group(1), m.group(2).strip()
            all_macros[name] = val

    # 2. 递归解析, 收集 resolved 表
    resolved: dict[str, str] = {}
    for n in all_macros:
        try:
            r = _resolve_macro_recursive(n, all_macros)
            if r is not None and not r.startswith("`"):
                resolved[n] = r
        except RecursionError:
            pass  # 跳过循环引用

    # 3. 跨文件替换
    out: dict[str, str] = {}
    for name, content in sources.items():
        lines = content.split("\n")
        new_lines: list[str] = []
        for line in lines:
            # 不替换 `define 行本身
            if line.strip().startswith("`define"):
                new_lines.append(line)
                continue
            for macro_name, val in resolved.items():
                # [Bug fix 2026-06-25] 用 lambda 做 replacement, 防止 val 里的 \
                # 被 re 当作 escape sequence (e.g. val 含 \000 → bad escape).
                # CVA6 cv64a60ax_config_pkg.sv 含 `define IFNDEF_DEFINE(...)` \` 多行宏,
                # 展开后 val 含行尾 \, trigger 这个 bug.
                line = re.sub(
                    r"`" + macro_name + r"\b",
                    lambda m, _v=val: _v,
                    line,
                )
            new_lines.append(line)
        out[name] = "\n".join(new_lines)

    return out


def auto_inject_package_imports(sources: dict[str, str]) -> dict[str, str]:
    """[Bug fix 2026-06-25] 自动给 package files inject missing imports.

    CVA6 的 ariane_pkg.sv 用了 config_pkg::cva6_cfg_t 但没 import config_pkg,
    在 strict compile mode 下报 UnknownClassOrPackage.

    这个 function 检测每个 package file 的 body:
      1. 扫所有 `pkg::symbol` references
      2. 对比 file 里的 `import pkg::*;` 和 package declarations
      3. 自动 inject missing `import pkg::*;` 到 package body 顶部

    Args:
        sources: {filename: source_code}

    Returns:
        改造后的 sources dict (可能 inject import statements)
    """
    import re

    # 1. 收集所有 package declarations
    declared_packages: dict[str, str] = {}  # pkg_name -> file_path
    for path, content in sources.items():
        m = re.search(r"package\s+(\w+)\s*;", content)
        if m:
            declared_packages[m.group(1)] = path

    if not declared_packages:
        return sources

    # 2. 对每个 package file, 检测 referenced packages + 已有 imports
    out = dict(sources)  # copy
    for pkg_name, path in declared_packages.items():
        content = out[path]
        # 找 package body
        m = re.search(r"(package\s+\w+\s*;)(.*?)(endpackage)", content, re.DOTALL)
        if not m:
            continue
        header, body, footer = m.group(1), m.group(2), m.group(3)

        # 已有 import pkg::*;
        existing_imports = set(re.findall(r"import\s+(\w+)\s*::\*\s*;", body))

        # 检测 body 内的 pkg::symbol references (排除 self + 标准库)
        referenced_pkgs: set[str] = set()
        for rm in re.finditer(r"\b(\w+)::(\w+)", body):
            ref_pkg = rm.group(1)
            # 排除 self reference
            if ref_pkg == pkg_name:
                continue
            # 排除标准 SV types (logic, int, bit, etc.) + 不常见但合法标识符
            if ref_pkg in (
                "std", "uvm", "sv",  # 标准库
                "logic", "bit", "reg", "wire",  # types
            ):
                continue
            # 排除 macros 和 system functions
            if ref_pkg.startswith("$"):
                continue
            referenced_pkgs.add(ref_pkg)

        # 哪些 ref 但没 import + 实际在 filelist 里定义
        missing = referenced_pkgs - existing_imports - set(declared_packages.keys()) - {pkg_name}
        truly_missing = referenced_pkgs - existing_imports - {pkg_name}
        # 必须是 declared 的 package
        truly_missing = truly_missing & set(declared_packages.keys())

        if not truly_missing:
            continue

        # Inject `import X::*;` 到 package header 后面
        import_lines = "\n".join(f"  import {p}::*;" for p in sorted(truly_missing))
        new_header = f"{header}\n  // [auto-injected by sv_query 2026-06-25] missing imports for cross-package refs\n{import_lines}"
        new_content = content.replace(header, new_header, 1)
        out[path] = new_content
        print(f"[auto-import] {pkg_name}: injected imports for {sorted(truly_missing)}", file=__import__("sys").stderr)

    return out


def preprocess_all(
    sources: dict[str, str],
    enable_macros: bool = True,
    enable_import_injection: bool = True,
) -> dict[str, str]:
    """[新增 2026-06-25] 组合所有 preprocess phases.

    Order matters:
      1. macro 展开 (修改 source content)
      2. import injection (基于 macro 展开后的 content)
    """
    out = dict(sources)
    if enable_macros:
        out = preprocess_macros(out)
    if enable_import_injection:
        out = auto_inject_package_imports(out)
    return out
