"""
inputs.py — benchmark 输入 (filelist / 文件列表) 的统一构建 [iter_187]

背景: benchmark 的输入过去散落在测试的 `_ensure_filelist()` 和 /tmp 手工文件里,
baseline JSON 记的 `/tmp/pulp_axi_xbar_pr2.f` 重启即失, 导致:
- baseline 无法复现 (2026-08 的三个 baseline 全部与当前行为不符, 见
  `baselines/README.md`);
- 测试与手工命令用的输入可能不是同一份。

本模块是**唯一**输入构建点: 从现成开源语料 (`~/my_dv_proj/openrtl/`) 现场
生成 filelist, 源缺失时返回 None (调用方 skip, 不伪造)。filelist 落在
`CACHE_DIR` 下 (默认 `/tmp`), 每次按源文件集合重新生成, 保证行为可复现。
"""
from __future__ import annotations

import os
from pathlib import Path

# 开源语料根 (缺失时相关输入不可用 → 调用方 skip)
OPENRTL = Path(os.path.expanduser("~/my_dv_proj/openrtl"))
AXI = OPENRTL / "axi"
COMMON_CELLS = OPENRTL / "common_cells"
VERILOG_AXI = OPENRTL / "verilog-axi"
PICORV32 = OPENRTL / "picorv32" / "picorv32.v"

# benchmark 仓库内的 fixture (wrapper)
REPO = Path(__file__).resolve().parents[2]
PR5_WRAPPER = REPO / "sim" / "tests" / "fixtures" / "bench_wrappers" / "pr5_wrap.sv"

# filelist 落点 (可被 SVQ_BENCH_INPUT_DIR 覆盖)
INPUT_DIR = Path(os.environ.get("SVQ_BENCH_INPUT_DIR", "/tmp"))


def _write(path: Path, lines: list[str]) -> str:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def ensure_axi_filelist() -> str | None:
    """pulp axi + common_cells 语料 filelist (含 deprecated/, 供 axi 旧名引用)。

    含 `+incdir+` → 会走 SVCompiler 的私有 SourceManager 分支
    (iter_185 修的就是这条路径的生命周期)。
    """
    if not (AXI / "src").exists() or not (COMMON_CELLS / "src").exists():
        return None
    lines = [f"+incdir+{AXI}/include/", f"+incdir+{COMMON_CELLS}/include/"]
    lines += sorted(str(p) for p in (AXI / "src").glob("*.sv"))
    lines += sorted(str(p) for p in (COMMON_CELLS / "src").glob("*.sv")
                    if not p.name.endswith("_tb.sv"))
    dep = COMMON_CELLS / "src" / "deprecated"
    if dep.exists():
        lines += sorted(str(p) for p in dep.glob("*.sv"))
    return _write(INPUT_DIR / "pulp_axi_xbar_pr2.f", lines)


def ensure_pr5_wrap_filelist() -> str | None:
    """axi 语料 + 深结构 wrapper (`pr5_wrap`, 真实 Cfg) — pr5 结构基准输入。"""
    base = ensure_axi_filelist()
    if base is None or not PR5_WRAPPER.exists():
        return None
    text = Path(base).read_text(encoding="utf-8")
    if "pr5_wrap.sv" in text:
        return base
    path = INPUT_DIR / "pr5_wrap.f"
    return _write(path, [*text.split("\n"), str(PR5_WRAPPER)])


def ensure_verilog_axi_filelist() -> str | None:
    """verilog-axi (alexforencich) rtl/*.v filelist — 无 include 依赖。"""
    rtl = VERILOG_AXI / "rtl"
    if not rtl.exists():
        return None
    files = sorted(str(p) for p in rtl.glob("*.v"))
    if not files:
        return None
    return _write(INPUT_DIR / "verilog-axi.f", files)


def picorv32_file() -> str | None:
    """picorv32 单文件 (自包含, 无子实例)。"""
    return str(PICORV32) if PICORV32.exists() else None
