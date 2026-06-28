# ==============================================================================
# compiler.py - Semantic AST 编译入口
#
# 统一管理所有源文件的 Compilation 和 Semantic AST 获取
# 遵循铁律1: 必须使用 Semantic AST (Compilation + getRoot())
# ==============================================================================

import os
import sys

# [A1 + A3 2026-06-28] Global quiet flag for LLM-friendly output.
# When True, all diagnostic output (warnings, info, errors) goes to /dev/null.
# Without --quiet, all non-JSON output still goes to stderr (Unix convention).
_QUIET = False


def set_quiet(quiet: bool = True) -> None:
    """Set global quiet mode for LLM consumption.

    When quiet=True, all diagnostic messages (SWAP warning, INFO logs,
    ERROR messages) are suppressed. JSON output via stdout is unaffected.

    Usage:
        from trace.core.compiler import set_quiet
        set_quiet(True)  # suppress all stderr noise
    """
    global _QUIET
    _QUIET = quiet

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


# ---------------------------------------------------------------------------
# 内存检测
# ---------------------------------------------------------------------------

def _check_memory_pressure():
    """检测系统内存压力, 如果不足输出告警.

    pyslang elaboration 在内存不足时静默失败:
      - 不报错, 不抛异常
      - 返回部分 AST (缺 module, 缺 port)
      - 部分对象 name 变为 binary garbage

    这个函数检测 swap 使用情况, 如果超过阈值就 warn.
    """
    import sys as _sys
    if _QUIET:  # [A3 2026-06-28] quiet 模式下不输出任何警告
        return
    try:
        import subprocess, re
        # macOS: 从 sysctl 获取 swap
        result = subprocess.run(
            ["sysctl", "vm.swapusage"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            m = re.search(r'used = (\d+[,.]?\d*)M', result.stdout)
            if m:
                swap_used = float(m.group(1).replace(',', '.'))
                if swap_used > 2000:  # > 2GB swap used
                    print(
                        f"[sv_query] ⚠️  SWAP 使用量 {swap_used:.0f}MB (可能内存不足)",
                        file=_sys.stderr,
                    )
                    print(
                        "[sv_query] → pyslang 在内存不足时**不会报错**, 但 elaboration",
                        file=_sys.stderr,
                    )
                    print(
                        "           可能不完整 (缺 module, binary 名字)。",
                        file=_sys.stderr,
                    )
                    print(
                        "           建议: (1) 关闭浏览器/IDE 释放内存。",
                        file=_sys.stderr,
                    )
                    print(
                        "                 (2) 或运行: python3 -c 'import time; a=bytearray(4*1024**3); time.sleep(3); del a'",
                        file=_sys.stderr,
                    )
                    print(
                        "                 强制系统回收 inactive pages, 再重试。",
                        file=_sys.stderr,
                    )
    except Exception:
        pass  # 检测失败不影响正常编译


class SVCompiler:
    """
    SystemVerilog 编译器 - 提供 Semantic AST 访问

    使用方式:
        compiler = SVCompiler({'module.sv': 'module ...'})
        root = compiler.get_root()  # Semantic AST root
        comp = compiler.get_compilation()  # Compilation 对象
    """

    def __init__(self, sources: dict[str, str] | None = None, log_level: str = "WARNING", strict: bool = True):
        """
        初始化编译器

        Args:
            sources: {filename: source_code} 字典
            log_level: 诊断输出级别 (DEBUG/INFO/WARNING/ERROR/NONE)
            strict: True (默认) 时 elaboration error 会 raise;
                    False 时优雅降级, 仍返回 partial AST (供 visualize/partial 分析用)
        """
        self._sources = sources or {}
        self._comp: pyslang.Compilation | None = None
        self._root = None
        self._diagnostics = []
        self._elaboration_errors = []  # [FIX 2026-06-11 Issue 17] 存解析出的错误, 非 strict 模式可被 snapshot 读取
        self._log_level = self._parse_log_level(log_level)
        self._include_dirs: list[str] = []  # [铁律1] include 搜索路径
        self._strict = strict  # [FIX 2026-06-11] False 时不对 elaboration error raise

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
        """内部日志输出. [A1 2026-06-28] 全部走 stderr (LLM-friendly)."""
        if _QUIET:
            return
        level_val = self._parse_log_level(level)
        if level_val >= self._log_level:
            # [A1 fix 2026-06-28] 所有 level 都走 stderr, 避免污染 stdout JSON
            print(f"[{level}] {msg}", file=sys.stderr)

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
        # [PR1 2026-06-14] 提高 generate loop step 限制 (默认 64 不够 lzc/rr_arb_tree)
        # lzc.sv 用 `for (level = 0; level < NumLevels; level++)` 加嵌套循环
        # NumLevels = 2**WIDTH, lzc WIDTH 默认 2 → 4 levels, 但 lzc 还嵌套 g_index_lut
        # 总步数 = 2 * 4 * 2 = 16 阶 → 超过默认 64 (应该是嵌套 deep 触发)
        self._comp.options.maxGenerateSteps = 1024 * 1024
        # [PR1 2026-06-14] 这些限制是 default, 增至 4M 避免模块多时触发
        self._comp.options.maxInstanceArray = 1024 * 1024
        self._comp.options.maxInstanceDepth = 1024 * 1024

        # [PR1 2026-06-14] 为 pulp axi typedef interface modules 设默认 param
        # axi_mux_intf/axi_id_remap/id_queue 默认所有 param=0 → $clog2(0) / lzc 触发 MaxGenerateStepsExceeded
        # pyslang 会预 elabor 所有 top-level modules, 所以必须设默认值
        # 注: 这些值只用于 free-floating elaboration, 实际实例化时会被覆盖
        # 注意: paramOverrides 必须重新赋值 (extend 不生效)
        # 格式: 'MODULE.PARAM=VALUE', 用 defparam 语法
        # 只在源文件包含对应模块时才设 (避免 UndeclaredIdentifier 误报)
        _has_axi_mux_intf = any('axi_mux.sv' in f for f in self._sources.keys())
        _has_id_queue = any('id_queue.sv' in f for f in self._sources.keys())
        _overrides = []
        if _has_axi_mux_intf:
            _overrides.extend([
                'axi_mux_intf.SLV_AXI_ID_WIDTH=4',
                'axi_mux_intf.MST_AXI_ID_WIDTH=4',
                'axi_mux_intf.AXI_ADDR_WIDTH=32',
                'axi_mux_intf.AXI_DATA_WIDTH=64',
                'axi_mux_intf.AXI_USER_WIDTH=0',
                'axi_mux_intf.NO_SLV_PORTS=2',
            ])
        if _has_id_queue:
            # CAPACITY=0 触发 HtCapacity=$clog2(0) → lzc WIDTH=0 → infinite loop
            _overrides.extend([
                'id_queue.ID_WIDTH=4',
                'id_queue.CAPACITY=4',
            ])
        # 注: rr_arb_tree 在全集上下文被 pyslang drop, override 会 CouldNotResolveHierarchicalPath
        # pre-elab 错误不影响实际 elaboration (使用 axi_demux_simple 的实际实例), 跳过
        # stream_arbiter/stream_arbiter_flushable N_INP=-1 → $clog2(-1) 错误
        if any('stream_arbiter.sv' in f for f in self._sources.keys()):
            _overrides.append('stream_arbiter.N_INP=4')
        if _overrides:
            self._comp.options.paramOverrides = self._comp.options.paramOverrides + _overrides

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
            # [FIX 2026-06-11] strict=False 时优雅降级: 输出错误但仍返回 partial AST
            # 让 visualize / protocol detect 在缺依赖的 opentitan 等项目仍能 work
            # [FIX 2026-06-11 Issue 17] 把 elaboration 错误存到 self._elaboration_errors
            # 供 UnifiedTracer / snapshot 读取, 标记哪些文件失败
            self._elaboration_errors = self._format_elaboration_errors(errors)
            if not self._strict:
                # [FIX 2026-06-11 Req-10] 改成不重复提示 — 错误明细已走 [ERROR] 行输出
                # stats 等 CLI 会另外接 result.elaboration_errors 输出 partial 提示
                import sys as _sys
                print(f"[sv_query] {len(errors)} error(s), continuing in non-strict mode (partial AST)", file=_sys.stderr)
            else:
                raise CompilationError(f"Elaboration errors:\n{report}") from None
        else:
            self._elaboration_errors = []

        # 获取 Semantic AST root
        self._root = self._comp.getRoot()

        # [PR1 2026-06-14] 内存不足检测: 8GB 机器上 pyslang elaboration 会因
        # swap 压力静默失败 (返回不完整 AST, 但无报错).
        # 在发现这种情况时输出告警, 提示用户关闭内存占用大的程序.
        _check_memory_pressure()

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

    def get_elaboration_errors(self) -> list[dict]:
        """[FIX 2026-06-11 Issue 17] 公开 API: 返回 elaboration 错误列表

        Returns:
            list of dict: [
                {
                    "file": "src/foo.sv",  # 源文件相对名
                    "line": 42,
                    "column": 8,
                    "code": "UndeclaredIdentifier",
                    "message": "use of undeclared identifier 'foo'",
                },
                ...
            ]
        """
        return list(self._elaboration_errors)

    def _format_elaboration_errors(self, errors: list) -> list[dict]:
        """[FIX 2026-06-11 Issue 17] 把 pyslang 诊断转结构化 dict

        pyslang v3 API: loc 是 SourceLocation, .buffer (BufferID) + .offset.
        文件名走 sm.getFileName(loc), 行/列走 sm.getLineNumber(loc)/getColumnNumber(loc).
        """
        out = []
        sm = getattr(self._comp, "sourceManager", None)
        for d in errors:
            loc = getattr(d, "location", None)
            line = col = 0
            fname = ""
            if loc is not None and sm is not None:
                # pyslang v3 getFileName 接受 SourceLocation, 不是 BufferID
                try:
                    fname = sm.getFileName(loc) or ""
                except Exception:
                    pass
                if not fname:
                    try:
                        fname = sm.getRawFileName(loc) or ""
                    except Exception:
                        pass
                # 行号 / 列号
                try:
                    line = sm.getLineNumber(loc) or 0
                except Exception:
                    pass
                try:
                    col = sm.getColumnNumber(loc) or 0
                except Exception:
                    pass
            code = getattr(d, "code", None)
            code_str = str(code) if code else "unknown"
            # 提取代码名: "DiagCode(UndeclaredIdentifier)" -> "UndeclaredIdentifier"
            if "(" in code_str and code_str.endswith(")"):
                code_str = code_str.split("(", 1)[1].rstrip(")")
            # [ADD 2026-06-12 Req-18] 从 diag.args 抽未定义名 (e.g. ['undefined_typedef'])
            # 让 fix imports 等工具能精准定位该补哪个 typedef/module
            args = getattr(d, "args", []) or []
            identifier = None
            if args and isinstance(args[0], str):
                identifier = args[0]
            out.append({
                "file": fname,
                "line": line,
                "column": col,
                "code": code_str,
                "message": self._format_diagnostic(d).strip(),
                "identifier": identifier,  # 未定义的标识符名 (e.g. 'service_message_t')
            })
        return out

    def _format_diagnostic(self, diag) -> str:
        """格式化单个诊断信息

        输出格式: <file>:<line>:<col>: [<code>] <message>
        其中 file/line/col 从 diag.location 抽, code 从 diag.code 抽, message 走 DiagCode.formatted.
        """
        args = getattr(diag, "args", [])
        code = getattr(diag, "code", None)
        code_str = str(code) if code else "unknown"
        # 提取代码名称: "DiagCode(WidthExpand)" -> "WidthExpand"
        if "DiagCode(" in code_str:
            code_name = code_str.split("(")[1].rstrip(")")
        else:
            code_name = code_str

        # [FIX 2026-06-11 Req-10] 从 diag.location 抽 file:line:col
        loc = getattr(diag, "location", None)
        loc_str = ""
        if loc is not None and self._comp is not None:
            try:
                sm = self._comp.sourceManager
                fname = sm.getFileName(loc) or sm.getRawFileName(loc) or ""
                line = sm.getLineNumber(loc) or 0
                col = sm.getColumnNumber(loc) or 0
                if fname:
                    loc_str = f"{fname}:{line}:{col}: "
            except Exception:
                pass
        if not loc_str and len(args) >= 2:
            # 回退: 从 args 拿 line/col
            loc_str = f"{args[0]}:{args[1]}: "

        return f"{loc_str}[{code_name}]"

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
