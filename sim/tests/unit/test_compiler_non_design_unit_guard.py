"""
test_compiler_non_design_unit_guard.py — [iter_189] 非设计单元输入不能崩进程

背景: pyslang/slang 的 `Compilation.addSyntaxTree()` 在语法树根节点是**表达式**
时 `SIGTRAP` (exit 133, 无输出、无异常, Python 侧无法捕获)。触发条件: 输入文本
不是 SystemVerilog 设计单元 → slang 走 script 模式解析成表达式。最典型的事故是
**把 filelist 当源码传** (`sv_query visualize module -f project.f`):

    content "/path/to/mod.sv\\n" → 根节点 SyntaxKind.DivideExpression → trap
    content "1 + 2"             → 根节点 SyntaxKind.AddExpression    → trap

实测合法输入的根节点是 `CompilationUnit` (多成员/空文件/仅注释/仅 `define`) 或
单个设计单元 (`ModuleDeclaration` / `ClassDeclaration` 等)。

`SVCompiler._reject_non_design_unit()` 在 `addSyntaxTree` 之前拦下"表达式根",
抛可行动的 `CompilationError`。

⚠️ 本测试若在守卫失效时会以 **SIGTRAP 打死测试进程** (不是普通 failed) —
这正是原 bug 的形态; pytest 会报 crash, 属于预期可见信号。
"""
import pytest

from trace.core.compiler import SVCompiler, CompilationError

EXPRESSION_INPUTS = {
    "filelist 内容 (路径被当源码)": "/tmp/does_not_matter/mod.sv\n",
    "裸表达式": "1 + 2\n",
    "路径拼接式内容": "a/b/c.sv\n",
}

LEGIT_INPUTS = {
    "空文件": "",
    "仅注释": "// nothing here\n",
    "仅 define": "`define FOO 1\n",
    "单 module": "module m; endmodule\n",
    "两 module": "module a; endmodule\nmodule b; endmodule\n",
    "class only": "class c; endclass\n",
    "package + module": "package p; endpackage\nmodule m; endmodule\n",
}


@pytest.mark.parametrize("name,src", sorted(EXPRESSION_INPUTS.items()))
def test_expression_root_rejected_not_crash(name, src):
    """表达式根 → 明确报错 (而不是 SIGTRAP)。"""
    comp = SVCompiler({"x.sv": src}, log_level="NONE", strict=True)
    with pytest.raises(CompilationError) as ei:
        comp.get_root()
    msg = str(ei.value)
    assert "Expression" in msg, f"错误信息应指出根节点类型, got: {msg[:120]}"
    assert "设计单元" in msg, f"错误信息应说明原因, got: {msg[:120]}"


@pytest.mark.parametrize("name,src", sorted(LEGIT_INPUTS.items()))
def test_legit_inputs_unaffected(name, src):
    """守卫不能误伤合法输入 (含空文件/仅注释/仅 define 这些"没有设计单元"的文件)。"""
    comp = SVCompiler({"x.sv": src}, log_level="NONE", strict=True)
    root = comp.get_root()  # 不抛异常即通过 (空/注释/define 文件 tops=0 是合法的)
    assert root is not None, f"{name}: root 不应为 None"


def test_module_only_file_still_compiles():
    """最常见的单文件场景 (根节点是 ModuleDeclaration) 必须照常工作。"""
    src = "module top(input logic a, output logic b); assign b = a; endmodule\n"
    comp = SVCompiler({"top.sv": src}, log_level="NONE", strict=True,
                      top_modules=["top"])
    root = comp.get_root()
    tops = list(root.topInstances)
    assert len(tops) == 1
    assert str(tops[0].name) == "top"
