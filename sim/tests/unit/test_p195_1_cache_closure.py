"""P195.1 — cache key covers the resolved filelist/build closure."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from sv_query.trace.core.cache.ast_cache import ASTCache, CacheKeyError  # noqa: E402


def _cache(tmp_path: Path) -> ASTCache:
    return ASTCache(cache_dir=str(tmp_path / "cache"))


def test_define_change_changes_filelist_hash(tmp_path):
    src = tmp_path / "m.sv"
    src.write_text("module m; endmodule\n")
    fl = tmp_path / "d.f"
    fl.write_text(f"+define+SIG=aaa\n{src}\n")
    cache = _cache(tmp_path)
    h1 = cache.compute_filelist_hash(str(fl))
    fl.write_text(f"+define+SIG=bbb\n{src}\n")
    assert cache.compute_filelist_hash(str(fl)) != h1


def test_filelist_incdir_header_change_changes_hash(tmp_path):
    src = tmp_path / "m.sv"
    src.write_text("module m; endmodule\n")
    inc = tmp_path / "inc"
    inc.mkdir()
    hdr = inc / "defs.svh"
    hdr.write_text("`define SIG aaa\n")
    fl = tmp_path / "d.f"
    fl.write_text(f"+incdir+{inc}\n{src}\n")
    cache = _cache(tmp_path)
    h1 = cache.compute_filelist_hash(str(fl))
    hdr.write_text("`define SIG bbb\n")
    assert cache.compute_filelist_hash(str(fl)) != h1


def test_sources_mode_hashes_explicit_incdir_headers(tmp_path):
    inc = tmp_path / "inc"
    inc.mkdir()
    hdr = inc / "defs.svh"
    hdr.write_text("`define SIG aaa\n")
    cache = _cache(tmp_path)
    h1 = cache.compute_sources_hash({"m.sv": "module m; endmodule\n"}, [str(inc)])
    hdr.write_text("`define SIG bbb\n")
    h2 = cache.compute_sources_hash({"m.sv": "module m; endmodule\n"}, [str(inc)])
    assert h1 != h2


def test_unreadable_closure_member_is_explicit_key_error(tmp_path):
    src = tmp_path / "m.sv"
    src.write_text("module m; endmodule\n")
    fl = tmp_path / "d.f"
    fl.write_text(f"{src}\n")
    cache = _cache(tmp_path)
    # Filelist parser records missing files; key computation must not skip them.
    fl.write_text(f"{tmp_path / 'missing.sv'}\n")
    try:
        cache.compute_filelist_hash(str(fl))
    except CacheKeyError:
        pass
    else:
        raise AssertionError("missing closure member must raise CacheKeyError")


def test_graph_session_refresh_after_header_change(tmp_path, monkeypatch):
    from sv_query.graph_session import GraphSession

    inc = tmp_path / "inc"
    inc.mkdir()
    hdr = inc / "defs.svh"
    hdr.write_text("`define SIG aaa\n")
    src = tmp_path / "top.sv"
    src.write_text('`include "defs.svh"\nmodule top; logic `SIG; endmodule\n')
    fl = tmp_path / "d.f"
    fl.write_text(f"+incdir+{inc}\n{src}\n")
    monkeypatch.setenv("SVQ_CACHE_DIR", str(tmp_path / "cache"))

    gs = GraphSession(filelist=str(fl))
    assert gs.graph_nodes()["nodes"][0]["id"] == "top.aaa"
    hdr.write_text("`define SIG bbb\n")
    assert gs.refresh() is True
    assert gs.graph_nodes()["nodes"][0]["id"] == "top.bbb"
