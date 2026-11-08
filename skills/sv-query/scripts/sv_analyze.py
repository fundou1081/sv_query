#!/usr/bin/env python3
"""
sv-query helper: 用 sv_query 跑一站式分析 (LLM 友好)

用法:
    # Python API
    from sv_analyze import trace_evidence
    result = trace_evidence("sim/test.sv", "top.data")
    # result 是 dict, 自动处理 error_code 分类

    # CLI
    python3 sv_analyze.py <sv_file> <signal> [--mode trace|f|in|fanin|evidence|dataflow|risk|cdc|verify] [--to TARGET] [--depth N] [--max-results N]

LLM-friendly 设计:
- 永远加 `--json -q` 抑制 stderr 污染 stdout
- 默认 `--max-results 50` 防 OOM
- 返回 dict 含 `ok` (bool) + `error_code` (stable) + `result` / `errors`
- 不返回 raw stderr (LLM 难处理)
- 路径用 `<PROJ_DIR>/sv_query` (USER_PROFILE.md 主目录, 不是 agent runtime cache)

输出 schema 跟 `tools/llm_schema.json` 一致:
    {
      "ok": bool,
      "command": str,
      "error_code": str | null,
      "error": str | null,
      "result": dict | null,
      "errors": list
    }
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# sv_query 项目主目录 (USER_PROFILE.md 强制, 不用 agent runtime cache [agent-runtime-cache]/)
# sv_query 项目主目录占位符:
# 默认: ~/projects/sv_query (Linux/macOS 通用约定)
# 真实用户可能用其他路径 (~/projects/sv_query, ~/work/sv_query 等)
# 如需修改, 改这一行或用环境变量 SV_QUERY_DIR 覆盖:
#   export SV_QUERY_DIR=/path/to/your/sv_query
import os as _os
_SV_QUERY_DEFAULT = _os.environ.get("SV_QUERY_DIR") or str(Path.home() / "projects" / "sv_query")
# 修正: 如果默认路径不是用户明确配置的, 用一个通用占位符
# 这样 error message 不会泄露用户名
if _SV_QUERY_DEFAULT.startswith(str(Path.home())) and "projects" in _SV_QUERY_DEFAULT and "sv_query" in _SV_QUERY_DEFAULT:
    # 默认路径未配置, 使用占位符供文档/错误消息使用
    SV_QUERY_DIR = Path(_os.environ.get("SV_QUERY_DIR", "/path/to/sv_query"))
else:
    SV_QUERY_DIR = Path(_SV_QUERY_DEFAULT)
PYTHON = sys.executable


def run_cli(*args, timeout=120, quiet=True, max_results=None):
    """Run sv_query CLI and return (rc, stdout, stderr)

    LLM 友好:
    - 自动加 --json -q (除非 caller 显式 override)
    - max_results 是 per-command flag, 默认 50 (trace fanin/fanout/cdc/risk 支持)

    关键: 全局 flag (--json/-j, --quiet/-q) 必须在 subcommand 之后;
         per-command flag (--max-results/-N, --summary/-S) 也在 subcommand 之后.
    """
    args = list(args)

    # 处理特殊情况: 第一个 arg 已经是全局 flag
    if args and args[0] in ("--json", "-j", "--pretty", "-p", "--quiet", "-q"):
        if len(args) >= 2 and not args[1].startswith("-"):
            global_flag = args.pop(0)
            args.insert(1, global_flag)

    # 强制 --json
    has_json = any(a in ("--json", "-j") for a in args)
    if not has_json:
        for i, a in enumerate(args):
            if not a.startswith("-"):
                args.insert(i + 1, "--json")
                break
        else:
            args.append("--json")

    # 强制 --quiet
    if quiet and not any(a in ("--quiet", "-q") for a in args) and not os.environ.get("SVQ_QUIET"):
        for i, a in enumerate(args):
            if not a.startswith("-"):
                args.insert(i + 1, "-q")
                break
        else:
            args.append("-q")

    # max_results 是 per-command, 只在显式要求时加
    # (避免 stats/evidence 等命令报 "no such option: --max-results")
    if max_results is not None and not any(a in ("--max-results", "-N") for a in args):
        for i, a in enumerate(args):
            if not a.startswith("-"):
                args.insert(i + 1, "--max-results")
                args.insert(i + 2, str(max_results))
                break
        else:
            args.extend(["--max-results", str(max_results)])

    try:
        result = subprocess.run(
            [PYTHON, "run_cli.py", *args],
            cwd=str(SV_QUERY_DIR),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        # SV_QUERY_DIR 不存在或没有 run_cli.py
        # 不暴露实际路径, 给出配置指引
        return 127, "", (
            "sv_query not found at expected location. "
            "Please configure SV_QUERY_DIR environment variable: "
            "`export SV_QUERY_DIR=/path/to/your/sv_query`. "
            f"Default location: {SV_QUERY_DIR}."
        )
    except Exception as e:
        return 1, "", f"{type(e).__name__}: {e}"


def parse_json_or_error(rc, stdout, stderr):
    """解析 sv_query JSON 输出, 自动分类 error

    Returns: dict with `ok`, `command`, `error_code`, `error`, `result`, `errors`

    error_code 分类规则 (从 error 文本推断):
    - "Elaboration errors" / "unknown module" → E_ELABORATION_FAILED
    - "No such file" / "FileNotFound" → E_FILE_NOT_FOUND
    - "parse error" / "ParseError" → E_PARSE_ERROR
    - exit != 0 且 ok=false → E_INTERNAL
    """
    if not stdout.strip():
        # rc=127 通常是 binary 不存在 (subprocess FileNotFoundError 包装)
        if rc == 127 and stderr and "not found" in stderr.lower():
            return {
                "ok": False,
                "command": None,
                "error_code": "E_FILE_NOT_FOUND",
                "error": stderr.strip()[:500],
                "result": None,
                "errors": [],
            }
        return {
            "ok": False,
            "command": None,
            "error_code": "E_ELABORATION_FAILED",
            "error": (stderr or "").strip()[:500] or "empty stdout (elaboration failed?)",
            "result": None,
            "errors": [],
        }

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        return {
            "ok": False,
            "command": None,
            "error_code": "E_PARSE_ERROR",
            "error": f"json decode failed: {e}; stdout[:200]={stdout[:200]!r}",
            "result": None,
            "errors": [],
        }

    # sv_query 输出格式: {ok, command, result, error, error_code, errors}
    if data.get("error_code") is None and data.get("ok") is False:
        # 推断 error_code (从 error 文本)
        err_text = (data.get("error") or "").lower()
        if "elaboration" in err_text or "unknown module" in err_text:
            data["error_code"] = "E_ELABORATION_FAILED"
        elif "no such file" in err_text or "filenotfound" in err_text or "no such option" in err_text:
            data["error_code"] = "E_FILE_NOT_FOUND"
        elif "parse error" in err_text or "syntax error" in err_text:
            data["error_code"] = "E_PARSE_ERROR"
        elif "signal not found" in err_text or "no signal" in err_text:
            data["error_code"] = "E_SIGNAL_NOT_FOUND"
        elif "target not found" in err_text:
            data["error_code"] = "E_TARGET_NOT_FOUND"
        elif "no data" in err_text:
            data["error_code"] = "E_NO_DATA"
        elif rc != 0:
            data["error_code"] = "E_INTERNAL"
        else:
            data["error_code"] = "E_INTERNAL"  # 默认
    elif data.get("error_code") is None and data.get("ok") is True:
        # 成功情况, 确保 error_code 字段存在 (None 表示 OK)
        data["error_code"] = None

    return data


def trace_fanin(sv_file: str, signal: str, depth: int = 5, max_results: int = 50) -> dict:
    """Trace signal drivers (fanin)

    Args:
        sv_file: .sv 文件路径
        signal: 要 trace 的信号名
        depth: trace 深度 (默认 5)
        max_results: cap 结果数 (LLM context 安全)

    Returns: dict, {ok, command, result: {drivers, truncated, total_count, ...}}
    """
    rc, out, err = run_cli(
        "trace", "fanin", signal, "-f", sv_file,
        "--depth", str(depth),
        "--max-results", str(max_results),
    )
    return parse_json_or_error(rc, out, err)


def trace_fanin_filelist(filelist: str, signal: str, depth: int = 5, max_results: int = 50) -> dict:
    """Trace fanin using filelist (multi-file projects)

    Returns: dict, {ok, command, result: {drivers, ...}}
    """
    rc, out, err = run_cli(
        "trace", "fanin", signal, "--filelist", filelist,
        "--depth", str(depth),
        "--max-results", str(max_results),
    )
    return parse_json_or_error(rc, out, err)


def trace_fanout(sv_file: str, signal: str, max_results: int = 50) -> dict:
    """Trace signal loads (fanout)

    Args:
        sv_file: .sv 文件路径
        signal: 要 trace 的信号名
        max_results: cap 结果数

    Returns: dict, {ok, command, result: {loads, truncated, total_count}}
    """
    rc, out, err = run_cli(
        "trace", "fanout", signal, "-f", sv_file,
        "--max-results", str(max_results),
    )
    return parse_json_or_error(rc, out, err)


def trace_fanout_filelist(filelist: str, signal: str, max_results: int = 50) -> dict:
    """Trace fanout using filelist"""
    rc, out, err = run_cli(
        "trace", "fanout", signal, "--filelist", filelist,
        "--max-results", str(max_results),
    )
    return parse_json_or_error(rc, out, err)


def trace_evidence(sv_file: str, signal: str, chain: bool = False) -> dict:
    """Get evidence (source code context) for a signal

    Args:
        sv_file: .sv 文件路径
        signal: 要看源码的信号名
        chain: 是否显示 chain (默认 False)

    Returns: dict, {ok, command, result: {signal, evidence: {credibility_score, source_text, source_range, ...}}}

    Note: sv_query trace_evidence 返回时 evidence 在顶层, 不在 result wrapper 里.
          这个函数自动包装成 {result: {evidence: ...}} 跟其他命令保持一致.
    """
    rc, out, err = run_cli("trace", "evidence", signal, "-f", sv_file, "--json", "-q")
    data = parse_json_or_error(rc, out, err)
    if data.get("ok") and "result" not in data and "evidence" in data:
        # 包装 evidence 到 result 里 (跟其他命令保持一致)
        data["result"] = {
            "signal": data.get("signal"),
            "evidence": data.get("evidence"),
            "params": data.get("params"),
        }
    return data


def trace_evidence_filelist(filelist: str, signal: str, chain: bool = False) -> dict:
    """Trace evidence using filelist"""
    rc, out, err = run_cli("trace", "evidence", signal, "--filelist", filelist, "--json", "-q")
    data = parse_json_or_error(rc, out, err)
    if data.get("ok") and "result" not in data and "evidence" in data:
        data["result"] = {
            "signal": data.get("signal"),
            "evidence": data.get("evidence"),
            "params": data.get("params"),
        }
    return data


def dataflow(sv_file: str, from_sig: str, to_sig: str) -> dict:
    """Dataflow between two signals

    Returns: dict, {ok, command, result: {paths: [...]}}
    """
    rc, out, err = run_cli(
        "dataflow", "analyze", from_sig, to_sig, "-f", sv_file,
        "--evidence", "--max-results", "50",
    )
    return parse_json_or_error(rc, out, err)


def dataflow_filelist(filelist: str, from_sig: str, to_sig: str) -> dict:
    """Dataflow analysis using filelist"""
    rc, out, err = run_cli(
        "dataflow", "analyze", from_sig, to_sig, "--filelist", filelist,
        "--evidence", "--max-results", "50",
    )
    return parse_json_or_error(rc, out, err)


def risk_analyze(sv_file: str, summary: bool = True) -> dict:
    """Risk analysis with evidence

    Args:
        sv_file: .sv 文件路径
        summary: True=只返回 top-10 + counts (LLM 友好); False=全量

    Returns: dict, {ok, command, result: {top_risks, clocks_count, resets_count, ...}}
    """
    args = ["risk", "analyze", "-f", sv_file, "--max-results", "50"]
    if summary:
        args.append("--summary")
    rc, out, err = run_cli(*args)
    return parse_json_or_error(rc, out, err)


def risk_analyze_filelist(filelist: str, summary: bool = True) -> dict:
    """Risk analysis using filelist"""
    args = ["risk", "analyze", "--filelist", filelist, "--max-results", "50"]
    if summary:
        args.append("--summary")
    rc, out, err = run_cli(*args)
    return parse_json_or_error(rc, out, err)


def cdc_analyze(sv_file: str, summary: bool = True) -> dict:
    """CDC analysis with evidence

    Args:
        sv_file: .sv 文件路径
        summary: True=只返回 counts + domains; False=全 paths

    Returns: dict, {ok, command, result: {total_cdc, high_risk, low_risk, domains, ...}}
    """
    args = ["cdc", "analyze", "-f", sv_file, "--max-results", "50"]
    if summary:
        args.append("--summary")
    rc, out, err = run_cli(*args)
    return parse_json_or_error(rc, out, err)


def cdc_analyze_filelist(filelist: str, summary: bool = True) -> dict:
    """CDC analysis using filelist"""
    args = ["cdc", "analyze", "--filelist", filelist, "--max-results", "50"]
    if summary:
        args.append("--summary")
    rc, out, err = run_cli(*args)
    return parse_json_or_error(rc, out, err)


def verify_gap(sv_file: str) -> dict:
    """Find verification gaps with evidence

    Returns: dict, {ok, command, result: {gaps: [...]}}
    """
    rc, out, err = run_cli("verify", "gap", "-f", sv_file, "--max-results", "50")
    return parse_json_or_error(rc, out, err)


def verify_gap_filelist(filelist: str) -> dict:
    """Find verification gaps with filelist"""
    rc, out, err = run_cli("verify", "gap", "--filelist", filelist, "--max-results", "50")
    return parse_json_or_error(rc, out, err)


def stats(sv_file: str = None, filelist: str = None) -> dict:
    """Get graph statistics

    Args:
        sv_file: 单 .sv 文件 (二选一)
        filelist: filelist 路径 (二选一, 优先)

    Returns: dict, {ok, command, result: {total_nodes, total_edges, nodes, edges, modules}}
    """
    if filelist:
        args = ["stats", "--filelist", filelist]
    elif sv_file:
        args = ["stats", "-f", sv_file]
    else:
        return {"ok": False, "error_code": "E_INVALID_INPUT", "error": "need sv_file or filelist", "result": None}
    rc, out, err = run_cli(*args)
    return parse_json_or_error(rc, out, err)


def main():
    parser = argparse.ArgumentParser(
        description="sv-query one-shot analyzer (LLM-friendly wrapper)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
LLM 调用示例:
    # 看信号源码
    python3 sv_analyze.py sim/test.sv top.data --mode evidence
    # 找驱动
    python3 sv_analyze.py sim/test.sv top.q --mode fanin
    # 找负载
    python3 sv_analyze.py sim/test.sv clk --mode fanout --max-results 20
    # CDC 概要
    python3 sv_analyze.py sim/test.sv --mode cdc --summary
    # 风险评分
    python3 sv_analyze.py sim/test.sv --mode risk --summary
    # 整个图 stats
    python3 sv_analyze.py --filelist /tmp/myproj.f --mode stats
        """,
    )
    parser.add_argument("sv_file", nargs="?", help="Path to .sv file (or --filelist)")
    parser.add_argument("signal", nargs="?", help="Signal name (for trace/dataflow/evidence)")
    parser.add_argument(
        "--filelist",
        help="Path to filelist (.f) - alternative to sv_file",
    )
    parser.add_argument(
        "--mode",
        default="evidence",
        choices=["trace", "fanin", "fanout", "f", "fi", "fo", "in", "out",
                 "evidence", "e", "ev", "dataflow", "df",
                 "risk", "r", "cdc", "c", "verify", "v",
                 "stats", "s"],
        help="Analysis mode (default: evidence)",
    )
    parser.add_argument("--to", help="Target signal (for dataflow mode)")
    parser.add_argument("--depth", type=int, default=5, help="Trace depth (default: 5)")
    parser.add_argument("--max-results", "-N", type=int, default=50,
                        help="Cap results count (default: 50, LLM context safety)")
    parser.add_argument("--summary", "-S", action="store_true",
                        help="Summary mode for cdc/risk (LLM friendly)")
    parser.add_argument("--chain", action="store_true", help="Show evidence chain")

    args = parser.parse_args()

    # CLI 参数解析补充:
    # argparse nargs="?" 会让第一个 positional 作为 sv_file, 第二个作为 signal.
    # 但如果指定了 --filelist, sv_file 应该是 None, 第一个 positional 应该是 signal.
    if args.filelist and not args.signal and args.sv_file:
        # 交换: sv_file (signal 误传) → signal
        args.signal = args.sv_file
        args.sv_file = None

    # Validate inputs
    target = args.sv_file or args.filelist
    if not target:
        print(json.dumps({"ok": False, "error_code": "E_INVALID_INPUT",
                          "error": "need sv_file or --filelist", "result": None}))
        sys.exit(1)

    # 检查 sv_file 存在 (如果有指定)
    if args.sv_file and not Path(args.sv_file).exists():
        print(json.dumps({"ok": False, "error_code": "E_FILE_NOT_FOUND",
                          "error": f"file not found: {args.sv_file}", "result": None}))
        sys.exit(1)

    # 检查 filelist 存在 (如果有指定)
    if args.filelist and not Path(args.filelist).exists():
        print(json.dumps({"ok": False, "error_code": "E_FILELIST_NOT_FOUND",
                          "error": f"filelist not found: {args.filelist}", "result": None}))
        sys.exit(1)

    # Dispatch
    mode = args.mode
    sv_file = args.sv_file

    if mode in ("trace", "fanin", "f", "fi", "in"):
        if not args.signal:
            print(json.dumps({"ok": False, "error_code": "E_INVALID_INPUT",
                              "error": "fanin mode needs signal", "result": None}))
            sys.exit(1)
        if args.filelist:
            result = trace_fanin_filelist(args.filelist, args.signal, args.depth, args.max_results)
        else:
            result = trace_fanin(sv_file, args.signal, args.depth, args.max_results)
    elif mode in ("fanout", "fo", "out"):
        if not args.signal:
            print(json.dumps({"ok": False, "error_code": "E_INVALID_INPUT",
                              "error": "fanout mode needs signal", "result": None}))
            sys.exit(1)
        if args.filelist:
            result = trace_fanout_filelist(args.filelist, args.signal, args.max_results)
        else:
            result = trace_fanout(sv_file, args.signal, args.max_results)
    elif mode in ("evidence", "e", "ev"):
        if not args.signal:
            print(json.dumps({"ok": False, "error_code": "E_INVALID_INPUT",
                              "error": "evidence mode needs signal", "result": None}))
            sys.exit(1)
        if args.filelist:
            result = trace_evidence_filelist(args.filelist, args.signal, args.chain)
        else:
            result = trace_evidence(sv_file, args.signal, args.chain)
    elif mode in ("dataflow", "df"):
        if not args.signal or not args.to:
            print(json.dumps({"ok": False, "error_code": "E_INVALID_INPUT",
                              "error": "dataflow needs <signal> and --to <target>",
                              "result": None}))
            sys.exit(1)
        if args.filelist:
            result = dataflow_filelist(args.filelist, args.signal, args.to)
        else:
            result = dataflow(sv_file, args.signal, args.to)
    elif mode in ("risk", "r"):
        if args.filelist:
            result = risk_analyze_filelist(args.filelist, summary=args.summary)
        else:
            result = risk_analyze(sv_file, summary=args.summary)
    elif mode in ("cdc", "c"):
        if args.filelist:
            result = cdc_analyze_filelist(args.filelist, summary=args.summary)
        else:
            result = cdc_analyze(sv_file, summary=args.summary)
    elif mode in ("verify", "v"):
        if args.filelist:
            result = verify_gap_filelist(args.filelist)
        else:
            result = verify_gap(sv_file)
    elif mode in ("stats", "s"):
        result = stats(sv_file=sv_file, filelist=args.filelist)
    else:
        result = {"ok": False, "error_code": "E_INVALID_INPUT",
                  "error": f"unknown mode: {args.mode}", "result": None}

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()