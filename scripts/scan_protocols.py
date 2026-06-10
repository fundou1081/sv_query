#!/usr/bin/env python3
"""
scan_protocols.py - 批量扫描项目目录的协议分布

用法:
    # 模式 1: 扫目录下所有 .sv/.v (单文件编译, 适合无 cross-dep)
    python scripts/scan_protocols.py <dir> [--pattern "*.sv"] [--include ...] [--output report.md]

    # 模式 2: 用 filelist 一次编译 (解决 cross-file 依赖)
    python scripts/scan_protocols.py --filelist <file.f> [--include ...] [--output report.md]

功能:
  - 扫目录下所有匹配文件 (或 filelist)
  - 每个文件运行 protocol detect
  - 汇总协议分布 + 错例 (低置信度) + UNKNOWN
  - 输出 Markdown 报告
"""
import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root / "src"))


@dataclass
class ScanResult:
    file: str
    module: str
    protocol: str
    variant: Optional[str]
    confidence: float
    signals: int
    error: Optional[str]
    skipped: bool
    skip_reason: Optional[str]


def _build_detector():
    from trace.core.protocol.detector import ProtocolDetector
    from trace.core.protocol.schema import ProtocolSchemaRegistry
    from trace.core.protocol.handshake_provider import NameBasedHandshakeProvider
    reg = ProtocolSchemaRegistry.from_directory(
        str(_project_root / "config" / "protocols")
    )
    return ProtocolDetector(
        registry=reg,
        handshake_provider=NameBasedHandshakeProvider(),
    )


def _best_match(detector, mods) -> Optional[Tuple[str, object, int]]:
    best = None
    best_conf = -1.0
    for mod_name, mod in mods.items():
        if not mod.signals:
            continue
        m = detector.detect(mod.signals)
        if m.confidence > best_conf:
            best_conf = m.confidence
            best = (mod_name, m, len(mod.signals))
    return best


def _scan_one(ext, detector) -> Tuple[Optional[ScanResult], List[ScanResult]]:
    """扫描单个文件. 返回 (best_result, [其他低置信度 results])."""
    try:
        mods = ext.extract_all_modules()
    except Exception as e:
        # 编译失败
        return (
            ScanResult(
                file=ext._filelist or (ext._files[0] if ext._files else "?"),
                module="(error)", protocol="", variant=None,
                confidence=0, signals=0, error=str(e),
                skipped=True, skip_reason=f"compile error: {str(e)[:100]}",
            ),
            [],
        )

    if not mods:
        return (
            ScanResult(
                file=ext._filelist or (ext._files[0] if ext._files else "?"),
                module="(none)", protocol="", variant=None,
                confidence=0, signals=0, error=None,
                skipped=True, skip_reason="no modules",
            ),
            [],
        )

    best = _best_match(detector, mods)
    if not best:
        return (
            ScanResult(
                file=ext._filelist or (ext._files[0] if ext._files else "?"),
                module="(none)", protocol="", variant=None,
                confidence=0, signals=0, error="no signals",
                skipped=True, skip_reason="no signals",
            ),
            [],
        )

    mod_name, m, sig_count = best
    return (
        ScanResult(
            file=ext._filelist or (ext._files[0] if ext._files else "?"),
            module=mod_name, protocol=m.protocol,
            variant=m.variant, confidence=m.confidence,
            signals=sig_count, error=None,
            skipped=False, skip_reason=None,
        ),
        [],
    )


def scan_files(
    files: List[str],
    include_dirs: Optional[List[str]] = None,
) -> List[ScanResult]:
    """逐个文件扫描 (每个文件单独编译)."""
    from trace.core.protocol.sv_extractor import SVSignalExtractor

    detector = _build_detector()
    results = []
    start = time.time()
    for i, f in enumerate(files, 1):
        if i % 5 == 0 or i == 1:
            elapsed = time.time() - start
            eta = (len(files) - i) * (elapsed / i) if i > 0 else 0
            print(f"  [{i}/{len(files)}] {Path(f).name}  ({elapsed:.0f}s, ETA {eta:.0f}s)", file=sys.stderr)
        ext = SVSignalExtractor.from_file(f, include_dirs=include_dirs)
        r, _ = _scan_one(ext, detector)
        results.append(r)
    return results


