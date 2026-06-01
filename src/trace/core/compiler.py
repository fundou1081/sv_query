# ==============================================================================
# compiler.py - Semantic AST 编译入口
#
# 统一管理所有源文件的 Compilation 和 Semantic AST 获取
# 遵循铁律1: 必须使用 Semantic AST (Compilation + getRoot())
# ==============================================================================

import os
import sys

# pyslang  bindings 路径
PYSLLANG_BINDINGS_PATH = "/Users/fundou/my_dv_proj/slang/build/bindings"
if PYSLLANG_BINDINGS_PATH not in sys.path:
    sys.path.insert(0, PYSLLANG_BINDINGS_PATH)

# UVM 源码路径 (自动检测)
DEFAULT_UVM_SRC = None
for candidate in [
    os.path.expanduser("~/my_dv_proj/uvm-1.2/src"),
    os.path.expanduser("~/uvm-1.2/src"),
    "/usr/local/uvm-1.2/src",
]:
    if os.path.isfile(os.path.join(candidate, "uvm_pkg.sv")):
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

    def __init__(self, sources: dict[str, str] | None = None, log_level: str = "WARNING"):
        """
        初始化编译器

        Args:
            sources: {filename: source_code} 字典
            log_level: 诊断输出级别 (DEBUG/INFO/WARNING/ERROR/NONE)
        """
        self._sources = sources or {}
        self._comp: pyslang.Compilation | None = None
        self._root = None
        self._diagnostics = []
        self._log_level = self._parse_log_level(log_level)
        self._include_dirs: list[str] = []  # [铁律1] include 搜索路径

    def _parse_log_level(self, level: str) -> int:
        """将日志级别字符串转换为 logging 常量"""
        level_map = {
            "DEBUG": 10,
            "INFO": 20,
            "WARNING": 30,
            "ERROR": 40,
            "NONE": 100,
        }
        return level_map.get(level.upper(), 30)

    def _log(self, level: str, msg: str):
        """内部日志输出"""
        level_val = self._parse_log_level(level)
        if level_val >= self._log_level:
            print(f"[{level}] {msg}", file=sys.stderr if level == "ERROR" else sys.stdout)

    def add_source(self, filename: str, source: str):
        """添加源文件"""
        self._sources[filename] = source
        self._comp = None  # 需要重新编译

    def add_sources(self, sources: dict[str, str]):
        """批量添加源文件"""
        self._sources.update(sources)
        self._comp = None

    def add_include_dir(self, dir_path: str):
        """添加 include 搜索路径 [铁律1]"""
        if dir_path not in self._include_dirs:
            self._include_dirs.append(dir_path)
            self._comp = None

    def add_include_dirs(self, dir_paths: list[str]):
        """批量添加 include 搜索路径"""
        for d in dir_paths:
            self.add_include_dir(d)

    def add_files(self, file_paths: list[str]):
        """添加文件列表

        Args:
            file_paths: SV 源文件路径列表
        """
        for path in file_paths:
            with open(path, encoding="utf-8", errors="replace") as f:
                self._sources[os.path.basename(path)] = f.read()
        self._comp = None

    def add_filelist(self, filelist_path: str, env: dict[str, str] | None = None, already_loaded: set | None = None):
        """从文件列表加载源文件

        支持以下语法（Verilator/Modelsim 风格）:
        - 每行一个文件路径
        - +incdir+DIR        添加 include 搜索路径
        - -F FILELIST         嵌套加载另一个 filelist
        - -f FILELIST         同上 (小写)
        - +define+VAR=VAL     添加宏定义（部分支持：仅记入环境变量）
        - +libext+EXT         库扩展名（未使用，跳过）
        - ${VAR} 或 $VAR      环境变量展开
        - // 或 # 开头       注释行
        - 空行                跳过

        Args:
            filelist_path: .fl / .f / .filelist 文件路径
            env: 额外环境变量字典（会与 os.environ 合并）
            already_loaded: 已加载的 filelist 路径集合（防止循环引用）
        """
        if already_loaded is None:
            already_loaded = set()
        if env is None:
            env = {}

        filelist_path = os.path.abspath(filelist_path)
        if filelist_path in already_loaded:
            return  # 防止循环引用
        already_loaded.add(filelist_path)

        # 合并环境变量 (用户 env 覆盖系统 env)
        full_env = dict(os.environ)
        full_env.update(env)

        with open(filelist_path, encoding="utf-8") as f:
            for line in f:
                # 去除行尾注释 (// 之后到行尾的内容)
                # 但不要在 // 是路径一部分时切割
                # 简单处理：只在 // 前有空格时认为是注释
                line = line.strip()

                if not line:
                    continue
                if line.startswith("//") or line.startswith("#"):
                    continue

                # 展开环境变量 ${VAR} 或 $VAR
                line = self._expand_env(line, full_env)
                # 展开用户主目录
                line = os.path.expanduser(line)

                # +incdir+DIR - 添加 include 搜索路径
                if line.startswith("+incdir+"):
                    inc_dir = line[len("+incdir+") :].strip()
                    if os.path.isdir(inc_dir):
                        self.add_include_dir(inc_dir)
                    continue

                # +define+VAR=VAL - 宏定义（仅记入环境）
                if line.startswith("+define+"):
                    define = line[len("+define+") :].strip()
                    if "=" in define:
                        k, v = define.split("=", 1)
                        full_env[k.strip()] = v.strip()
                    else:
                        full_env[define] = "1"
                    continue

                # +libext+EXT - 库扩展名（占位，跳过）
                if line.startswith("+libext+"):
                    continue

                # -F FILELIST 或 -f FILELIST - 嵌套 filelist
                if line.startswith("-F") or line.startswith("-f"):
                    parts = line.split(None, 1)
                    if len(parts) < 2:
                        continue
                    sub_filelist = parts[1].strip()
                    if os.path.isfile(sub_filelist):
                        self.add_filelist(sub_filelist, env=full_env, already_loaded=already_loaded)
                    continue

                # 其他以 + 或 - 开头的行：跳过
                if line.startswith("+") or line.startswith("-"):
                    continue

                # 现在 line 应该是一个文件路径
                if not os.path.isabs(line):
                    dir_path = os.path.dirname(filelist_path)
                    line = os.path.join(dir_path, line)
                if os.path.isfile(line):
                    self.add_files([line])

        self._comp = None

    def _expand_env(self, text: str, env: dict[str, str]) -> str:
        """展开 ${VAR} 或 $VAR 形式的环境变量"""
        import re

        # 先展开 ${VAR} 形式
        def replace_braced(match):
            var = match.group(1)
            return env.get(var, match.group(0))

        text = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", replace_braced, text)

        # 再展开 $VAR 形式（避免匹配 $xxxx 中的 $xxxx 是普通字符）
        def replace_simple(match):
            var = match.group(1)
            return env.get(var, match.group(0))

        text = re.sub(r"\$([A-Za-z_][A-Za-z0-9_]*)", replace_simple, text)
        return text

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
            if "uvm_pkg" in source or "uvm_sequence" in source or "uvm_driver" in source:
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
                raise CompilationError(f"Failed to parse {fname}: {e}") from None

        # 触发 elaboration
        self._diagnostics = self._comp.getSemanticDiagnostics()

        # 输出所有诊断信息
        self._report_diagnostics()

        # 检查错误
        errors = [d for d in self._diagnostics if d.isError()]
        if errors:
            report = DiagnosticEngine.reportAll(self._comp.sourceManager, errors)
            raise CompilationError(f"Elaboration errors:\n{report}") from None

        # 获取 Semantic AST root
        self._root = self._comp.getRoot()

    def _report_diagnostics(self):
        """输出所有诊断信息（按级别）"""
        if not self._diagnostics:
            self._log("DEBUG", "No diagnostics")
            return

        # 按严重程度分组 (pyslang 只支持 isError)
        errors = [d for d in self._diagnostics if d.isError()]
        others = [d for d in self._diagnostics if not d.isError()]

        if errors:
            self._log("ERROR", f"{len(errors)} error(s) found")
            for d in errors:
                self._log("ERROR", self._format_diagnostic(d))
        if others:
            self._log("WARNING", f"{len(others)} warning(s)/note(s) found")
            for d in others:
                self._log("WARNING", self._format_diagnostic(d))

    def _format_diagnostic(self, diag) -> str:
        """格式化单个诊断信息"""
        # diag.args 包含 [line, column]
        args = getattr(diag, "args", [])
        code = getattr(diag, "code", None)
        code_str = str(code) if code else "unknown"
        # 提取代码名称: "DiagCode(WidthExpand)" -> "WidthExpand"
        if "DiagCode(" in code_str:
            code_name = code_str.split("(")[1].rstrip(")")
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
    def sources(self) -> dict[str, str]:
        """获取源文件字典"""
        return self._sources.copy()


# ==============================================================================
# 便捷函数
# ==============================================================================


def compile_sources(sources: dict[str, str]) -> tuple[pyslang.Compilation, any]:
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


# ==============================================================================
# 测试
# ==============================================================================

if __name__ == "__main__":
    # 测试代码
    test_source = """
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
"""

    print("=== SVCompiler 测试 ===")

    try:
        compiler = SVCompiler({"test.sv": test_source})
        comp = compiler.get_compilation()
        root = compiler.get_root()

        print("✅ Compilation 成功")
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
