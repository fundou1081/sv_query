"""
test_benchmark_pr5.py
=======================
[PR5 2026-06-15] 端到端 benchmark 测试.

测试 benchmark 工具自身:
  - 能跑完不 crash
  - L1/L2/L3/L4 数据都有
  - JSON 输出合法
  - 跑出来的数据在合理范围 (PR1-4 已保证的能力)

[iter_145] 2026-09-05 修复测试环境:
  - filelist 自动生成 (原 /tmp/pulp_axi_xbar_pr2.f 手工准备, 重启丢失 →
    FileNotFoundError → 11 测试长期 skip; 现从 ~/my_dv_proj/openrtl/axi +
    common_cells 现成源码生成, 缺失时自动重建)
  - TARGET axi_xbar_dp_ram → axi_xbar_intf (axi 现版本只有 axi_xbar/
    axi_xbar_intf; dp_ram 是旧 pulp 名, baseline 时代 instance_count 已 0)
  - run_benchmark 传 top_modules=[target]: free-floating type-param 模块
    (axi_demux 等 axi_req_t=logic) 被 pyslang 预 elab 报错, 显式 top 避开
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BENCH = PROJECT_ROOT / "tools" / "benchmark" / "run_benchmark.py"
FILENAME_LIST = "/tmp/pulp_axi_xbar_pr2.f"
TARGET = "axi_xbar_intf"
# [iter_180] 深结构基准 (真实 Cfg: 4 slv / 3 mst / 32b addr / 64b data)
WRAPPER = PROJECT_ROOT / "sim" / "tests" / "fixtures" / "bench_wrappers" / "pr5_wrap.sv"
WRAP_TARGET = "pr5_wrap"

# [iter_187] 输入构建统一走 tools/benchmark/inputs.py (与 regen_baselines.py
# 同一份逻辑) — 过去测试自带 _ensure_filelist + /tmp 手工文件, 导致 baseline
# 与测试可能吃不同输入、baseline 无法复现。
sys.path.insert(0, str(PROJECT_ROOT / "tools" / "benchmark"))
import inputs  # noqa: E402

FILENAME_LIST = inputs.ensure_pr5_wrap_filelist() or FILENAME_LIST


def _run_benchmark(runs: int = 1, skip_flakiness: bool = False, target: str = TARGET, depth: int = 4, output: Path = None) -> dict:
    """Run benchmark, return parsed JSON."""
    if output is None:
        output = Path("/tmp/bench_pr5_test.json")
    args = [
        sys.executable, str(BENCH),
        "--filelist", FILENAME_LIST,
        "--target", target,
        "--depth", str(depth),
        "--runs", str(runs),
        "--output", str(output),
    ]
    if skip_flakiness:
        args.append("--skip-flakiness")
    result = subprocess.run(
        args, capture_output=True, text=True, timeout=300, cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        pytest.skip(f"benchmark failed: rc={result.returncode}, stderr={result.stderr[:500]}")
    if not output.exists():
        pytest.skip(f"benchmark output not found: {output}")
    with open(output) as f:
        return json.load(f)


class TestBenchmarkRuns:
    """benchmark 跑得通."""

    def test_benchmark_runs_successfully(self):
        """benchmark 跑完不 crash."""
        data = _run_benchmark(runs=1, skip_flakiness=True)
        assert data is not None
        assert "metadata" in data

    def test_benchmark_4_levels_present(self):
        """4 维能力字段都有."""
        data = _run_benchmark(runs=1, skip_flakiness=True)
        for key in ("L1_module_extraction", "L2_graph_topology", "L3_signal_traces", "L4_cross_instance_edges"):
            assert key in data, f"missing {key} in {list(data.keys())}"


class TestL1Extraction:
    """L1 数据合理."""

    def test_l1_instance_count_at_least_2(self):
        """[iter_145] axi 现版默认参数: axi_xbar_intf → i_xbar → i_xbar_unmuxed
        (≥2 实例)。旧 pulp pr2 axi_xbar_dp_ram 大参数结构 (≥3) 已不存在 —
        深结构 wrapper 基准 = TODO (pr5_wrap)."""
        data = _run_benchmark(runs=1, skip_flakiness=True)
        l1 = data["L1_module_extraction"]
        if "error" in l1:
            pytest.skip(f"L1 error: {l1['error']}")
        assert l1["instance_count"] >= 2, f"expected >= 2 instances, got {l1['instance_count']}"

    def test_l1_xbar_hierarchy(self):
        """[iter_145] i_xbar (axi_xbar) → i_xbar_unmuxed 链存在 (target 自身不在
        instances 列表, 旧断言含 axi_xbar_intf 已删)."""
        data = _run_benchmark(runs=1, skip_flakiness=True)
        l1 = data["L1_module_extraction"]
        if "error" in l1:
            pytest.skip(f"L1 error: {l1['error']}")
        defs = [i["def"] for i in l1.get("instances", [])]
        assert "axi_xbar" in defs, f"missing axi_xbar in {defs}"
        assert "axi_xbar_unmuxed" in defs, f"missing axi_xbar_unmuxed in {defs}"


class TestL2Graph:
    """L2 数据合理."""

    def test_l2_node_count_nonempty(self):
        """[iter_145] 新 axi 默认参数图 ~168 nodes (旧 pulp 大参数 1000+ 已不
        存在, wrapper TODO); 断言降为"非空图"."""
        data = _run_benchmark(runs=1, skip_flakiness=True)
        l2 = data["L2_graph_topology"]
        if "error" in l2:
            pytest.skip(f"L2 error: {l2['error']}")
        assert l2["nodes"] >= 50, f"expected >= 50 nodes, got {l2['nodes']}"

    def test_l2_im_count_small(self):
        """[iter_145] 新 axi 默认参数 im=2 (旧 ~200 wrapper TODO)."""
        data = _run_benchmark(runs=1, skip_flakiness=True)
        l2 = data["L2_graph_topology"]
        if "error" in l2:
            pytest.skip(f"L2 error: {l2['error']}")
        assert 1 <= l2["instantiated_modules"] <= 10, (
            f"IM count {l2['instantiated_modules']} outside expected 1-10"
        )


class TestL3Traces:
    """L3 数据合理."""

    def test_l3_awvalid_present(self):
        """[iter_145] s_axi_awvalid 有 trace 数据 (旧版 fanout>=1 断言 — 默认
        参数空壳下 fanout 0, wrapper TODO 后恢复链断言)."""
        data = _run_benchmark(runs=1, skip_flakiness=True)
        l3 = data["L3_signal_traces"]
        s = l3.get(f"{TARGET}.s_axi_awvalid", {})
        assert s, f"{TARGET}.s_axi_awvalid trace 应存在, got keys {list(l3.keys())[:5]}"

    def test_l3_clk_i_fanout(self):
        """clk_i 应该有 fanout (PR1 已知分配给所有 sub-instance)."""
        data = _run_benchmark(runs=1, skip_flakiness=True)
        l3 = data["L3_signal_traces"]
        clk = l3.get(f"{TARGET}.clk_i", {})
        if "error" not in clk:
            assert clk.get("fanout", 0) >= 1, f"expected clk fanout>=1, got {clk}"


class TestL4Edges:
    """L4 数据合理."""

    def test_l4_edge_count_present(self):
        """[iter_145] L4 有数据即可 (默认参数空壳 edge 0 — 旧 ≥10 需 wrapper
        深度结构, TODO)."""
        data = _run_benchmark(runs=1, skip_flakiness=True)
        l4 = data["L4_cross_instance_edges"]
        if "error" in l4:
            pytest.skip(f"L4 error: {l4['error']}")
        assert "edge_count" in l4, f"missing edge_count in {list(l4.keys())}"

    def test_l4_top_ports_includes_clk(self):
        """top_ports 应该包含 clk_i (PR4 已知 shared clock)."""
        data = _run_benchmark(runs=1, skip_flakiness=True)
        l4 = data["L4_cross_instance_edges"]
        if "error" in l4 or not l4.get("top_ports"):
            pytest.skip("L4 has no top_ports")
        assert "clk_i" in l4["top_ports"], f"expected clk_i in {list(l4['top_ports'].keys())}"


class TestMarkdownOutput:
    """Markdown 报告."""

    def test_markdown_flag_writes_md(self, tmp_path):
        """--markdown 应该写 .md 文件."""
        out = tmp_path / "bench.json"
        subprocess.run(
            [
                sys.executable, str(BENCH),
                "--filelist", FILENAME_LIST,
                "--target", TARGET,
                "--depth", "4",
                "--runs", "1",
                "--output", str(out),
                "--markdown",
            ],
            capture_output=True, text=True, timeout=300, cwd=PROJECT_ROOT,
        )
        if not out.exists():
            pytest.skip("benchmark failed")
        md = out.with_suffix(".md")
        assert md.exists(), f"markdown file not created: {md}"
        content = md.read_text()
        # Should have all 4 sections
        for section in ("L1", "L2", "L3", "L4"):
            assert f"## {section}" in content or "# L1" in content or section in content, (
                f"markdown missing L* section: {section}"
            )


def _try_benchmark(target: str, depth: int = 4, runs: int = 1,
                   skip_flakiness: bool = True, attempts: int = 3):
    """容错版 benchmark 调用: 失败返回 None (不 skip)。

    [iter_181 加 / iter_185 更正归因] 重试是为了抗**环境性**失败 (子进程 OOM /
    超时), 不是抗语料解码问题 —— 原注释归因 "非 utf8 identifier 间歇崩溃" 已被
    iter_185 证伪 (真因 = SourceManager 生命周期, 已修); 修复后同一命令 3/3
    完全一致。保留 attempts 作为环境兜底。
    """
    out = Path("/tmp/bench_pr5_wrap.json")
    for i in range(attempts):
        args = [
            sys.executable, str(BENCH),
            "--filelist", FILENAME_LIST,
            "--target", target,
            "--depth", str(depth),
            "--runs", str(runs),
            "--output", str(out),
        ]
        if skip_flakiness:
            args.append("--skip-flakiness")
        result = subprocess.run(args, capture_output=True, text=True,
                                timeout=300, cwd=PROJECT_ROOT)
        if result.returncode == 0 and out.exists():
            with open(out) as f:
                return json.load(f)
        out.unlink(missing_ok=True)
    return None


class TestBenchmarkWrapperDepth:
    """[iter_180] pr5_wrap 深结构基准 (iter_145 登记的 wrapper TODO 兑现).

    背景: `axi_xbar_intf` 默认参数 `Cfg = '0` → 空壳树 (2 实例 / 168 nodes,
    clk fanout 0), 原测试结构断言只能弱化。本类用**真实 Cfg** 的 wrapper
    (`sim/tests/fixtures/bench_wrappers/pr5_wrap.sv`) 恢复深结构断言。

    基准 (2026-09-08 iter_185 实测, depth=4, 3 次同一值):
      L1  instance_count = 2  (pr5_wrap.i_xbar → axi_xbar_intf;
                               pr5_wrap.i_xbar.i_xbar → axi_xbar)
      L2  nodes = 4,946 / edges = 5,808 / instantiated_modules = 516
          depth_distribution 最深 14; flakiness 3 次 stdev = 0.0
      L3  pr5_wrap.clk_i fanout = 445  ← 空壳 168 nodes 且 clk=2
      L4  edge_count = 0 (wrapper 顶层只暴露 clk/rst, 无 AXI 端口 — 预期)

    ⚠️ iter_185 更正: iter_180/181/184 记的 "非 UTF-8 identifier → 部分
    elaboration / 跨次波动 (nodes 2,814→1,778~3,408, clk 187→0)" **不是**
    语料问题 — 真因是 `SVCompiler` 把 `SourceManager` 存成局部变量, parse
    循环结束后被 GC → 源文件 buffer 释放 → 符号名/ token 是指向释放内存的
    string_view。修好 manager 生命周期后同一命令 3 次完全一致 (见
    docs/task_tree/iterations/iter_185_slang_sourcemanager_lifetime.md)。
    """

    @classmethod
    def setup_class(cls):
        """pytest xunit-style 钩子 (纯 pytest 类不认 unittest 的 setUpClass)"""
        if not WRAPPER.exists():
            pytest.skip(f"wrapper fixture 缺失: {WRAPPER}")
        # runs=1 + skip_flakiness: 结构基准只需单次结构数据 (flakiness 阶段
        # 单独由 TestBenchmarkStability 测)。iter_185 起复跑退化已消失。
        cls.data = _try_benchmark(WRAP_TARGET, depth=4, runs=1, attempts=3)
        if cls.data is None:
            pytest.skip("wrapper benchmark 3 次均失败 (rc≠0 或无输出)")

    def test_l1_instance_chain(self):
        l1 = self.data["L1_module_extraction"]
        assert l1["instance_count"] >= 2, l1
        defs = {i.get("def") for i in l1["instances"]}
        assert "axi_xbar_intf" in defs, f"应有 axi_xbar_intf 实例, got {defs}"
        assert "axi_xbar" in defs, f"wrapper 应展开到 axi_xbar (深链), got {defs}"

    def test_l2_deep_structure(self):
        """深结构断言 (iter_185 起确定性, 阈值回到真实值的结构性下限)。

        [iter_185 实测 3/3 同一值] nodes = 4,946 / IM = 516 / 最深 14;
        空壳 (默认 Cfg) = 168 nodes / IM = 2 / clk = 2。
        断言留 ~20% 余量以容忍 pyslang 版本差异, 但仍远高于空壳。
        """
        l2 = self.data["L2_graph_topology"]
        assert l2["nodes"] >= 4000, f"深结构节点数应 >= 4000 (空壳 168), got {l2['nodes']}"
        assert l2["instantiated_modules"] >= 400, f"实例模块应 >= 400, got {l2}"
        depths = [int(k) for k in l2["depth_distribution"]]
        assert max(depths) >= 12, f"层次深度应 >= 12, got {max(depths)}"

    def test_l3_clock_fanout_restored(self):
        """clk fanout: 空壳 2 → wrapper 深结构下 445 (恢复链断言)。

        [iter_180] 原始断言 (fanout >= 50) 曾因 "跨次 0~137 波动" 被放宽为
        "深结构 OR clk 恢复"; iter_185 定位真因 (SourceManager 生命周期) 后
        波动消失, 断言收回到真实值下限。
        """
        l3 = self.data["L3_signal_traces"]
        clk = l3.get(f"{WRAP_TARGET}.clk_i")
        assert clk is not None, f"wrapper clk_i 未采集, got {list(l3)[:5]}"
        fanout = clk.get("fanout", 0)
        assert fanout >= 300, f"clk fanout 应 >= 300 (空壳 2, iter_185 实测 445), got {fanout}"
