"""
test_filelist_parity.py — [iter_193] 两个消费方必须解析出**同一份文件集**

背景: 过去 tracer 侧 (`SVCompiler.add_filelist`) 与 CLI 侧
(`cli._common._read_filelist`) 各有一套解析实现, 相对路径基准与嵌套解析规则不同 →
同一份 filelist 两侧结果不一致 (iter_190 记录, iter_192 只做到"结果一致"), 且
对实际存在的文件误报缺失。

iter_193 起两者共用 `trace.core.filelist.parse_filelist`。本测试是**不变量锁**:
对多种 filelist 场景断言两侧解析出的文件集完全一致 —— 一旦有人再引入第二套实现,
这里立刻失败。
"""
from pathlib import Path

import pytest

from cli._common import _read_filelist
from trace.core.compiler import SVCompiler
from trace.core.filelist import parse_filelist

SV_A = "module a; endmodule\n"
SV_B = "module b; endmodule\n"


def _tracer_files(filelist: str) -> set[str]:
    c = SVCompiler({}, log_level="ERROR")
    c.add_filelist(filelist)
    return {Path(k).name for k in c._sources}


def _cli_files(filelist: str, base_dir: Path) -> set[str]:
    return {Path(k).name for k in _read_filelist(filelist, base_dir)}


@pytest.fixture(autouse=True)
def _in_tmp_cwd(tmp_path, monkeypatch):
    """生产里两个消费方的"第二候选基准"都是 cwd (tracer 固定 cwd; CLI 由调用方传
    cwd/项目根) → 测试统一把 cwd 切到 tmp_path, 才能真实对比两侧。"""
    monkeypatch.chdir(tmp_path)


def test_parity_filelist_relative(tmp_path):
    """① 相对 filelist 所在目录。"""
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "a.sv").write_text(SV_A, encoding="utf-8")
    fl = tmp_path / "fl.f"
    fl.write_text("sub/a.sv\n", encoding="utf-8")

    assert _tracer_files(str(fl)) == {"a.sv"}
    assert _cli_files(str(fl), Path.cwd()) == {"a.sv"}


def test_parity_base_dir_relative(tmp_path):
    """② 相对 base_dir (cwd/项目根)。"""
    (tmp_path / "b.sv").write_text(SV_B, encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    fl = elsewhere / "fl.f"
    fl.write_text("b.sv\n", encoding="utf-8")

    assert _tracer_files(str(fl)) == {"b.sv"}
    assert _cli_files(str(fl), Path.cwd()) == {"b.sv"}


def test_parity_with_incdir_and_nested(tmp_path):
    """③ +incdir+ / +define+ / 嵌套 -f 混合场景, 两侧文件集一致。"""
    inc = tmp_path / "inc"
    inc.mkdir()
    (inc / "h.svh").write_text("`define W 4\n", encoding="utf-8")
    (tmp_path / "a.sv").write_text(SV_A, encoding="utf-8")
    (tmp_path / "b.sv").write_text(SV_B, encoding="utf-8")

    nested = tmp_path / "nested.f"
    nested.write_text("b.sv\n", encoding="utf-8")
    main = tmp_path / "main.f"
    main.write_text(
        "+incdir+inc\n"
        "+define+WIDTH=8\n"
        "a.sv\n"
        f"-f {nested.name}\n",
        encoding="utf-8",
    )

    spec = parse_filelist(str(main), base_dirs=[tmp_path])
    assert {Path(f).name for f in spec.files} == {"a.sv", "b.sv"}
    assert spec.include_dirs == [str(inc.resolve())]
    assert spec.defines.get("WIDTH") == "8"

    assert _tracer_files(str(main)) == {"a.sv", "b.sv"}
    assert _cli_files(str(main), Path.cwd()) == {"a.sv", "b.sv"}


def test_parity_missing_entries_recorded(tmp_path):
    """④ 缺失条目两侧都记录 (不静默), 且不影响存在的文件。"""
    (tmp_path / "a.sv").write_text(SV_A, encoding="utf-8")
    fl = tmp_path / "fl.f"
    fl.write_text("a.sv\ngone.sv\n", encoding="utf-8")

    spec = parse_filelist(str(fl), base_dirs=[tmp_path])
    assert [Path(f).name for f in spec.files] == ["a.sv"]
    assert spec.missing == ["gone.sv"]
    assert _tracer_files(str(fl)) == {"a.sv"}
    assert _cli_files(str(fl), Path.cwd()) == {"a.sv"}


def test_missing_filelist_raises_from_both(tmp_path):
    """⑤ filelist 本身不存在 → 两个入口都明确报错 (不是静默空结果)。"""
    import pytest

    missing = str(tmp_path / "no_such.f")
    with pytest.raises(FileNotFoundError):
        parse_filelist(missing)
    with pytest.raises(FileNotFoundError):
        SVCompiler({}, log_level="ERROR").add_filelist(missing)
    with pytest.raises(FileNotFoundError):
        _read_filelist(missing, Path.cwd())
