"""P165.2: packaging rename guard (no top-level trace package)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_no_top_level_trace_package():
    assert not (ROOT / "src/trace").exists()
    assert (ROOT / "src/sv_query/trace/__init__.py").is_file()


def test_pyproject_installs_sv_query_package():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "sv_query*" in text
    assert '"sv_query.trace" = ["py.typed"]' in text
    assert "trace*" not in text.split("[tool.setuptools.packages.find]", 1)[1].split("[tool.setuptools.package-data]", 1)[0]
