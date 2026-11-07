"""[P91/A] top-aware filelist pruning."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MOD = ROOT / "src" / "trace" / "core" / "top_prune.py"


def _load():
    spec = importlib.util.spec_from_file_location("top_prune", MOD)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _sources(tmp_path: Path) -> dict[str, str]:
    files = {
        "top.sv": "module top; child u(); endmodule\n",
        "child.sv": "module child; assign x = '0; endmodule\n",
        "unused.sv": "module unused; endmodule\n",
        "pkg.sv": "package p; endpackage\n",
        "hdr.svh": "`define X 1\n",
        "fake.sv": "// module fake; endmodule\nmodule real; endmodule\n",
    }
    out = {}
    for name, text in files.items():
        p = tmp_path / name
        p.write_text(text)
        out[str(p)] = text
    return out


def test_top_closure_keeps_special_files(tmp_path):
    m = _load()
    src = _sources(tmp_path)
    r = m.prune_sources(src, "top")
    names = {Path(p).name for p in r.selected}
    assert {"top.sv", "child.sv", "pkg.sv", "hdr.svh"} <= names
    assert "unused.sv" not in names
    assert "fake.sv" not in names
    assert r.reason == "reachable"


def test_single_quote_literal_does_not_hide_child(tmp_path):
    m = _load()
    src = _sources(tmp_path)
    # child.sv contains a SystemVerilog '0 literal. A naive quote stripper would
    # swallow the rest of the file and drop the dependency.
    r = m.prune_sources(src, "top")
    assert any(p.endswith("child.sv") for p in r.selected)


def test_top_not_found_returns_all(tmp_path):
    m = _load()
    src = _sources(tmp_path)
    r = m.prune_sources(src, "missing_top")
    assert r.reason == "top_not_found"
    assert set(r.selected) == set(src)


def test_no_top_returns_all(tmp_path):
    m = _load()
    src = _sources(tmp_path)
    r = m.prune_sources(src, None)
    assert r.reason == "no_top"
    assert set(r.selected) == set(src)


def test_pruned_build_falls_back_to_full_filelist(tmp_path):
    """A macro-generated instantiation is invisible to the textual scan; the
    pruned build fails and the helper must rebuild from the full filelist."""
    (tmp_path / "defs.svh").write_text("`define CHILD child\n")
    (tmp_path / "top.sv").write_text(
        '`include "defs.svh"\nmodule top; `CHILD u(); endmodule\n')
    (tmp_path / "child.sv").write_text("module child; endmodule\n")
    fl = tmp_path / "all.f"
    fl.write_text("\n".join(str(tmp_path / n) for n in
                            ("top.sv", "child.sv", "defs.svh")) + "\n")

    from cli._common import _build_pruned_tracer
    tr = _build_pruned_tracer(str(fl), "top", log_level="ERROR")
    info = tr._svq_prune_info
    assert info["fallback"] is True
    assert "elaboration" in info["fallback_reason"].lower() or "unknown module" in info["fallback_reason"].lower()
    assert "top.u" in [i.full_path for i in tr.get_instances()]
