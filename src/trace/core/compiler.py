#==============================================================================
# compiler.py - Semantic AST 编译入口
#
# 统一管理所有源文件的 Compilation 和 Semantic AST 获取
# 遵循铁律1: 必须使用 Semantic AST (Compilation + getRoot())
#==============================================================================

import sys
from typing import Dict, Optional, Tuple

# pyslang  bindings 路径
PYSLLANG_BINDINGS_PATH = '/Users/fundou/my_dv_proj/slang/build/bindings'
if PYSLLANG_BINDINGS_PATH not in sys.path:
    sys.path.insert(0, PYSLLANG_BINDINGS_PATH)

import pyslang
from pyslang import DiagnosticEngine


class CompilationError(Exception):
    """编译错误异常"""
    pass


class SVCompiler:
    """
    SystemVerilog 编译器 - 提供 Semantic AST 访问
    
    使用方式:
        compiler = SVCompiler({'module.sv': 'module ...'})
        root = compiler.get_root()  # Semantic AST root
        comp = compiler.get_compilation()  # Compilation 对象
    """
    
    def __init__(self, sources: Optional[Dict[str, str]] = None, log_level: str = 'WARNING'):
        """
        初始化编译器
        
        Args:
            sources: {filename: source_code} 字典
            log_level: 诊断输出级别 (DEBUG/INFO/WARNING/ERROR)
        """
        self._sources = sources or {}
        self._comp: Optional[pyslang.Compilation] = None
        self._root = None
        self._diagnostics = []
        self._log_level = self._parse_log_level(log_level)
    
    def _parse_log_level(self, level: str) -> int:
        """将日志级别字符串转换为 logging 常量"""
        level_map = {
            'DEBUG': 10,
            'INFO': 20,
            'WARNING': 30,
            'ERROR': 40,
        }
        return level_map.get(level.upper(), 30)
    
    def _log(self, level: str, msg: str):
        """内部日志输出"""
        level_val = self._parse_log_level(level)
        if level_val >= self._log_level:
            print(f"[{level}] {msg}", file=sys.stderr if level == 'ERROR' else sys.stdout)
    
    def add_source(self, filename: str, source: str):
        """添加源文件"""
        self._sources[filename] = source
        self._comp = None  # 需要重新编译
    
    def add_sources(self, sources: Dict[str, str]):
        """批量添加源文件"""
        self._sources.update(sources)
        self._comp = None
        
    def _do_compile(self):
        """执行编译"""
        if self._comp is not None:
            return
            
        self._comp = pyslang.Compilation()
        
        for fname, source in self._sources.items():
            try:
                tree = pyslang.SyntaxTree.fromText(source, fname)
                self._comp.addSyntaxTree(tree)
            except Exception as e:
                raise CompilationError(f"Failed to parse {fname}: {e}")
        
        # 触发 elaboration
        self._diagnostics = self._comp.getSemanticDiagnostics()
        
        # 输出所有诊断信息
        self._report_diagnostics()
        
        # 检查错误
        errors = [d for d in self._diagnostics if d.isError()]
        if errors:
            report = DiagnosticEngine.reportAll(self._comp.sourceManager, errors)
            raise CompilationError(f"Elaboration errors:\n{report}")
        
        # 获取 Semantic AST root
        self._root = self._comp.getRoot()
    
    def _report_diagnostics(self):
        """输出所有诊断信息（按级别）"""
        if not self._diagnostics:
            self._log('DEBUG', 'No diagnostics')
            return
        
        # 按严重程度分组 (pyslang 只支持 isError)
        errors = [d for d in self._diagnostics if d.isError()]
        others = [d for d in self._diagnostics if not d.isError()]
        
        if errors:
            self._log('ERROR', f"{len(errors)} error(s) found")
            for d in errors:
                self._log('ERROR', self._format_diagnostic(d))
        if others:
            self._log('WARNING', f"{len(others)} warning(s)/note(s) found")
            for d in others:
                self._log('WARNING', self._format_diagnostic(d))
    
    def _format_diagnostic(self, diag) -> str:
        """格式化单个诊断信息"""
        # diag.args 包含 [line, column]
        args = getattr(diag, 'args', [])
        code = getattr(diag, 'code', None)
        code_str = str(code) if code else 'unknown'
        # 提取代码名称: "DiagCode(WidthExpand)" -> "WidthExpand"
        if 'DiagCode(' in code_str:
            code_name = code_str.split('(')[1].rstrip(')')
        else:
            code_name = code_str
        
        if len(args) >= 2:
            line, column = args[0], args[1]
            return f"{line}:{column}: [{code_name}]"
        return f"[{code_name}]"
    
    def get_diagnostic_report(self) -> str:
        """获取格式化的完整诊断报告"""
        if not self._diagnostics:
            return "No diagnostics"
        
        lines = []
        for d in self._diagnostics:
            level = "ERROR" if d.isError() else "WARNING" if d.isWarning() else "INFO"
            lines.append(f"[{level}] {self._format_diagnostic(d)}")
        return "\n".join(lines)
    
    def get_compilation(self) -> pyslang.Compilation:
        """获取 Compilation 对象"""
        self._do_compile()
        return self._comp
    
    def get_root(self):
        """获取 Semantic AST root"""
        self._do_compile()
        return self._root
    
    def get_diagnostics(self):
        """获取诊断信息"""
        self._do_compile()
        return self._diagnostics
    
    @property
    def sources(self) -> Dict[str, str]:
        """获取源文件字典"""
        return self._sources.copy()


#==============================================================================
# 便捷函数
#==============================================================================

def compile_sources(sources: Dict[str, str]) -> Tuple[pyslang.Compilation, any]:
    """
    编译源文件并返回 (Compilation, Semantic AST root)

    Args:
        sources: {filename: source_code}

    Returns:
        (Compilation, root) 元组

    Example:
        >>> comp, root = compile_sources({'test.sv': 'module test(); endmodule'})
        >>> root.kind  # Semantic AST 节点
    """
    compiler = SVCompiler(sources)
    return compiler.get_compilation(), compiler.get_root()


#==============================================================================
# 测试
#==============================================================================

if __name__ == '__main__':
    # 测试代码
    test_source = '''
module test (
    input wire clk,
    input wire rst_n,
    input wire [7:0] data_in,
    output reg [7:0] data_out
);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            data_out <= 8'b0;
        else
            data_out <= data_in;
    end
endmodule
'''

    print("=== SVCompiler 测试 ===")

    try:
        compiler = SVCompiler({'test.sv': test_source})
        comp = compiler.get_compilation()
        root = compiler.get_root()

        print(f"✅ Compilation 成功")
        print(f"✅ Root 类型: {type(root).__name__}")
        print(f"✅ Root kind: {root.kind}")

        # 测试遍历 Semantic AST 节点
        nodes = []
        root.visit(lambda n: nodes.append(type(n).__name__) if n else None)

        print(f"✅ 遍历到 {len(nodes)} 个节点")
        print(f"   节点类型: {set(nodes)}")

    except CompilationError as e:
        print(f"❌ 编译错误: {e}")
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()