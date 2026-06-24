#!/usr/bin/env python3
"""
coverage_gen_demo.py — Phase 1 POC

用 sv_query 现有信息 (risk --json) 自动生成 SystemVerilog covergroup。

输入: RTL 源文件 + 目标信号名 (+ 可选 filelist, related signals, module name)
输出: 完整 covergroup (含 sample 条件, bins, cross)

策略:
  - DATA 信号 (width >= 8): 范围分 bin (zero/low/mid/high/max)
  - CONTROL 信号 (width < 8 或名字含 valid/ready/state/...): 离散 bin
  - cross: 主信号 x 相关 control 信号 (mode, valid 等)
  - sample 条件: 保守推断 (VLD/control/data reg 启发式; 推断不到不加 iff)

用法:
  # 单文件模式
  python tools/coverage_gen_demo.py <file.sv> <signal> [<related> ...]
  例: python tools/coverage_gen_demo.py sim/openTitan_validation.sv state_q mode_i valid_i

  # 多文件 filelist 模式 (Verilator/Modelsim 风格, 复用 sv_query _read_filelist)
  python tools/coverage_gen_demo.py --filelist=<project.f> <top.sv> <signal> [<related> ...]
  例: python tools/coverage_gen_demo.py --filelist=project.f top.sv data_o valid_i

  # filelist 也能用 .f/.fl 作第一个 positional (auto-detect)
  python tools/coverage_gen_demo.py <project.f> <top.sv> <signal> [<related> ...]

  # RTL 错误时用 --no-strict (sv_query graceful degradation)
  python tools/coverage_gen_demo.py sim/test_comprehensive.sv q d --no-strict

  # 多 module 文件限定到具体 module
  python tools/coverage_gen_demo.py sim/test_comprehensive.sv q d --no-strict --module=seq_basic

  # 多文件 + +incdir+ (Verilator 风格, 从 filelist 自动提)
  # 依赖 sv_query 0.6+ (risk analyze 支持 --include/-I flag)
  python tools/coverage_gen_demo.py --filelist=project.f top.sv data_o enable_i

  # 手动加 include path (逗号分隔, 跟其他 sv_query CLI 一致)
  python tools/coverage_gen_demo.py sim/logger.sv events_counter --include=/path/inc1,/path/inc2
"""
import json
import os
import re
import sys
from pathlib import Path

# 复用 sv_query 的 filelist 解析器 (Verilator/Modelsim 风格)
# 支持 -F 嵌套, +incdir+, ${VAR} 展开等
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
try:
    from cli._common import _read_filelist
    _HAS_FILELIST = True
except ImportError:
    _HAS_FILELIST = False


def read_all_sources(
    file: str | None = None,
    filelist: str | None = None,
) -> tuple[dict[str, str], list[str], list[str]]:
    """
    读所有源文件返回 (sources, paths, include_dirs).
    - file + filelist 都没给 → raise
    - file 给, filelist 没给 → sources = {file: content}, paths = [file]
    - filelist 给 → 用 _read_filelist 读多文件, file 作为主 RTL 解析文件
    Returns:
        sources: {绝对路径: 文件内容}
        paths: 用于 RTL regex 解析的路径列表 (file + filelist 内所有文件)
        include_dirs: 从 filelist +incdir+ 解析的 include 路径
    """
    if not file and not filelist:
        raise ValueError("Either --file or --filelist is required")
    include_dirs = []
    if filelist:
        if not _HAS_FILELIST:
            raise RuntimeError("filelist support requires src/cli/_common.py (run from project root)")
        base = Path.cwd()
        # 解析 filelist 拿 +incdir+ (sv_query._read_filelist 不解析这些)
        include_dirs = _parse_filelist_incdirs(filelist, base)
        sources = _read_filelist(filelist, base_dir=base)
        paths = list(sources.keys())
        if file and file not in paths:
            try:
                sources[file] = Path(file).read_text(encoding="utf-8", errors="replace")
            except FileNotFoundError:
                pass
            paths.insert(0, file)
    else:
        sources = {file: Path(file).read_text(encoding="utf-8", errors="replace")}
        paths = [file]
    return sources, paths, include_dirs


