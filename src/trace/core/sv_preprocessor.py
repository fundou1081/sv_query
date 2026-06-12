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
                # 用 \b 边界确保不替换部分匹配
                line = re.sub(r"`" + macro_name + r"\b", val, line)
            new_lines.append(line)
        out[name] = "\n".join(new_lines)

    return out