def scan_filelist(
    filelist: str,
    include_dirs: Optional[List[str]] = None,
) -> List[Tuple[str, ScanResult]]:
    """用 filelist 一次编译, 然后对每个 module 单独检测.

    返回 [(module_name, ScanResult), ...] — 多个 module per file.
    """
    from trace.core.protocol.sv_extractor import SVSignalExtractor

    detector = _build_detector()
    ext = SVSignalExtractor.from_filelist(filelist, include_dirs=include_dirs)
    try:
        mods = ext.extract_all_modules()
    except Exception as e:
        return [("(compile error)", ScanResult(
            file=filelist, module="(error)", protocol="", variant=None,
            confidence=0, signals=0, error=str(e),
            skipped=True, skip_reason=str(e)[:200],
        ))]

    out = []
    for mod_name, mod in mods.items():
        if not mod.signals:
            continue
        m = detector.detect(mod.signals)
        out.append((mod_name, ScanResult(
            file=filelist, module=mod_name,
            protocol=m.protocol, variant=m.variant,
            confidence=m.confidence, signals=len(mod.signals),
            error=None, skipped=False, skip_reason=None,
        )))
    return out


def scan_directory(
    directory: str,
    pattern: str = "*.sv",
    limit: Optional[int] = None,
    skip_patterns: Optional[List[str]] = None,
    include_dirs: Optional[List[str]] = None,
) -> List[ScanResult]:
    """扫描目录下所有匹配文件 (单文件模式)."""
    from trace.core.protocol.sv_extractor import SVSignalExtractor

    detector = _build_detector()
    dir_path = Path(directory).expanduser()
    if not dir_path.exists():
        print(f"Error: directory not found: {dir_path}", file=sys.stderr)
        sys.exit(1)

    files = sorted(dir_path.rglob(pattern))
    if skip_patterns:
        files = [f for f in files if not any(p in str(f) for p in skip_patterns)]
    if limit:
        files = files[:limit]

    results = []
    start = time.time()
    for i, f in enumerate(files, 1):
        if i % 5 == 0 or i == 1:
            elapsed = time.time() - start
            eta = (len(files) - i) * (elapsed / i) if i > 0 else 0
            print(f"  [{i}/{len(files)}] {f.name}  ({elapsed:.0f}s, ETA {eta:.0f}s)", file=sys.stderr)
        ext = SVSignalExtractor.from_file(str(f), include_dirs=include_dirs)
        r, _ = _scan_one(ext, detector)
        results.append(r)
    return results


def aggregate(results: List[ScanResult]) -> Dict:
    """汇总统计."""
    scanned = [r for r in results if not r.skipped]
    skipped = [r for r in results if r.skipped]
    errors = [r for r in results if r.error]

    by_protocol: Dict[str, List[ScanResult]] = {}
    for r in scanned:
        key = r.protocol or "UNKNOWN"
        by_protocol.setdefault(key, []).append(r)

    by_variant: Dict[str, List[ScanResult]] = {}
    for r in scanned:
        key = f"{r.protocol}/{r.variant or '(none)'}"
        by_variant.setdefault(key, []).append(r)

    low_conf = [r for r in scanned if r.confidence < 0.5]

    return {
        "total_files": len(results),
        "scanned": len(scanned),
        "skipped": len(skipped),
        "errors": len(errors),
        "by_protocol": {k: len(v) for k, v in sorted(by_protocol.items())},
        "by_variant": {k: len(v) for k, v in sorted(by_variant.items())},
        "low_confidence": low_conf,
        "errors_list": errors,
    }


