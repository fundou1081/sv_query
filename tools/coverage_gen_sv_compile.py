#!/usr/bin/env python3
"""
coverage_gen_sv_compile.py — Phase 3 #C

验证 coverage_gen_demo.py 生成的 covergroup **SV 语法正确性**.
用 pyslang (SystemVerilog compiler) 实际编译生成的 covergroup.

用法:
  python tools/coverage_gen_sv_compile.py \
    --file sim/openTitan_validation.sv \
    --signal data_o \
    --module simple_pipe

  python tools/coverage_gen_sv_compile.py \
    --filelist picorv32.f \
    --file picorv32.v \
    --signal mem_addr

返回:
  PASS — covergroup SV 语法正确 (slang 0 errors)
  FAIL — 有 X 个 errors + 错误详情

设计:
  1. 调 coverage_gen_demo.generate_covergroup() 生成 covergroup 文本
  2. 把 covergroup 跟 signal declarations 包装成 SV wrapper file
  3. 用 pyslang.driver 编译 wrapper
  4. 解析 diagnostic (filter out wrapper-specific warnings)

为什么用 pyslang 而不是 slang CLI:
  - pyslang 已装 (sv_query 现有依赖)
  - 避免 brew install slang (network issues)
  - 一致性 (跟 coverage_gen_demo.py 用同一 parser)

Phase 3 #C, 2026-06-24.
"""
import argparse
import re
import sys
from pathlib import Path

# 让 tools/coverage_gen_demo.py 能 import
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from coverage_gen_demo import generate_covergroup


def _silence_stderr():
    """Context manager 屏蔽 pyslang WARNING 到 stderr (避免重复输出).

    generate_covergroup + parse_signal_decl 会各自调 pyslang 一次, 总共 3 次 WARNING 输出.
    我们不关心这些 wrapper warning, 只关心 compile 结果.
    """
    import contextlib
    import io

    @contextlib.contextmanager
    def silence():
        saved = sys.stderr
        sys.stderr = io.StringIO()
        try:
            yield
        finally:
            sys.stderr = saved
    return silence()


def parse_signal_decl(sig_name: str, file: str, module_name: str | None = None) -> str:
    """从 RTL 拿 signal 的 width, 生成 `logic [N-1:0] sig_name;` 声明.

    用于 wrapper module 内部, 让 coverpoint 能看到 signal.

    策略 (跟 generate_covergroup 一致):
      1. 先试 parse_width_from_pyslang (能拿 hierarchical + 真实 width)
      2. fallback 到 parse_width_from_rtl (regex 解析)
      3. 最后 fallback 到 1-bit
    """
    from coverage_gen_demo import parse_width_from_pyslang, parse_width_from_rtl, read_all_sources

    # 1. pyslang (AST)
    result = parse_width_from_pyslang(sig_name, file=file, module_name=module_name)
    if result is not None:
        width, hi, lo = result
    else:
        # 2. regex fallback
        try:
            sources, paths, include_dirs = read_all_sources(file=file)
            width, hi, lo = parse_width_from_rtl(sig_name, paths)
        except Exception:
            # 3. default 1-bit
            return f"logic {sig_name};"
    if width == 1:
        return f"logic {sig_name};"
    return f"logic [{hi}:{lo}] {sig_name};"


def build_wrapper(covergroup_text: str, sig_decls: list[str]) -> str:
    """把 covergroup + signal decls 包装成完整 SV 文件.

    wrapper structure:
        module __test_wrap;
            // 解析 covergroup 里的 @(posedge CLK iff !RST) 拿真实 clk/rst 名
            logic <CLK>;
            logic <RST>;
            // signal decls
            {sig_decls}
            // covergroup
            {covergroup_text}
            // instantiate covergroup
            cg_my cg_inst = new();
        endmodule
    """
    sig_block = "\n    ".join(sig_decls)
    # 把 covergroup name 拿出来实例化
    m = re.search(r"covergroup\s+(\w+)\s+@?\(?\)?", covergroup_text)
    cg_name = m.group(1) if m else "cg_my"

    # 解析 sample event: @(posedge CLK iff !RST) 或 @(posedge CLK)
    clk_name, rst_name = "clk", "rst_n"  # fallback
    # pattern: @(posedge <clk>) 或 @(posedge <clk> iff !<rst>)
    sample_m = re.search(
        r"@\(\s*posedge\s+(\w+)(?:\s+iff\s+!?\s*(\w+))?\s*\)", covergroup_text
    )
    if sample_m:
        clk_name = sample_m.group(1)
        rst_name = sample_m.group(2) or "rst_n"

    return f"""// Auto-generated test wrapper for covergroup SV validation
// Generator: tools/coverage_gen_sv_compile.py
module __test_wrap;
    logic {clk_name};
    logic {rst_name};
    {sig_block}

{covergroup_text}

    {cg_name} cg_inst = new();
endmodule
"""


