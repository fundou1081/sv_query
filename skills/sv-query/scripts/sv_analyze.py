#!/usr/bin/env python3
"""
sv-query helper: 用 sv_query 跑一站式分析 (LLM 友好)

用法:
    # Python API
    from sv_analyze import trace_evidence
    result = trace_evidence("sim/test.sv", "top.data")
    # result 是 dict, 自动处理 error_code 分类

    # CLI
    python3 sv_analyze.py <sv_file> <signal> \\
        [--mode trace|fanin|fanout|evidence|dataflow|audit|verify|stats] \\
        [--to TARGET] [--depth N] [--max-results N] [--checks a,b]

LLM-friendly 设计:
- 永远加 `--json -q` 抑制 stderr 污染 stdout
- flag 一律放在**子命令之后** (Typer 只认 leaf command 的选项, 放中间会报 unknown option)
- 返回 dict 含 `ok` (bool) + `command` + `error_code` (stable, CLI 提供时) + `result` / `errors`
- 不返回 raw stderr (LLM 难处理)
- 仓库根目录自动定位: 从本文件向上找含 `run_cli.py` 的目录; 可用 `SV_QUERY_DIR` 覆盖

注意 (2026-11-11, 与 CLI 实测对齐):
- 旧的 `risk analyze` / `cdc analyze` / `verify gap` 命令已在 iter_263 退役,
  对应能力改由 `audit --checks risk|cdc|verification_gaps` 提供。
- 旧的 `--summary` flag 不存在; `dataflow analyze` 的 cap 是 `--max-paths/-n`。
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def _find_repo_root() -> Path | None:
    """从本文件向上找含 run_cli.py 的目录 (skill 随仓库安装时有效)"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "run_cli.py").is_file():
            return parent
    return None


def _resolve_sv_query_dir() -> Path | None:
    """SV_QUERY_DIR 优先; 否则自动向上定位仓库根"""
    env = os.environ.get("SV_QUERY_DIR")
    if env:
        p = Path(env).expanduser()
        return p if (p / "run_cli.py").is_file() else None
    return _find_repo_root()


SV_QUERY_DIR = _resolve_sv_query_dir()
PYTHON = sys.executable

_MISSING_DIR_MSG = (
    "sv_query 仓库根目录未找到 (需要含 run_cli.py)。"
    "请设置环境变量: export SV_QUERY_DIR=/path/to/your/sv_query"
)