def render_report(target: str, results: List[ScanResult], agg: Dict) -> str:
    """渲染 Markdown 报告."""
    lines = []
    lines.append(f"# Protocol Scan Report")
    lines.append("")
    lines.append(f"**Target**: `{target}`")
    lines.append(f"**Files**: {agg['total_files']}")
    lines.append(f"**Scanned**: {agg['scanned']}")
    lines.append(f"**Skipped**: {agg['skipped']}")
    lines.append(f"**Errors**: {agg['errors']}")
    lines.append("")

    lines.append("## Protocol Distribution")
    lines.append("")
    lines.append("| Protocol | Count | % |")
    lines.append("|----------|-------|---|")
    for proto, count in sorted(agg["by_protocol"].items(), key=lambda x: -x[1]):
        pct = 100 * count / max(1, agg["scanned"])
        lines.append(f"| {proto} | {count} | {pct:.1f}% |")
    lines.append("")

    lines.append("## Variant Distribution")
    lines.append("")
    lines.append("| Protocol/Variant | Count |")
    lines.append("|------------------|-------|")
    for variant, count in sorted(agg["by_variant"].items(), key=lambda x: -x[1]):
        lines.append(f"| {variant} | {count} |")
    lines.append("")

    if agg["low_confidence"]:
        lines.append(f"## Low Confidence (< 0.5) — {len(agg['low_confidence'])} modules")
        lines.append("")
        lines.append("| File | Module | Protocol | Variant | Conf | Signals |")
        lines.append("|------|--------|----------|---------|------|---------|")
        for r in sorted(agg["low_confidence"], key=lambda x: x.confidence):
            fname = Path(r.file).name if r.file else "?"
            lines.append(
                f"| `{fname}` | {r.module} | {r.protocol or '?'} | "
                f"{r.variant or ''} | {r.confidence:.2f} | {r.signals} |"
            )
        lines.append("")

    if agg["errors_list"]:
        lines.append(f"## Errors — {len(agg['errors_list'])} files")
        lines.append("")
        for r in agg["errors_list"][:20]:
            fname = Path(r.file).name if r.file else "?"
            err = r.error or "?"
            lines.append(f"- `{fname}`: {err[:150]}")
        if len(agg["errors_list"]) > 20:
            lines.append(f"- ... and {len(agg['errors_list']) - 20} more")
        lines.append("")

    scanned = [r for r in results if not r.skipped]
    top = sorted(scanned, key=lambda x: -x.confidence)[:15]
    if top:
        lines.append("## Top Detected (highest confidence)")
        lines.append("")
        lines.append("| File | Module | Protocol | Variant | Conf |")
        lines.append("|------|--------|----------|---------|------|")
        for r in top:
            fname = Path(r.file).name if r.file else "?"
            lines.append(
                f"| `{fname}` | {r.module} | {r.protocol} | "
                f"{r.variant or ''} | {r.confidence:.3f} |"
            )
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Batch scan SV files for protocol detection")
    parser.add_argument("directory", nargs="?", help="Directory to scan")
    parser.add_argument("--filelist", help="Use filelist (single compilation)")
    parser.add_argument("--pattern", default="*.sv", help="File pattern (default: *.sv)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of files")
    parser.add_argument("--skip", action="append", default=[], help="Skip files containing this string")
    parser.add_argument("--include", "-I", action="append", default=[], help="Include directory (can be repeated)")
    parser.add_argument("--output", "-o", help="Output Markdown report to file")
    args = parser.parse_args()

    if args.filelist:
        target = f"filelist:{args.filelist}"
        print(f"Scanning filelist: {args.filelist}")
        module_results = scan_filelist(args.filelist, include_dirs=args.include or None)
        results = [r for _, r in module_results]
    elif args.directory:
        target = args.directory
        print(f"Scanning: {args.directory}")
        print(f"  Pattern: {args.pattern}")
        if args.skip:
            print(f"  Skipping: {args.skip}")
        if args.limit:
            print(f"  Limit: {args.limit}")
        results = scan_directory(
            args.directory,
            pattern=args.pattern,
            limit=args.limit,
            skip_patterns=args.skip,
            include_dirs=args.include or None,
        )
    else:
        parser.error("Either DIRECTORY or --filelist required")

    agg = aggregate(results)

    print()
    print("=== Summary ===")
    for proto, count in sorted(agg["by_protocol"].items(), key=lambda x: -x[1]):
        print(f"  {proto:12s}: {count:4d}")
    if agg["low_confidence"]:
        print(f"  LOW_CONF    : {len(agg['low_confidence'])} (need review)")
    if agg["errors_list"]:
        print(f"  ERRORS      : {len(agg['errors_list'])}")

    if args.output:
        report = render_report(target, results, agg)
        Path(args.output).write_text(report)
        print(f"\nReport saved to: {args.output}")


if __name__ == "__main__":
    main()
