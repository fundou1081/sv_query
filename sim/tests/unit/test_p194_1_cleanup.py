"""P194.1 — no author paths / entry sys.path bootstrap / duplicate imports."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"


def test_src_has_no_author_paths():
    hits = []
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "my_dv_proj" in text or "slang/build/bindings" in text:
            hits.append(str(path))
    assert hits == []


def test_entry_has_no_sys_path_bootstrap():
    text = (SRC / "sv_query/cli/_entry.py").read_text(encoding="utf-8")
    assert "sys.path.insert" not in text
    assert "SRC_DIR" not in text


def test_bindings_env_is_explicit(monkeypatch, tmp_path):
    sys.path.insert(0, str(SRC))
    from sv_query.trace.core._bindings import add_bindings_from_env
    monkeypatch.setenv("SVQ_PYSLANG_BINDINGS", str(tmp_path))
    added = add_bindings_from_env()
    assert added == str(tmp_path)
    assert str(tmp_path) in sys.path
    sys.path.remove(str(tmp_path))