def compile_sv(sv_text: str, source_label: str = "wrapper") -> tuple[bool, list[str], list[str]]:
    """用 pyslang 编译 SV, 返回 (ok, errors, warnings).

    ok=True 表示 0 errors.
    """
    import pyslang

    # 写临时文件 (pyslang 期望文件路径)
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sv', delete=False) as f:
        f.write(sv_text)
        tmp_path = f.name

    driver = pyslang.driver.Driver()
    driver.addStandardArgs()
    # 关键: 必须 parseCommandLine (dummy args) 才能初始化 driver
    driver.parseCommandLine("--help")
    driver.sourceLoader.addFiles(tmp_path)
    driver.processOptions()
    driver.parseAllSources()

    errors = []
    warnings = []

    # elaboration 阶段 diagnostics (含 parse + type check + covergroup eval)
    compilation = driver.createCompilation()
    driver.runAnalysis(compilation)

    for d in compilation.getAllDiagnostics():
        # 拿 formatted message
        msg = driver.diagEngine.formatMessage(d)
        # 加 line/col
        loc_str = ""
        try:
            loc = d.location
            if loc and loc.offset >= 0:
                # 拿 line/col from source manager
                sm = driver.sourceManager
                line = sm.getLineNumber(loc)
                col = sm.getColumnNumber(loc)
                fname = sm.getFileName(loc) or "?"
                loc_str = f"{fname}:{line}:{col}: "
        except Exception:
            pass
        full_msg = f"{loc_str}{msg}"
        if d.isError():
            errors.append(full_msg)
        elif d.isWarning():
            warnings.append(full_msg)

    # 清理 temp file
    try:
        Path(tmp_path).unlink()
    except Exception:
        pass

    return (len(errors) == 0, errors, warnings)


def _extract_width_from_cg(cg_text: str, sig_name: str) -> int | None:
    """从生成的 covergroup 文本里拿 signal 的 width.
    e.g. 'option.comment = "data_o (DATA, 16-bit, ...)"' → 16
    """
    # 1. 主 coverpoint: option.comment 里找 "<name> (CLASS, N-bit, ...)"
    pat = re.compile(
        rf'option\.comment\s*=\s*"[^"]*?{re.escape(sig_name)}\s*\(\s*\w+\s*,\s*(\d+)-bit[^)]*?\)"'
    )
    m = pat.search(cg_text)
    if m:
        try:
            return int(m.group(1))
        except (ValueError, IndexError):
            pass
    # 2. cross coverpoint: cp_<sig>_for_<signal> 的 width
    cross_pat = re.compile(
        rf'option\.comment\s*=\s*"[^"]*?cp_{re.escape(sig_name)}_for_\w+\s*\(\s*\w+\s*,\s*(\d+)-bit[^)]*?\)"'
    )
    m = cross_pat.search(cg_text)
    if m:
        try:
            return int(m.group(1))
        except (ValueError, IndexError):
            pass
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Validate generated covergroup SV syntax with pyslang compiler"
    )
    parser.add_argument("-f", "--file", help="Top RTL file")
    parser.add_argument("--filelist", help="Filelist (.f/.fl) for multi-file projects")
    parser.add_argument("-s", "--signal", required=True, help="Target signal name")
    parser.add_argument("-m", "--module", help="Module name (for multi-module files)")
    parser.add_argument("-r", "--related", action="append", default=[],
                        help="Related signals for cross coverpoint (repeatable)")
    parser.add_argument("--keep-wrapper", help="Save wrapper SV to this file (debug)")
    args = parser.parse_args()

    # Step 1: 生成 covergroup
    print(f"=== Generating covergroup for signal: {args.signal} ===", file=sys.stderr)
    with _silence_stderr():
        cg_text = generate_covergroup(
            file=args.file,
            target_signal=args.signal,
            related_signals=args.related,
            filelist=args.filelist,
            module_name=args.module,
        )

    # Step 2: 解析所有 signal 的 width, 生成 SV 声明
    # 优先从 covergroup option.comment 拿 (覆盖更准)
    sig_decls = []
    for sig in [args.signal] + args.related:
        width = _extract_width_from_cg(cg_text, sig)
        if width is None:
            # fallback: regex parse RTL
            with _silence_stderr():
                decl = parse_signal_decl(sig, file=args.file, module_name=args.module)
        elif width == 1:
            decl = f"logic {sig};"
        else:
            decl = f"logic [{width-1}:0] {sig};"
        sig_decls.append(decl)
        print(f"  signal decl: {decl} (width from {'cg option.comment' if width else 'regex fallback'})", file=sys.stderr)

    # Step 3: 构建 wrapper
    wrapper_sv = build_wrapper(cg_text, sig_decls)
    if args.keep_wrapper:
        Path(args.keep_wrapper).write_text(wrapper_sv)
        print(f"  wrapper saved to {args.keep_wrapper}", file=sys.stderr)

    # Step 4: 编译
    print(f"\n=== Compiling with pyslang ===", file=sys.stderr)
    with _silence_stderr():
        ok, errors, warnings = compile_sv(wrapper_sv)

    # Step 5: 输出结果
    print()
    if ok:
        print(f"✅ PASS: covergroup SV is syntactically valid (0 errors, {len(warnings)} warnings)")
        if warnings:
            print(f"\nWarnings (non-blocking):")
            for w in warnings:
                print(f"  ⚠️  {w}")
    else:
        print(f"❌ FAIL: covergroup SV has {len(errors)} error(s)")
        for i, err in enumerate(errors, 1):
            print(f"  {i}. {err}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())