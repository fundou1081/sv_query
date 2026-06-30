# ==============================================================================
# search.py - Grep-like keyword search across SystemVerilog source files
# ==============================================================================
"""
Usage:
  python run_cli.py search "always_ff" -f top.sv
  python run_cli.py search "q1" -f sim/test_cases.sv -n 5
  python run_cli.py search "clk" -f ~/my_dv_proj/opentitan/hw/ip/aes/rtl/

Reference output to compare with: trace evidence
  python run_cli.py trace evidence test_multi_alway.q1 -f sim/test_cases.sv
"""

import re
import sys
from pathlib import Path

import typer

# Add project root to path
_project_root = Path(__file__).parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def search(
    keyword: str = typer.Argument(..., help="Keyword / regex pattern to search"),
    file: Path = typer.Option(..., "--file", "-f", help="File or directory to search"),
    context: int = typer.Option(2, "-C", "--context", help="Lines of context before/after"),
    regex: bool = typer.Option(False, "-E", "--regex", help="Interpret as extended regex (default: literal)"),
    case_insensitive: bool = typer.Option(False, "-i", "--ignore-case", help="Case-insensitive search"),
    max_results: int = typer.Option(50, "-n", "--max-results", help="Max number of results"),
    line_numbers: bool = typer.Option(True, "-l", "--line-numbers", help="Show line numbers"),
) -> None:
    """Grep-like search across .sv/.v files"""

    target = Path(file).expanduser().resolve()

    if not target.exists():
        print(f"Error: {target} does not exist", file=sys.stderr)
        raise typer.Exit(code=1)

    # Collect files to search
    if target.is_dir():
        files = list(target.rglob("*.sv")) + list(target.rglob("*.v"))
        files = [f for f in files if ".git" not in str(f) and "__pycache__" not in str(f)]
    else:
        files = [target]

    if not files:
        print(f"No .sv/.v files found in {target}", file=sys.stderr)
        raise typer.Exit(code=1)

    # Build pattern
    flags = re.IGNORECASE if case_insensitive else 0
    if regex:
        pattern = re.compile(keyword, flags)
    else:
        pattern = re.compile(re.escape(keyword), flags)

    total_matches = 0
    for filepath in sorted(files):
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception as e:
            continue

        matches = []
        for i, line in enumerate(lines, start=1):
            if pattern.search(line):
                matches.append(i)

        if not matches:
            continue

        # Header
        rel = filepath.relative_to(target.parent) if target.is_dir() else filepath.name
        print(f"\n{'='*60}")
        print(f"  {rel}")
        print(f"  {len(matches)} match(es) in {len(lines)} lines")
        print(f"{'='*60}")

        for lineno in matches[:max_results]:
            start = max(0, lineno - context - 1)
            end = min(len(lines), lineno + context)

            for j in range(start, end):
                marker = ">>>" if j + 1 == lineno else "   "
                print(f"  {marker} {j+1:5d}  {lines[j].rstrip()}")

            if len(matches) > max_results:
                print(f"\n  ... and {len(matches) - max_results} more matches")
                break

        total_matches += len(matches)

    print(f"\n{'='*60}")
    print(f"Total: {total_matches} match(es) across {len(files)} file(s)")
    print(f"{'='*60}")

    if total_matches == 0:
        print(f"\n(no matches found for '{keyword}')")


if __name__ == "__main__":
    typer.run(search)