def _parse_filelist_incdirs(filelist_path: str, base_dir: Path) -> list[str]:
    """从 filelist 里提取 +incdir+DIR 路径 (sv_query._read_filelist 不解析这些).
    返回绝对路径列表.
    """
    incdirs = []
    try:
        with open(filelist_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("//") or line.startswith("#"):
                    continue
                if line.startswith("+incdir+"):
                    raw = line[len("+incdir+"):].strip()
                    # 解析环境变量
                    raw = os.path.expandvars(raw)
                    # 转绝对路径 (相对 base_dir)
                    p = Path(raw)
                    if not p.is_absolute():
                        p = (base_dir / p).resolve()
                    else:
                        p = p.resolve()
                    if p.exists() and p.is_dir():
                        incdirs.append(str(p))
    except (FileNotFoundError, OSError):
        pass
    return incdirs


# =============================================================================
# Step 1: 用 sv_query risk --json 拿信号元信息
# =============================================================================
def query_risk_json(
    file: str | None = None,
    filelist: str | None = None,
    include_dirs: list[str] | None = None,
    strict: bool = True,
) -> dict:
    import subprocess
    args = ["python", "run_cli.py", "risk", "analyze", "--json"]
    # filelist 模式下不传 -f (避免 sv_query 重复加载 source 冲突)
    # file 只用于 RTL regex 解析 (width/typedef/param)
    if filelist:
        args += ["--filelist", filelist]
    elif file:
        args += ["-f", file]
    if include_dirs:
        args += ["--include", ",".join(include_dirs)]
    if not strict:
        args.append("--no-strict")
    out = subprocess.run(
        args, capture_output=True, text=True, cwd=Path(__file__).parent.parent,
    )
    start = out.stdout.find("{")
    if start < 0:
        raise RuntimeError(f"risk analyze --json returned no JSON:\n{out.stdout[:500]}")
    return json.loads(out.stdout[start:])["result"]


def find_signal(sig_name: str, data_signals: list) -> dict | None:
    for s in data_signals:
        # sv_query 报 "state_q[2:0]" 这种带 bit-select, normalize 匹配
        bare = re.sub(r"\[.*?\]", "", s["name"])
        if bare == sig_name:
            return s
    return None


def find_signal_in_module(sig_name: str, data_signals: list, module_name: str) -> dict | None:
    """从指定 module 里找 signal (通过 node_id 前缀匹配)"""
    for s in data_signals:
        node_id = s.get("node_id", "")
        # node_id 格式: "module.signal" (e.g. "seq_basic.q")
        if node_id.startswith(f"{module_name}."):
            bare = re.sub(r"\[.*?\]", "", s["name"])
            if bare == sig_name:
                return s
    return None


# =============================================================================
# Step 2: 从 RTL 拿精确 width (sv_query 简化成 1, 这里补回真实 width)
# =============================================================================
def parse_parameters(file_or_paths) -> dict[str, int]:
    """解析 module 的 parameter 声明 (例如 parameter WIDTH = 8).
    file_or_paths 可以是 str (单文件) 或 list[str] (多文件, 合并 parameters).
    """
    paths = [file_or_paths] if isinstance(file_or_paths, str) else file_or_paths
    params = {}
    for f in paths:
        try:
            src = Path(f).read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            continue
        for m in re.finditer(r"(?:parameter|localparam)\s+(?:\w+\s+)?(\w+)\s*=\s*(\d+)", src):
            name, val = m.group(1), int(m.group(2))
            if name not in params:  # first-wins (避免后续 header override)
                params[name] = val
    return params


def _resolve_width_expr(expr: str, params: dict[str, int]) -> str:
    """把 [WIDTH-1:0] 这种表达式中的参数替换为字面量"""
    for name, val in params.items():
        expr = re.sub(rf"\b{name}\b", str(val), expr)
    return expr


def _eval_simple_expr(expr: str) -> int | None:
    """评估 '8-1' / 'WIDTH' / '7' 这种简单表达式 (仅整数运算)"""
    expr = expr.strip()
    if expr.isdigit():
        return int(expr)
    try:
        return int(eval(expr, {"__builtins__": {}}, {}))
    except Exception:
        return None


def _parse_logic_type_str(type_str: str) -> tuple[int, int] | None:
    """从 pyslang type 字符串拿 (hi, lo) width.
    支持:
      - 'logic' / 'bit' / 'reg' → 1-bit
      - 'logic[N:M]' (1D vector)
      - 'logic[N:M][K:L]' (2D nested, 取外层 bit 范围)
      - 'logic[N:M]$[0:X]' (unpacked array, 取 packed 维度)
    不支持 (返回 None):
      - 'types_pkg::foo' (package typedef, 需要 lookup 包装)
      - packed struct/union (无 bit range)
    """
    if not type_str:
        return None
    s = type_str.strip()
    if s in ("logic", "bit", "reg"):
        return (0, 0)  # 1-bit
    # 嵌套: 'logic[N:M][K:L]' (packed) or 'logic[N:M]$[0:X]' (unpacked 后缀)
    # 匹配第一个 [N:M]
    m = re.search(r"^(?:logic|bit|reg)\s*\[(\d+):(\d+)\]", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def _resolve_typedef(name: str, compilation, module_body=None) -> str | None:
    """递归解析 typedef (package + module scope). 返回 underlying type 字符串.
    name 格式: 'pkg::foo' 或 'module::foo' 或 'foo'.
    module_body: 如果给, 同时查 module-scope typedef (e.g. 'pyslang_types.local_word_t').
    """
    if "::" in name:
        pkg_name, type_name = name.split("::", 1)
        try:
            pkg = compilation.getPackage(pkg_name)
        except Exception:
            pkg = None
        if pkg is not None:
            sym = pkg.find(type_name)
            if sym is not None:
                ct = getattr(sym, "canonicalType", None)
                if ct is not None:
                    return str(ct)
    # module-scope typedef: 名称格式 'module_name.type_name' 或裸 'type_name'
    if module_body is not None:
        # type_name 是 name 最后一段 (after :: 或 .)
        type_name = re.split(r"::|\.", name)[-1]
        try:
            sym = module_body.find(type_name)
        except Exception:
            sym = None
        if sym is not None:
            ct = getattr(sym, "canonicalType", None)
            if ct is not None:
                return str(ct)
    return None


def parse_width_from_pyslang(
    sig_name: str,
    file: str | None = None,
    filelist: str | None = None,
    module_name: str | None = None,
    include_dirs: list[str] | None = None,
) -> tuple[int, int, int] | None:
    """用 sv_query + pyslang 拿 signal 的真实 width (包括 $clog2 / package typedef).
    返回 (width, hi, lo) 或 None (拿不到 / 跨 module / packed struct).
    """
    try:
        from cli._common import _build_tracer
    except ImportError:
        return None
    try:
        from pathlib import Path as P
        tracer = _build_tracer(
            file=P(file) if file else None,
            filelist=filelist,
            strict=False,
            include_dirs=include_dirs,
        )
        tracer.build_graph()
    except Exception:
        return None
    root = tracer._compiler.get_root()
    compilation = tracer._compiler.get_compilation()
    # 找 module instance
    for inst in root.topInstances if hasattr(root, "topInstances") else []:
        if module_name and inst.name != module_name:
            continue
        body = inst.body
        # 拿 sym (port 或 internal)
        sym = None
        # 1) 顶层 portList
        if hasattr(body, "portList") and body.portList:
            for p in body.portList:
                if p.name == sig_name:
                    sym = p
                    break
        # 2) 内部 signals
        if sym is None:
            try:
                sym = body.find(sig_name)
            except Exception:
                sym = None
        if sym is None:
            continue
        # 拿 type 字符串
        t = getattr(sym, "type", None) or getattr(sym, "declaredType", None)
        type_str = str(t) if t else ""
        # 直接 1D logic
        r = _parse_logic_type_str(type_str)
        if r is not None:
            hi, lo = r
            return hi - lo + 1, hi, lo
        # typedef (package scope) — 'pkg::foo' 或 'module::foo' 或 'module_name.type_name'
        if "::" in type_str or "." in type_str:
            resolved = _resolve_typedef(type_str, compilation, module_body=body)
            if resolved:
                # 处理 enum / struct / logic
                r2 = _parse_logic_type_str(resolved)
                if r2 is not None:
                    hi, lo = r2
                    return hi - lo + 1, hi, lo
                # enum: 用 'enum{' 开头 → 找所有 enum value 拿 max
                if resolved.startswith("enum{"):
                    import math
                    all_vals = re.findall(r"=\s*\d+'[dbh](\d+)", resolved)
                    if all_vals:
                        max_val = max(int(v) for v in all_vals)
                        w = max(1, math.ceil(math.log2(max_val + 1)))
                        return w, w - 1, 0
                    return 2, 1, 0  # fallback
                # packed union 先匹配 (可能含 nested struct packed)
                if "union packed" in resolved:
                    bit_widths = [int(b) + 1 for b in re.findall(r"\[(\d+):0\]", resolved)]
                    if bit_widths:
                        m = max(bit_widths)
                        return m, m - 1, 0
                # packed struct: 'struct packed{logic[7:0] opcode;logic[23:0] addr;}...'
                if "struct packed" in resolved:
                    # 累加所有 logic[K:0] 字段
                    bit_widths = [int(b) + 1 for b in re.findall(r"\[(\d+):0\]", resolved)]
                    if bit_widths:
                        total = sum(bit_widths)
                        return total, total - 1, 0
    return None


def parse_width_from_rtl(sig_name: str, file_or_paths) -> tuple[int, int, int]:
    """返回 (width, hi, lo). file_or_paths 可以是 str 或 list[str]."""
    paths = [file_or_paths] if isinstance(file_or_paths, str) else file_or_paths
    params = parse_parameters(paths)
    # 合并所有文件内容
    combined_src = ""
    for f in paths:
        try:
            combined_src += "\n" + Path(f).read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            continue
    # 匹配多种位宽声明: logic [N:M] / reg [N:M] / wire [N:M] / input/output [N:M] / 参数化 [WIDTH-1:0]
    patterns = [
        rf"(?:input|output|inout)\s+(?:logic\s+)?\[([^\]]+)\]\s+(?:\w+\s+)*{re.escape(sig_name)}\b",
        rf"(?:logic|reg|wire)\s*\[([^\]]+)\]\s+(?:\w+\s+)*{re.escape(sig_name)}\b",
        rf"(?:logic|reg|wire|input|output)\s+(?:logic\s+)?(?:\w+\s+){0,2}{re.escape(sig_name)}\b",
    ]
    for p in patterns[:2]:
        m = re.search(p, combined_src)
        if m:
            range_expr = m.group(1)
            parts = range_expr.split(":")
            if len(parts) == 2:
                hi_expr = _resolve_width_expr(parts[0], params)
                lo_expr = _resolve_width_expr(parts[1], params)
                hi = _eval_simple_expr(hi_expr)
                lo = _eval_simple_expr(lo_expr)
                if hi is not None and lo is not None:
                    return hi - lo + 1, hi, lo
    if re.search(patterns[2], combined_src):
        return 1, 0, 0
    return 1, 0, 0  # default 1-bit


def parse_is_input_port(sig_name: str, file_or_paths) -> bool:
    """检查信号是否是 module input port (不包括 output reg)."""
    paths = [file_or_paths] if isinstance(file_or_paths, str) else file_or_paths
    combined_src = ""
    for f in paths:
        try:
            combined_src += "\n" + Path(f).read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            continue
    # 检查 output 声明 (output reg xxx 或 output logic xxx) — 排除
    if re.search(rf"output\s+(?:reg|logic|wire)\s+(?:\w+\s+)*(?:\w+\s+)*{re.escape(sig_name)}\b", combined_src):
        return False
    if re.search(rf"output\s+(?:reg|logic|wire)\s*\[", combined_src) and re.search(rf"output\s+(?:reg|logic|wire)\s*\[[^\]]+\]\s+(?:\w+\s+)*{re.escape(sig_name)}\b", combined_src):
        return False
    # 检查 input 声明
    if re.search(rf"input\s+(?:logic\s+)?(?:\w+\s+)?(?:\w+\s+)?{re.escape(sig_name)}\b", combined_src):
        return True
    if re.search(rf"input\s+(?:logic\s+)?\[[^\]]+\]\s+(?:\w+\s+)*{re.escape(sig_name)}\b", combined_src):
        return True
    return False


def parse_clock_reset(file_or_paths) -> tuple[str | None, str | None]:
    paths = [file_or_paths] if isinstance(file_or_paths, str) else file_or_paths
    combined_src = ""
    for f in paths:
        try:
            combined_src += "\n" + Path(f).read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            continue
    clk = None
    rst = None
    # 找 clock: 优先 clk_i / clk_x, 退回 clk
    for pat in [r"\b(clk\w*_i)\b", r"\b(clk)\b"]:
        m = re.search(pat, combined_src)
        if m:
            clk = m.group(1) or m.group(2)
            break
    # 找 reset: rst_n_i / rstn / rst_n / resetn
    for pat in [r"\b(rst\w*_n\w*)\b", r"\b(rst_n\w*)\b", r"\b(rstn)\b", r"\b(rst)\b", r"\b(resetn)\b"]:
        m = re.search(pat, combined_src)
        if m:
            rst = next((g for g in m.groups() if g), None)
            break
    return clk, rst


def parse_enums(file_or_paths) -> dict[str, list[tuple[str, int]]]:
    """粗略提取 typedef enum 里的 enum 名 + 值 (用于 FSM state bin 命名)."""
    paths = [file_or_paths] if isinstance(file_or_paths, str) else file_or_paths
    result = {}
    for f in paths:
        try:
            src = Path(f).read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            continue
        for m in re.finditer(r"typedef\s+enum[^{]*\{([^}]+)\}\s*(\w+)\s*;", src):
            body = m.group(1)
            ty_name = m.group(2)
            if ty_name in result:  # first-wins
                continue
            items = []
            next_val = 0
            for line in body.split("\n"):
                line = line.strip().rstrip(",").rstrip(";").strip()
                if not line or line.startswith("//"):
                    continue
                mm = re.match(r"(\w+)(?:\s*=\s*(\d+)'?d?(\d+)|\s*=\s*(\d+))?", line)
                if not mm:
                    continue
                n = mm.group(1)
                if mm.group(4):
                    v = int(mm.group(4))
                elif mm.group(2) and mm.group(3):
                    v = int(mm.group(3))
                else:
                    v = next_val
                items.append((n, v))
                next_val = v + 1
            if items:
                result[ty_name] = items
    return result


# =============================================================================
# Step 3: 信号分类 (data vs control)
# =============================================================================
_CONTROL_PATTERNS = [
    "valid", "ready", "stall", "ack", "req", "grant", "enable", "en_", "_en",
    "sel", "select", "we", "re", "cs", "ce", "we_i",
    "state", "next_state", "nxt_state", "state_q", "state_d",
    "mode", "op_mode",
    "done", "busy", "idle", "error", "fault", "alert", "trigger",
    "start", "stop", "flush", "flag", "status",
]


def classify(name: str, width: int) -> str:
    """判定信号是 DATA 还是 CONTROL.
    - DATA: width >= 8 (多 bit 通常是 data)
    - CONTROL: width < 8 + 名字含 control patterns (valid/state/mode/...)
    边界: 用 word boundary + 下划线边界, 避免 "re" 误匹配 "result"
    """
    nl = name.lower()
    if width >= 8:
        return "DATA"
    for p in _CONTROL_PATTERNS:
        if re.search(rf"(?:^|[_\W]){re.escape(p)}(?:$|[_\W])", nl):
            return "CONTROL"
    return "CONTROL"  # 1-bit default to control


# =============================================================================
# Step 4: bin 生成 (data vs control 策略不同)
# =============================================================================
def gen_bins_data(name: str, width: int) -> str:
    """DATA 信号: 范围分 bin (按 2^N 边界)"""
    if width == 32:
        return f"""    // DATA bins: 32-bit range partition
    bins zero  = {{32'h0}};
    bins byte  = {{[32'h1:32'hFF]}};          // 1-byte values
    bins word  = {{[32'h100:32'hFFFF]}};       // 2-byte values
    bins dword = {{[32'h10000:32'hFFFFFF]}};   // 3-byte values
    bins max   = {{32'hFFFF_FFFF}};"""
    if width == 16:
        return f"""    // DATA bins: 16-bit range partition
    bins zero = {{16'h0}};
    bins low  = {{[16'h1:16'hFF]}};
    bins mid  = {{[16'h100:16'h7FFF]}};
    bins high = {{[16'h8000:16'hFFFF]}};"""
    if width == 8:
        return f"""    // DATA bins: 8-bit range partition
    bins zero = {{8'h0}};
    bins low  = {{[8'h1:8'h7F]}};
    bins high = {{[8'h80:8'hFE]}};
    bins max  = {{8'hFF}};"""
    # generic
    return f"    bins auto = {{[0:{(1 << width) - 1}]}};  // width={width}"


def gen_bins_control(name: str, width: int, enums: dict, signal_enum: str | None) -> str:
    """CONTROL 信号: 离散 bin (用 enum 名字, 找不到就 generic)"""
    if signal_enum and signal_enum in enums:
        # 解析 enum names + 实际值 (从 typedef enum 里拿 N 或 N'hNN, 不再用 list index)
        # 返回 (name, value) list
        items = enums[signal_enum]  # list[tuple[name, value]] (重写 parse_enums)
        lines = [f"    // CONTROL bins (from enum {signal_enum}):"]
        used_vals = set()
        for n, v in items:
            lines.append(f"    bins {n.lower()} = {{{v}}};")
            used_vals.add(v)
        # 兜底: 未使用值
        max_v = (1 << width) - 1
        unused = sorted(set(range(max_v + 1)) - used_vals)
        if unused:
            lo, hi = min(unused), max(unused)
            lines.append(f"    bins reserved = {{[{lo}:{hi}]}};")
        return "\n".join(lines)
    if width == 1:
        return "    // CONTROL bins: 1-bit\n    bins low  = {1'b0};\n    bins high = {1'b1};"
    if width <= 4:
        max_v = (1 << width) - 1
        return f"""    // CONTROL bins: width={width} (1-of-N)
    bins zero  = {{0}};
    bins one   = {{1}};
    bins two   = {{2}};
    bins three = {{3}};
    bins other = {{[4:{max_v}]}};"""
    if width <= 7:
        max_v = (1 << width) - 1
        return f"""    // CONTROL bins: width={width} (1-of-N)
    bins zero  = {{0}};
    bins low   = {{[1:{max_v // 2}]}};
    bins high  = {{[{max_v // 2 + 1}:{max_v - 1}]}};
    bins max   = {{{max_v}}};"""
    # width 8+: 用 data bins
    return gen_bins_data(name, width)


# =============================================================================
# Step 5: 推断 sample 条件 (信号什么时候 stable)
# =============================================================================
# 启发式:
#   1. 名字含 vld/valid/req/ack/ready/grant/done → 需要 enable 配对
#   2. _q 后缀 (FF output) + width>=8 (data) → 找驱动它的 valid
#   3. _q 后缀 + width<8 (control/FSM) → sample 总是 1 (FSM state 本身总是 valid)
#   4. FSM state (enum 名字) → 1
#   5. 找不到 → None (sample 条件留空, 让用户填)

_VLD_SUFFIXES = ("valid", "vld", "req", "ack", "ready", "grant", "done")


def is_vld_signal(name: str) -> bool:
    """判定是否为 VLD 风格信号 (valid/req/ack/ready/grant/done)."""
    nl = name.lower()
    for suf in _VLD_SUFFIXES:
        # 名字: valid_o / valid_i / valid / din_valid / req_valid
        if nl == suf or nl.startswith(suf + "_") or nl.endswith("_" + suf):
            return True
    return False


_FF_SUFFIX = re.compile(r"_q$|_d$")


def infer_sample_condition(
    target: str,
    width: int,
    sig_class: str,
    related_signals: list[str],
    clk: str = "clk",
    rst: str | None = "rst_n",
    is_input_port: bool = False,
) -> tuple[str, str]:
    """
    返回 (sample_event, sample_caveat) 元组:
      - sample_event: 完整 sample 事件字符串 (含 @posedge clk 和可选 iff)
      - sample_caveat: 解释为什么这个 sample 条件是对的 (注释)

    策略 (保守):
      - 能确认 stable 条件 → 写 iff <cond>
      - 不能确认 → 只写 @posedge clk (不加 iff), 让用户填
    """
    base = f"@(posedge {clk}"
    rst_clause = f" && !{rst}" if rst else ""

    # 启发 1: VLD 信号 — 需要 enable/valid 配对
    if is_vld_signal(target):
        for r in related_signals:
            bare = re.sub(r"\[.*?\]", "", r)
            if bare in ("enable_i", "valid_i", "valid_o", "din_valid", "din_ready"):
                return f"{base} iff {bare}{rst_clause})", f"VLD-style signal — stable when {bare}=1"
        return f"{base} iff !{rst})" if rst else f"{base})", "VLD-style signal — no enable pair found; sample every cycle (may be too eager)"

    # 启发 2: Input port — 总是 stable (testbench 给, 每个 cycle 都有效)
    if is_input_port:
        if sig_class == "DATA":
            return f"{base})", "Input port — stable every cycle (testbench-driven)"
        return f"{base} iff !{rst})" if rst else f"{base})", "Input port control — always stable when not in reset"

    # 启发 3: Data reg (内部信号 + DATA) — 找 valid/ready/enable 配对
    if not is_input_port and sig_class == "DATA":
        # 优先找 valid/enable 单独配对
        for r in related_signals:
            bare = re.sub(r"\[.*?\]", "", r)
            if re.search(r"(_valid$|_enable$|^valid$|^enable$|valid$|enable$)", bare):
                return f"{base} iff {bare}{rst_clause})", f"Data reg — stable after upstream {bare}"
        return f"{base} iff !{rst})" if rst else f"{base})", "Data reg — no valid/enable gating found; sample every cycle (may be too eager)"

    # 启发 4: Control signal (FSM/enum) — 总是 sample
    if sig_class == "CONTROL":
        return f"{base} iff !{rst})" if rst else f"{base})", "Control signal (FSM/enum/flag) — always stable when not in reset"

    # 启发 5: default — 无法确认, 只写基础 clk
    return f"{base})", "Unknown — sample condition NOT inferred; please review and add 'iff ...' manually"


# =============================================================================
# Step 6: 找 cross 候选 (主信号的 fan-in 里的 control 信号)
# =============================================================================
_CONTROL_FOR_CROSS = {"mode_i", "valid_i", "valid_o", "enable_i", "trigger_i", "ready_i", "ready_o"}


def pick_cross_relations(main_sig: str, related: list[str], paths) -> list[str]:
    """从 related 参数里挑出真正 control 的信号. paths 是 list[str]."""
    picked = []
    for r in related:
        bare = re.sub(r"\[.*?\]", "", r)
        if bare in _CONTROL_FOR_CROSS:
            picked.append(bare)
        else:
            try:
                width, _, _ = parse_width_from_rtl(bare, paths)
            except Exception:
                continue
            if classify(bare, width) == "CONTROL":
                picked.append(bare)
    return picked


# =============================================================================
# Step 7: 主生成函数
# =============================================================================
def generate_covergroup(
    file: str | None = None,
    target_signal: str = None,
    related_signals: list[str] = None,
    filelist: str | None = None,
    module_name: str | None = None,
    strict: bool = False,
) -> str:
    related_signals = related_signals or []
    if not target_signal:
        raise ValueError("target_signal is required")

    # 读所有源文件 (file + filelist)
    sources, paths, include_dirs = read_all_sources(file=file, filelist=filelist)

    # sv_query risk analyze: 用 filelist (如果给) 否则用 file
    risk = query_risk_json(
        file=file, filelist=filelist, include_dirs=include_dirs, strict=strict,
    )
    # 多 module 文件: 只看指定 module (或第一个 module)
    if module_name:
        sig_info = find_signal_in_module(target_signal, risk["data_signals"], module_name)
    else:
        sig_info = find_signal(target_signal, risk["data_signals"])
    # ★ 优先用 pyslang 拿真实 width (包括 $clog2 等派生参数)
    pyslang_w = parse_width_from_pyslang(
        target_signal, file=file, filelist=filelist,
        module_name=module_name, include_dirs=include_dirs,
    )
    if pyslang_w is not None:
        width, hi, lo = pyslang_w
    else:
        # fallback: regex 解析 RTL (拿不到派生参数)
        width, hi, lo = parse_width_from_rtl(target_signal, paths)
    clk, rst = parse_clock_reset(paths)
    enums = parse_enums(paths)
    sig_class = classify(target_signal, width)

    # 找 enum 名 (用于 CONTROL bin 命名)
    signal_enum = None
    for ty_name, names in enums.items():
        if target_signal.replace("_q", "").replace("_d", "") in ty_name.replace("_e", ""):
            signal_enum = ty_name
            break
        # 启发: 名字相似
        if ty_name.replace("_e", "") in target_signal:
            signal_enum = ty_name
            break

    # 找 cross 候选
    cross_sigs = pick_cross_relations(target_signal, related_signals, paths)

    # ---- 拼 covergroup ----
    sample_clk = clk or "clk"
    sample_rst = rst or "rst_n"
    # 判定是 input port 还是 internal
    is_input_port = parse_is_input_port(target_signal, paths)
    # ★ Sample 条件推断 (保守策略: 能确认才写 iff, 不能确认留空)
    sample_evt, sample_caveat = infer_sample_condition(
        target_signal, width, sig_class, related_signals, sample_clk, sample_rst, is_input_port
    )

    risk_score = sig_info["func_score"] if sig_info else 0
    risk_level = sig_info.get("func_level", "MEDIUM") if sig_info else "MEDIUM"

    lines = []
    lines.append(f"// ======================================================================")
    lines.append(f"// Auto-generated covergroup for: {target_signal}")
    lines.append(f"//   class:     {sig_class}")
    lines.append(f"//   width:     {width} bits  (RTL: [{hi}:{lo}])")
    lines.append(f"//   risk:      {risk_score:.1f} ({risk_level})  fan_in={sig_info['fan_in'] if sig_info else '?'} fan_out={sig_info['fan_out'] if sig_info else '?'}")
    lines.append(f"//   generator: tools/coverage_gen_demo.py (Phase 1 POC)")
    lines.append(f"// ======================================================================")
    lines.append(f"covergroup cg_{target_signal} {sample_evt};")
    lines.append(f"  option.per_instance = 1;")
    lines.append(f"  option.comment = \"{target_signal} ({sig_class}, {width}-bit, risk={risk_score:.1f})\";")
    lines.append(f"")
    lines.append(f"  // ---- Primary coverpoint ----")
    lines.append(f"  cp_{target_signal}: coverpoint {target_signal} {{")

    if sig_class == "DATA":
        lines.append(gen_bins_data(target_signal, width))
    else:
        lines.append(gen_bins_control(target_signal, width, enums, signal_enum))
    lines.append(f"  }}")
    lines.append(f"")

    # ---- Cross coverpoints ----
    if cross_sigs:
        lines.append(f"  // ---- Cross coverpoints (related control signals) ----")
        for i, cs in enumerate(cross_sigs):
            cs_width, cs_hi, cs_lo = parse_width_from_rtl(cs, paths)
            cs_class = classify(cs, cs_width)
            lines.append(f"  cp_{cs}_for_{target_signal}: coverpoint {cs} {{")
            if cs_class == "CONTROL":
                lines.append(gen_bins_control(cs, cs_width, enums, None))
            else:
                lines.append(gen_bins_data(cs, cs_width))
            lines.append(f"  }}")
        lines.append(f"")
        lines.append(f"  // ---- Cross combinations ----")
        for cs in cross_sigs:
            lines.append(f"  cx_{target_signal}_x_{cs}: cross cp_{target_signal}, cp_{cs}_for_{target_signal};")
        lines.append(f"")

    # ---- Sample 条件注解 ----
    lines.append(f"  // ---- Sample event: {sample_evt} ----")
    lines.append(f"  //   {sample_caveat}")

    lines.append(f"endgroup: cg_{target_signal}")

    return "\n".join(lines)


# =============================================================================
# Main
# =============================================================================
def main():
    # 解析 flags
    args = sys.argv[1:]
    strict = False  # default: relaxed mode (工业多文件项目常见 UnknownModule)
    module_name = None
    filelist = None
    file = None
    positional = []
    for a in args:
        if a == "--no-strict":
            strict = False
        elif a.startswith("--module="):
            module_name = a.split("=", 1)[1]
        elif a.startswith("--filelist="):
            filelist = a.split("=", 1)[1]
        elif a == "--strict":
            pass
        else:
            positional.append(a)
    if len(positional) < 2:
        print(__doc__)
        sys.exit(1)
    # 智能解析 positional:
    #   - filelist 没给 + 第 1 个是 .f/.fl/.filelist → 当 filelist, 第 2 个是 file, 第 3 个是 target
    #   - filelist 已给 (via --filelist=) → 第 1 个是 file, 第 2 个是 target
    #   - 都没给 → 第 1 个是 file, 第 2 个是 target
    if filelist is None and len(positional) >= 1:
        first = positional[0]
        if first.endswith((".f", ".fl", ".filelist")) and Path(first).exists():
            filelist = first
            positional = positional[1:]
    if filelist is not None and len(positional) >= 2:
        # filelist 模式: positional[0] = file, positional[1] = target
        file = positional[0]
        target = positional[1]
        related = positional[2:]
    elif len(positional) >= 2:
        # 单文件模式: positional[0] = file, positional[1] = target
        file = positional[0]
        target = positional[1]
        related = positional[2:]
    else:
        print(__doc__)
        sys.exit(1)
    cg = generate_covergroup(
        file=file,
        target_signal=target,
        related_signals=related,
        filelist=filelist,
        module_name=module_name,
        strict=strict,
    )
    print(cg)


if __name__ == "__main__":
    main()
