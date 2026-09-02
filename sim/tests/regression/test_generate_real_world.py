# test_generate_real_world.py — Real-world generate 覆盖 (iter_069 重建版)
# [iter_069 2026-08-29] 原文件依赖 ZipCPU 单文件 + --no-strict (UnknownModule),
# 违反纪律 #1 已删除。重建: 用 ZipCPU **全 rtl (51 文件)** — iter_058 验证可
# **strict 编译** — 修正原测试"单文件缺依赖"的方式错误 (方豆: "修复语法错误,
# 让编译通过。可能本来测试目的也有不对的")。
#
# 测试目的 (保留): 真实 generate-heavy RTL 在 sv_query 上 strict 编译不 crash +
# 图规模合理 + generate 相关信号存在。真实 RTL 的 generate 用法比 synthetic
# fixture 复杂 (嵌套 generate for + 参数化实例 + 条件 instantiate)。
"""
[Plan F1.5 2026-08-12 + iter_069 重建] Real-world generate 覆盖

用 ZipCPU (Gisselquist Tech, GPL) 全 rtl 验证真实 generate-heavy RTL:
- 51 文件 (rtl/**/*.v), strict 编译 (无 --no-strict, 纪律 #1)
- wbxbar (49 generate lines) / idecode (25) / zipcore / axi2axilite 等
- 验证: strict 编译成功 + 图规模下限 + 关键 generate 信号存在

[铁律13] 金标准测试
"""
import glob
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer  # noqa: E402

ZIPCPU_RTL = Path("/Users/fundou/my_dv_proj/openrtl/zipcpu/rtl")


@pytest.fixture(scope="module")
def zipcpu_graph():
    """ZipCPU 全 rtl strict 编译 (iter_058 验证可编译, 51 文件)."""
    files = sorted(glob.glob(str(ZIPCPU_RTL / "**" / "*.v"), recursive=True))
    assert len(files) >= 40, f"ZipCPU rtl 文件数异常: {len(files)}"
    sources = {}
    for f in files:
        try:
            sources[f.split("/")[-1]] = Path(f).read_text(errors="replace")
        except OSError:
            continue
    tracer = UnifiedTracer(sources=sources)
    tracer.build_graph()  # strict=True (默认) — 编译不过即抛错
    return tracer.get_graph()


class TestRealWorldGenerateStrict:
    """[iter_069] 真实 generate RTL strict 编译 + 图行为"""

    def test_strict_compile_succeeds(self, zipcpu_graph):
        """[Golden] ZipCPU 全 rtl strict 编译成功 (不 crash)"""
        assert zipcpu_graph is not None, "strict 编译应成功"

    def test_graph_scale_reasonable(self, zipcpu_graph):
        """[Golden] 图规模合理 (51 文件真实 RTL, 3751 nodes baseline)"""
        n_nodes = len(zipcpu_graph.nodes())
        assert n_nodes > 1000, f"真实 RTL 图应 >1000 节点, 实际 {n_nodes}"
        n_edges = len(list(zipcpu_graph.edges()))
        assert n_edges > 1000, f"真实 RTL 图应 >1000 边, 实际 {n_edges}"

    def test_generate_heavy_modules_present(self, zipcpu_graph):
        """[Golden] generate-heavy 模块 (idecode/zipcore) 的节点存在

        原测试验证 wbxbar (在 zipcpu/sim/rtl, 不在 rtl/) — 重建版用 rtl/ 内的
        generate-heavy 模块: idecode (指令译码, 25 generate lines) 和 zipcore
        (核心, 大量 generate if/for). 这些经 generate 展开后的信号应出现在图.
        """
        node_ids = set(zipcpu_graph.nodes())
        # idecode 的 generate 展开信号
        idecode_hits = [n for n in node_ids if str(n).startswith('idecode')]
        assert len(idecode_hits) > 50, f"idecode generate 展开信号应存在: {len(idecode_hits)}"
        # zipcore 核心信号
        zipcore_hits = [n for n in node_ids if str(n).startswith('zipcore')]
        assert len(zipcore_hits) > 100, f"zipcore 信号应存在: {len(zipcore_hits)}"

    def test_cross_module_driver_edges(self, zipcpu_graph):
        """[Golden] 真实 RTL 有跨模块 DRIVER 边 (generate 实例化的模块间连接)"""
        from trace.core.graph.models import EdgeKind

        driver_edges = 0
        for u, v in zipcpu_graph.edges():
            e = zipcpu_graph.get_edge(u, v)
            if e and e.kind == EdgeKind.DRIVER:
                driver_edges += 1
        assert driver_edges > 100, f"真实 RTL 应有大量 DRIVER 边, 实际 {driver_edges}"
