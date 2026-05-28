#==============================================================================
# compiler.py - Semantic AST 编译入口
#
# 统一管理所有源文件的 Compilation 和 Semantic AST 获取
# 遵循铁律1: 必须使用 Semantic AST (Compilation + getRoot())
#==============================================================================

import sys, os
from typing import Dict, Optional, Tuple, List

# pyslang  bindings 路径
PYSLLANG_BINDINGS_PATH = '/Users/fundou/my_dv_proj/slang/build/bindings'
if PYSLLANG_BINDINGS_PATH not in sys.path:
    sys.path.insert(0, PYSLLANG_BINDINGS_PATH)

# UVM 源码路径 (自动检测)
DEFAULT_UVM_SRC = None
for candidate in [
    os.path.expanduser('~/my_dv_proj/uvm-1.2/src'),
    os.path.expanduser('~/uvm-1.2/src'),
    '/usr/local/uvm-1.2/src',
]:
    if os.path.isfile(os.path.join(candidate, 'uvm_pkg.sv')):
        DEFAULT_UVM_SRC = candidate
        break

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
            log_level: 诊断输出级别 (DEBUG/INFO/WARNING/ERROR/NONE)
        """
        self._sources = sources or {}
        self._comp: Optional[pyslang.Compilation] = None
        self._root = None
        self._diagnostics = []
        self._log_level = self._parse_log_level(log_level)
        self._include_dirs: List[str] = []  # [铁律1] include 搜索路径
    
    def _parse_log_level(self, level: str) -> int:
        """将日志级别字符串转换为 logging 常量"""
        level_map = {
            'DEBUG': 10,
            'INFO': 20,
            'WARNING': 30,
            'ERROR': 40,
            'NONE': 100,
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

    def add_include_dir(self, dir_path: str):
        """添加 include 搜索路径 [铁律1]"""
        if dir_path not in self._include_dirs:
            self._include_dirs.append(dir_path)
            self._comp = None

    def add_include_dirs(self, dir_paths: List[str]):
        """批量添加 include 搜索路径"""
        for d in dir_paths:
            self.add_include_dir(d)
    
    def add_files(self, file_paths: List[str]):
        """添加文件列表
        
        Args:
            file_paths: SV 源文件路径列表
        """
        for path in file_paths:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                self._sources[os.path.basename(path)] = f.read()
        self._comp = None
    
    def add_filelist(self, filelist_path: str):
        """从文件列表加载源文件
        
        支持两种格式:
        - 每行一个文件路径 (相对或绝对)
        - 每行格式: +incdir+$DIR 或 -f $FILELIST 或 +define+VAR=VAL (部分支持)
        
        Args:
            filelist_path: .fl / .f / .filelist 文件路径
        """
        with open(filelist_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # 跳过 +incdir+ 和 -f 以及 +define+ 行（简化处理）
                if line.startswith('+') or line.startswith('-f'):
                    continue
                # 相对路径相对于 filelist 所在目录
                if not os.path.isabs(line):
                    dir_path = os.path.dirname(filelist_path)
                    line = os.path.join(dir_path, line)
                line = os.path.expanduser(line)
                if os.path.isfile(line):
                    self.add_files([line])
        self._comp = None
        
    def _do_compile(self):
        """执行编译 [铁律1] 使用 Semantic AST"""
        if self._comp is not None:
            return
            
        self._comp = pyslang.Compilation()
        
        # 设置 include 搜索路径
        sm = None
        include_dirs = list(self._include_dirs)
        
        # 检测是否需要 UVM (源码中有 uvm_pkg 或 uvm_ 相关引用)
        needs_uvm = False
        for source in self._sources.values():
            if 'uvm_pkg' in source or 'uvm_sequence' in source or 'uvm_driver' in source:
                needs_uvm = True
                break
        
        if needs_uvm and DEFAULT_UVM_SRC and DEFAULT_UVM_SRC not in include_dirs:
            include_dirs.append(DEFAULT_UVM_SRC)
        
        if include_dirs:
            sm = pyslang.SourceManager()
            for d in include_dirs:
                sm.addUserDirectories(d)
        
        for fname, source in self._sources.items():
            try:
                if sm:
                    tree = pyslang.SyntaxTree.fromText(source, sourceManager=sm, name=fname)
                else:
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