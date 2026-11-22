"""P193.4 — core query paths must not swallow exceptions."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import check_core_except as tool  # noqa: E402


def test_current_core_files_have_no_silent_broad_except():
    assert tool.scan(ROOT) == []


def test_synthetic_silent_and_explicit_handlers(tmp_path):
    silent = tmp_path / "silent.py"
    silent.write_text(
        "def f():\n"
        "    try:\n"
        "        return 1\n"
        "    except Exception:\n"
        "        return []\n"
    )
    explicit = tmp_path / "explicit.py"
    explicit.write_text(
        "def f():\n"
        "    try:\n"
        "        return 1\n"
        "    except Exception as exc:\n"
        "        return {'status': 'unknown', 'error': str(exc)}\n"
    )
    assert tool.scan_source(silent)
    assert tool.scan_source(explicit) == []


def test_gate_covers_library_and_session():
    assert "src/sv_query/trace/unified_tracer.py" in tool.CORE_FILES
    assert "src/sv_query/graph_session.py" in tool.CORE_FILES
    assert "src/sv_query/cli/core/locate/session_cmd.py" in tool.CORE_FILES
    assert len(tool.CORE_FILES) >= 10
