#==============================================================================
# sv_compile_check.py - 检查 SV 源码是否能通过编译
#==============================================================================
"""
用于测试: 验证测试 fixture 中的 SV 源码是否能通过 Semantic AST 编译。

用法 (在测试中):
    from sim.tests.sv_compile_check import check_sv_compiles

    def test_something(self):
        source = '''
        module top(input clk, input d, output q);
            always_ff @(posedge clk) q <= d;
        endmodule
        '''
        ok, errors = check_sv_compiles(source)
        if not ok:
            self.skipTest(f"SV 语法错误 (无法编译): {errors}")

        # 正常测试 ...
"""

import sys
from pathlib import Path

# 添加 src 到 path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from trace.core.compiler import SVCompiler, CompilationError


def check_sv_compiles(source: str, filename: str = "test.sv") -> tuple[bool, str]:
    """
    检查 SV 源码是否能通过编译 (Semantic AST elaboration)。

    Args:
        source: SV 源码字符串
        filename: 虚拟文件名（用于错误报告）

    Returns:
        (True, "")                    编译成功
        (False, "<error message>")   编译失败，包含错误信息
    """
    try:
        compiler = SVCompiler({filename: source})
        compiler.get_root()  # 触发编译和 elaboration
        return True, ""
    except CompilationError as e:
        err_msg = str(e)
        # 提纯错误信息（去掉 "Elaboration errors:" 前缀和换行）
        if "Elaboration errors:" in err_msg:
            err_msg = err_msg.split("Elaboration errors:")[-1].strip()
        return False, err_msg
    except Exception as e:
        return False, str(e)


def check_sv_module(module_source: str, module_name: str = "test") -> tuple[bool, str]:
    """
    检查 SV 模块源码是否能通过编译。
    如果源码没有 module...endmodule 包装，自动包装后再检查。
    """
    source = module_source.strip()
    if not source.startswith("module "):
        source = f"module {module_name};\n{source}\nendmodule"
    return check_sv_compiles(source, f"{module_name}.sv")
