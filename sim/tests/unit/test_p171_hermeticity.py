"""P171.2: filelist fixtures and mutation runner must be CWD-independent."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MUT = ROOT / "tools/agent/mutation_faults.py"


def test_filelist_fixtures_have_no_absolute_paths():
    bad = []
    for f in (ROOT / "sim/tests").rglob("*.f"):
        for lineno, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            s = line.strip()
            if not s or s.startswith(("#", "//")):
                continue
            if s.startswith("+"):
                s = s.split("+", 2)[-1] if s.startswith("+incdir+") else ""
                if s.startswith("/"):
                    bad.append((f, lineno, line))
            elif s.startswith("/"):
                bad.append((f, lineno, line))
    assert not bad, "\n".join(f"{p}:{n}: {line}" for p, n, line in bad[:10])


@pytest.mark.skipif(shutil.which("verilator") is None, reason="verilator not installed")
def test_mutation_runner_is_cwd_independent(tmp_path):
    tasks = {
        "tasks": [{
            "id": "cwd_simple",
            "source": "sim/test_simple.sv",
            "top": "top",
            "query": "drivers",
            "signal": "top.data",
            "mutation": {"old": "assign data = din;", "new": "assign data = en;"},
            "expect": {
                "before": {"contains": ["top.din"]},
                "after": {"contains": ["top.en"]},
            },
        }]
    }
    task_file = tmp_path / "tasks.json"
    task_file.write_text(json.dumps(tasks), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(MUT), "--tasks", str(task_file), "--json"],
        cwd=str(tmp_path), capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr[-1000:]
    result = json.loads(proc.stdout)
    assert result["passed"] == 1, result
