"""test_discipline_semantic_regex.py — [iter_368 / PLAN P66] 语义 regex 纪律。

三层保证:
  1. 仓库语义模块当前 0 违规;
  2. 检查器能检出非 UVM 语义模块的 regex;
  3. UVM 宏例外文件不会被误报。
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CHECKER = REPO / "tools" / "check_semantic_regex.py"

sys.path.insert(0, str(REPO / "tools"))
import check_semantic_regex as csr  # noqa: E402


def test_repo_semantic_regex_clean():
    r = subprocess.run([sys.executable, str(CHECKER)], capture_output=True, text=True)
    assert r.returncode == 0, f"语义 regex 违规:\n{r.stdout}\n{r.stderr}"
    assert "通过" in r.stdout


def test_checker_detects_non_uvm_regex():
    text = "import re\n\ndef f(x):\n    return re.search('a', x)\n"
    bad = csr.scan_text(text, "src/trace/core/class_graph_builder.py")
    assert {v["kind"] for v in bad} >= {"import_re", "re.search"}


def test_checker_allows_uvm_macro_regex():
    text = "import re\n\n_RE = re.compile(r'`uvm_object_utils')\n"
    assert csr.scan_text(text, "src/trace/core/query/uvm.py") == []
