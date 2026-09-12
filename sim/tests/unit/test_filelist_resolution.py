"""
test_filelist_resolution.py — [iter_192] filelist 相对路径的两种基准都必须能解析

背景: 项目里有**两套** filelist 加载器, 相对路径规则不同:
  - `src/trace/core/compiler.py::add_filelist` (编译入口): 相对 **filelist 所在目录**
  - `src/cli/_common.py::_read_filelist` (CLI 辅助, 供 SVA/coverage 等用):

修复前 CLI 侧只按 base_dir (cwd) 解析 → 与 tracer 侧结果不一致, 且对**实际存在**
的文件误报 "条目不存在" (iter_190 加的告警变成噪声)。实测 (cwd 与 filelist 目录不同):
    CLI 侧 0 个文件 / tracer 侧 1 个文件。

现在 CLI 侧按**两个候选基准**依次尝试 (filelist 目录 → base_dir), 都不中才告警。
本测试把两种约定 + 缺失情形都钉死 (将来若把两套加载器统一, 这里是安全网)。
"""
from pathlib import Path

import pytest

from cli._common import _read_filelist

SRC = "module m; endmodule\n"


def test_filelist_relative_entry_resolves(tmp_path):
    """① 相对 filelist 所在目录 (tracer 侧约定) 必须能加载。"""
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "m.sv").write_text(SRC, encoding="utf-8")
    fl = tmp_path / "fl.f"
    fl.write_text("sub/m.sv\n", encoding="utf-8")

    # base_dir 故意指向别处 (模拟 cwd ≠ filelist 目录)
    sources = _read_filelist(str(fl), Path("/"))
    assert len(sources) == 1, f"filelist 目录相对路径未解析: {sources}"
    assert sources[next(iter(sources))] == SRC


def test_base_dir_relative_entry_resolves(tmp_path):
    """② 相对 base_dir (cwd/项目根) 必须能加载 (仓库内 industrial_filelists 的约定)。"""
    (tmp_path / "m.sv").write_text(SRC, encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    fl = elsewhere / "fl.f"
    fl.write_text("m.sv\n", encoding="utf-8")

    sources = _read_filelist(str(fl), tmp_path)
    assert len(sources) == 1, f"base_dir 相对路径未解析: {sources}"


def test_missing_entry_warns_and_skips(tmp_path, caplog):
    """③ 两个基准都不中 → 不计入 + 明确告警 (不静默)。"""
    (tmp_path / "ok.sv").write_text(SRC, encoding="utf-8")
    fl = tmp_path / "fl.f"
    fl.write_text("ok.sv\nnope_missing.sv\n", encoding="utf-8")

    with caplog.at_level("WARNING"):
        sources = _read_filelist(str(fl), tmp_path)
    assert len(sources) == 1, sources
    assert any("nope_missing.sv" in rec.getMessage() for rec in caplog.records), (
        [rec.getMessage() for rec in caplog.records]
    )


def test_missing_filelist_raises_clear_error(tmp_path):
    """④ filelist 本身不存在 → 明确报错 (不是静默返回空)。"""
    with pytest.raises(FileNotFoundError) as ei:
        _read_filelist(str(tmp_path / "no_such.f"), tmp_path)
    assert "Filelist not found" in str(ei.value)
