"""P165.4: .core -> filelist closure adapter (synthetic, no external source)."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MOD_PATH = ROOT / "tools/agent/filelist_closure.py"


def _load():
    spec = importlib.util.spec_from_file_location("filelist_closure", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _core(root: Path, rel: str, text: str):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def test_core_closure_follows_depend_and_skips_headers(tmp_path):
    _core(tmp_path, "top/top.core", """CAPI=2:
name: "x:top:0.1"
filesets:
  files_rtl:
    depend:
      - x:pkg:0.1
    files:
      - rtl/top.sv
      - rtl/defs.svh
targets:
  default:
    filesets:
      - files_rtl
""")
    _core(tmp_path, "pkg/pkg.core", """CAPI=2:
name: "x:pkg:0.1"
filesets:
  files_rtl:
    files:
      - rtl/pkg.sv
targets:
  default:
    filesets:
      - files_rtl
""")
    (tmp_path / "top/rtl").mkdir(parents=True)
    (tmp_path / "top/rtl/top.sv").write_text("module top; endmodule\n")
    (tmp_path / "top/rtl/defs.svh").write_text("`define X 1\n")
    (tmp_path / "pkg/rtl").mkdir(parents=True)
    (tmp_path / "pkg/rtl/pkg.sv").write_text("package pkg; endpackage\n")

    mod = _load()
    index = mod.CoreIndex(tmp_path, {})
    c = index.closure(str(tmp_path / "top/top.core"))
    c.apply_profile()
    out = tmp_path / "out.f"
    c.write(out)
    text = out.read_text()
    assert "top/rtl/top.sv" in text
    assert "pkg/rtl/pkg.sv" in text
    assert "defs.svh" not in text.splitlines()[-1]
    assert "+incdir+" in text


def test_profile_mapping_include_and_exclude(tmp_path):
    _core(tmp_path, "top/top.core", """CAPI=2:
name: "x:top:0.1"
filesets:
  files_rtl:
    files:
      - rtl/a.sv
targets:
  default:
    filesets:
      - files_rtl
""")
    (tmp_path / "top/rtl").mkdir(parents=True)
    (tmp_path / "top/rtl/a.sv").write_text("module top; endmodule\n")
    (tmp_path / "extra").mkdir()
    (tmp_path / "extra/e.sv").write_text("module e; endmodule\n")
    mod = _load()
    profile = {"exclude": ["*/a.sv"], "include": ["extra/e.sv"]}
    c = mod.CoreIndex(tmp_path, profile).closure(str(tmp_path / "top/top.core"))
    c.apply_profile()
    assert not any(str(x).endswith("/a.sv") for x in c.files)
    assert any(str(x).endswith("/extra/e.sv") for x in c.files)


def test_missing_dependency_is_reported_not_silent(tmp_path):
    _core(tmp_path, "top/top.core", """CAPI=2:
name: "x:top:0.1"
filesets:
  files_rtl:
    depend:
      - x:missing:0.1
    files:
      - rtl/top.sv
targets:
  default:
    filesets:
      - files_rtl
""")
    (tmp_path / "top/rtl").mkdir(parents=True)
    (tmp_path / "top/rtl/top.sv").write_text("module top; endmodule\n")
    mod = _load()
    c = mod.CoreIndex(tmp_path, {}).closure(str(tmp_path / "top/top.core"))
    assert "x:missing" in c.missing