def run_cli(*args, timeout=120, quiet=True, max_results=None):
    """Run sv_query CLI and return (rc, stdout, stderr)

    关键: `--json` / `-q` 必须放在**子命令之后** —— Typer 只认 leaf command 的选项,
    放在 group 和 subcommand 之间会报 "No such option"。所以统一追加到 argv 末尾。

    max_results 只对支持它的命令有效 (trace fanin/fanout); 其它命令用各自 flag。
    """
    if SV_QUERY_DIR is None:
        return 127, "", _MISSING_DIR_MSG

    argv = [str(a) for a in args]
    # 去掉调用方可能自带的 --json/-j, 统一在末尾追加
    argv = [a for a in argv if a not in ("--json", "-j")]
    if max_results is not None and not any(a in ("--max-results", "-N") for a in argv):
        argv += ["--max-results", str(max_results)]
    argv.append("--json")
    if quiet and not os.environ.get("SVQ_QUIET"):
        argv.append("-q")

    try:
        result = subprocess.run(
            [PYTHON, "run_cli.py", *argv],
            cwd=str(SV_QUERY_DIR),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"
    except Exception as e:
        return 1, "", f"{type(e).__name__}: {e}"


def _error_text(data: dict) -> str:
    """error 可能是 str / dict {type,message} / list —— 统一成可搜索的文本"""
    err = data.get("error")
    if isinstance(err, dict):
        return " ".join(str(x) for x in (err.get("type", ""), err.get("message", "")) if x)
    if isinstance(err, list):
        return " ".join(str(x) for x in err)
    return str(err or "")


def parse_json_or_error(rc, stdout, stderr):
    """解析 sv_query JSON 输出, 自动分类 error

    Returns: dict with `ok`, `command`, `error_code`, `error`, `result`, `errors`

    error_code 分类规则 (仅在 CLI 本身没给 error_code 时推断):
    - "Elaboration errors" / "unknown module" → E_ELABORATION_FAILED
    - "No such file" / "FileNotFound" → E_FILE_NOT_FOUND
    - "parse error" / "ParseError" → E_PARSE_ERROR
    - exit != 0 且 ok=false → E_INTERNAL
    """
    if not stdout.strip():
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

    if not isinstance(data, dict):
        return {
            "ok": False,
            "command": None,
            "error_code": "E_PARSE_ERROR",
            "error": f"unexpected json type: {type(data).__name__}",
            "result": None,
            "errors": [],
        }

    data.setdefault("errors", [])

    # sv_query 标准信封: {ok, command, params, result, errors, error_code?}
    if data.get("error_code") is None and data.get("ok") is False:
        err_text = _error_text(data).lower()
        if "elaboration" in err_text or "unknown module" in err_text:
            data["error_code"] = "E_ELABORATION_FAILED"
        elif "parse error" in err_text or "syntax error" in err_text:
            data["error_code"] = "E_PARSE_ERROR"
        elif "signal not found" in err_text or "no signal" in err_text:
            data["error_code"] = "E_SIGNAL_NOT_FOUND"
        elif "target not found" in err_text:
            data["error_code"] = "E_TARGET_NOT_FOUND"
        elif "no such file" in err_text or "filenotfound" in err_text or "not found" in err_text:
            data["error_code"] = "E_FILE_NOT_FOUND"
        elif "no data" in err_text:
            data["error_code"] = "E_NO_DATA"
        else:
            data["error_code"] = "E_INTERNAL"
    elif data.get("error_code") is None and data.get("ok") is True:
        data["error_code"] = None

    return data


def trace_fanin(sv_file: str, signal: str, depth: int = 5, max_results: int = 50) -> dict:
    """Trace signal drivers (fanin)

    Returns: dict, {ok, command, result: {signals[], total_count, truncated, ...}}
    """
    rc, out, err = run_cli(
        "trace", "fanin", signal, "-f", sv_file,
        "--depth", str(depth),
        max_results=max_results,
    )
    return parse_json_or_error(rc, out, err)


def trace_fanin_filelist(filelist: str, signal: str, depth: int = 5, max_results: int = 50) -> dict:
    """Trace fanin using filelist (multi-file projects)"""
    rc, out, err = run_cli(
        "trace", "fanin", signal, "--filelist", filelist,
        "--depth", str(depth),
        max_results=max_results,
    )
    return parse_json_or_error(rc, out, err)


def trace_fanout(sv_file: str, signal: str, max_results: int = 50) -> dict:
    """Trace signal loads (fanout)"""
    rc, out, err = run_cli(
        "trace", "fanout", signal, "-f", sv_file,
        max_results=max_results,
    )
    return parse_json_or_error(rc, out, err)


def trace_fanout_filelist(filelist: str, signal: str, max_results: int = 50) -> dict:
    """Trace fanout using filelist"""
    rc, out, err = run_cli(
        "trace", "fanout", signal, "--filelist", filelist,
        max_results=max_results,
    )
    return parse_json_or_error(rc, out, err)


def trace_evidence(sv_file: str, signal: str, chain: bool = False) -> dict:
    """Get evidence (source code context) for a signal

    Returns: dict, {ok, command, result: {signals: [{evidence: {...}}]}, evidence: {...}}
    """
    args = ["trace", "evidence", signal, "-f", sv_file]
    if chain:
        args.append("--chain")
    rc, out, err = run_cli(*args)
    return parse_json_or_error(rc, out, err)


def trace_evidence_filelist(filelist: str, signal: str, chain: bool = False) -> dict:
    """Trace evidence using filelist"""
    args = ["trace", "evidence", signal, "--filelist", filelist]
    if chain:
        args.append("--chain")
    rc, out, err = run_cli(*args)
    return parse_json_or_error(rc, out, err)


def dataflow(sv_file: str, from_sig: str, to_sig: str, max_paths: int = 50) -> dict:
    """Dataflow between two signals

    注意: cap 用 `--max-paths/-n` (不是 --max-results —— dataflow 不接受那个 flag)

    Returns: dict, {ok, command, result: {paths[], is_reachable, truncated, ...}}
    """
    rc, out, err = run_cli(
        "dataflow", "analyze", from_sig, to_sig, "-f", sv_file,
        "--evidence",
        "--max-paths", str(max_paths),
    )
    return parse_json_or_error(rc, out, err)


def dataflow_filelist(filelist: str, from_sig: str, to_sig: str, max_paths: int = 50) -> dict:
    """Dataflow analysis using filelist"""
    rc, out, err = run_cli(
        "dataflow", "analyze", from_sig, to_sig, "--filelist", filelist,
        "--evidence",
        "--max-paths", str(max_paths),
    )
    return parse_json_or_error(rc, out, err)


AUDIT_CHECKS = (
    "protocols", "handshakes", "backpressure_cycles", "assertions",
    "coverage", "verification_gaps", "risk", "constraints", "cdc", "timing",
)


def audit(sv_file: str = None, filelist: str = None, checks=None, target: str = None) -> dict:
    """设计审计 (CDC / 风险 / 验证缺口 / 覆盖率 / 协议 / 握手 ...)

    这是退役的 `cdc analyze` / `risk analyze` / `verify gap` 的替代入口。

    注意: audit 的 JSON **没有** 标准信封 (没有 ok/command/result),
    这里统一包成 {ok, command, result, errors} 让调用方逻辑一致。

    Returns: dict, {ok, command, result: {target, checks[], sections{}, summary{}}}
    """
    args = ["audit"]
    if sv_file:
        args += ["-f", sv_file]
    if filelist:
        args += ["--filelist", filelist]
    if target:
        args += ["--target", target]
    if checks:
        args += ["--checks", ",".join(checks)]
    rc, out, err = run_cli(*args)
    if not out.strip():
        return parse_json_or_error(rc, out, err)
    try:
        raw = json.loads(out)
    except json.JSONDecodeError:
        return parse_json_or_error(rc, out, err)
    if isinstance(raw, dict) and "sections" in raw:
        return {
            "ok": True,
            "command": "audit",
            "error_code": None,
            "error": None,
            "result": raw,
            "errors": [],
        }
    return parse_json_or_error(rc, out, err)


def verify_structural(sv_file: str = None, filelist: str = None, checks=None) -> dict:
    """结构性检查 (默认 symmetry) —— 退役 `verify gap` 的替代入口之一"""
    args = ["verify", "structural"]
    if sv_file:
        args += ["-f", sv_file]
    if filelist:
        args += ["--filelist", filelist]
    if checks:
        args += ["--checks", ",".join(checks)]
    rc, out, err = run_cli(*args)
    return parse_json_or_error(rc, out, err)


def verify_consistency(sv_file: str = None, filelist: str = None, checks=None) -> dict:
    """双向一致性检查 (reciprocity / bit / connection)"""
    args = ["verify", "consistency"]
    if sv_file:
        args += ["-f", sv_file]
    if filelist:
        args += ["--filelist", filelist]
    if checks:
        args += ["--checks", ",".join(checks)]
    rc, out, err = run_cli(*args)
    return parse_json_or_error(rc, out, err)


def stats(sv_file: str = None, filelist: str = None) -> dict:
    """Get graph statistics

    Returns: dict, {ok, command, result: {...}}
    """
    if filelist:
        args = ["stats", "--filelist", filelist]
    elif sv_file:
        args = ["stats", "-f", sv_file]
    else:
        return {
            "ok": False,
            "command": None,
            "error_code": "E_INVALID_INPUT",
            "error": "need sv_file or filelist",
            "result": None,
            "errors": [],
        }
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
    # CDC 概要 (audit 替代已退役的 cdc analyze)
    python3 sv_analyze.py sim/test.sv --mode cdc
    # 风险评分 (audit 替代已退役的 risk analyze)
    python3 sv_analyze.py sim/test.sv --mode risk
    # 验证缺口 (audit 替代已退役的 verify gap)
    python3 sv_analyze.py sim/test.sv --mode verify
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
        choices=["trace", "fanin", "f", "fi", "in",
                 "fanout", "fo", "out",
                 "evidence", "e", "ev",
                 "dataflow", "df",
                 "audit", "a", "risk", "r", "cdc", "c", "verify", "v",
                 "stats", "s"],
        help="Analysis mode (default: evidence)",
    )
    parser.add_argument("--to", help="Target signal (for dataflow mode)")
    parser.add_argument("--depth", type=int, default=5, help="Trace depth (default: 5)")
    parser.add_argument("--max-results", "-N", type=int, default=50,
                        help="Cap results count for trace fanin/fanout (default: 50)")
    parser.add_argument("--max-paths", type=int, default=50,
                        help="Cap path count for dataflow (default: 50)")
    parser.add_argument("--checks",
                        help="Comma-separated audit checks (default: all). "
                             "Available: " + ",".join(AUDIT_CHECKS))
    parser.add_argument("--chain", action="store_true", help="Show evidence chain")

    args = parser.parse_args()

    # argparse nargs="?" 会让第一个 positional 作为 sv_file, 第二个作为 signal.
    # 但如果指定了 --filelist, sv_file 应该是 None, 第一个 positional 应该是 signal.
    if args.filelist and not args.signal and args.sv_file:
        args.signal = args.sv_file
        args.sv_file = None

    target = args.sv_file or args.filelist
    if not target:
        print(json.dumps({"ok": False, "error_code": "E_INVALID_INPUT",
                          "error": "need sv_file or --filelist", "result": None}))
        sys.exit(1)

    if args.sv_file and not Path(args.sv_file).exists():
        print(json.dumps({"ok": False, "error_code": "E_FILE_NOT_FOUND",
                          "error": f"file not found: {args.sv_file}", "result": None}))
        sys.exit(1)

    if args.filelist and not Path(args.filelist).exists():
        print(json.dumps({"ok": False, "error_code": "E_FILELIST_NOT_FOUND",
                          "error": f"filelist not found: {args.filelist}", "result": None}))
        sys.exit(1)

    mode = args.mode
    sv_file = args.sv_file
    checks = [c.strip() for c in args.checks.split(",") if c.strip()] if args.checks else None

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
            result = dataflow_filelist(args.filelist, args.signal, args.to, args.max_paths)
        else:
            result = dataflow(sv_file, args.signal, args.to, args.max_paths)
    elif mode in ("audit", "a"):
        result = audit(sv_file=sv_file, filelist=args.filelist, checks=checks)
    elif mode in ("risk", "r"):
        result = audit(sv_file=sv_file, filelist=args.filelist,
                       checks=checks or ["risk"])
    elif mode in ("cdc", "c"):
        result = audit(sv_file=sv_file, filelist=args.filelist,
                       checks=checks or ["cdc"])
    elif mode in ("verify", "v"):
        result = audit(sv_file=sv_file, filelist=args.filelist,
                       checks=checks or ["verification_gaps"])
    elif mode in ("stats", "s"):
        result = stats(sv_file=sv_file, filelist=args.filelist)
    else:
        result = {"ok": False, "error_code": "E_INVALID_INPUT",
                  "error": f"unknown mode: {args.mode}", "result": None}

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
