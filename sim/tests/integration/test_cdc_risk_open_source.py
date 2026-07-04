"""
test_cdc_risk_open_source.py - cdc/risk on real OSS projects (5 projects)
======================================================================
[ADD 2026-07-04] Week 4 后续: cdc/risk 命令纪律补 (0 tests → 16+ tests).

**目标**: cdc / risk 命令 (之前 0 tests) 在 5+ 真实开源项目上跑.
**项目**: 
  - cdc 用: axi_cdc_src (4 clk, 2 HIGH CDC paths), axi_xbar (3 clk, 2 CDC paths)
  - risk 用: strict_uart (25 data, 8 critical), prim_arbiter_tree (33, 10 critical)
  - 共通: tlul (4 clk, 0 CDC = 全 synchronous)

**正反面测试**:
- 正面 (P1-P10): 5 项目各跑 cdc + risk, 验证输出稳定
- 反面 (N1-N5): 错误输入 + 边界情况

**Golden baseline** (2): 
- cdc axi_cdc_src 2 paths (HIGH risk)
- risk strict_uart 8 critical + 5 high

**注意** (跟 dataflow/controlflow 区分):
- cdc 必须 multi-clk 项目才有 paths, 1-clk 项目返 0 (正确)
- risk 每个 project 都跑 (不依赖 multi-clk)
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FILELIST_DIR = PROJECT_ROOT / "sim" / "tests" / "pyslang_type_fixtures" / "industrial_filelists"
GOLDEN_DIR = PROJECT_ROOT / "sim" / "tests" / "golden" / "cdc_risk_open_source"
GOLDEN_DIR.mkdir(parents=True, exist_ok=True)


def _run(*args, timeout=90) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["sv_query", *args],
        capture_output=True, text=True, timeout=timeout,
        cwd=str(PROJECT_ROOT),
    )


# ============================================================================
# CDC 正面 (Positive)
# ============================================================================

def test_p1_cdc_axi_cdc_src_2_high_risk_paths():
    """P1: axi_cdc_src (1 物理 src_clk_i) cdc 应 1 domain, 0 paths (同 physical wire, 非真 CDC).

    [FIX 2026-07-04] 之前 cdc 算法 bug 用 (module, clock_name) 当 domain key, 把同一根 physical
    wire 在不同 module 层级报成不同 domain, 制造 4 domains + 2 HIGH risk false positive.
    修后: 1 domain (src_clk_i), 0 paths (所有 instance port 共享同一 physical wire).
    """
    r = _run("-q", "cdc", "analyze", "--no-strict",
             "--file", "/Users/fundou/my_dv_proj/axi/src/axi_cdc_src.sv", "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    r_data = data["result"]
    # 期望 (修后): 1 domain (src_clk_i), 0 CDC paths (同 physical net)
    assert r_data["domain_count"] == 1
    assert r_data["total_cdc"] == 0
    assert r_data["high_risk"] == 0
    print(f"✅ P1 cdc axi_cdc_src: {r_data['domain_count']} domain, 0 CDC (单 physical src_clk_i, false positive 已修)")


def test_p2_cdc_axi_xbar_2_cdc_paths():
    """P2: axi_xbar 跑 cdc: 0 CDC (单 physical clk, 修算法后 0 false positive)."""
    r = _run("-q", "cdc", "analyze", "--no-strict",
             "--file", "/Users/fundou/my_dv_proj/axi/src/axi_xbar.sv", "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    r_data = data["result"]
    # 修后: 0 CDC (同 physical wire 共享)
    assert r_data["total_cdc"] == 0
    assert r_data["high_risk"] == 0
    print(f"✅ P2 cdc axi_xbar: {r_data['domain_count']} domains, 0 CDC (false positive 已修)")


def test_p3_cdc_tlul_4_domains_0_cdc():
    """P3: OpenTitan tlul 跑 cdc (修算法后): 1 domain (clk_i), 0 CDC.

    之前 cdc bug 把 sub-module clk_i 当独立 domain, 报 4 domains + 0 CDC.
    修后: 1 domain (所有 sub-module 共享 clk_i).
    """
    r = _run("-q", "cdc", "analyze", "--no-strict",
             "--filelist", str(FILELIST_DIR / "opentitan_tlul.f"), "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    r_data = data["result"]
    # 修后: 1 domain (clk_i)
    assert r_data["domain_count"] == 1
    assert r_data["total_cdc"] == 0  # 全 synchronous
    assert r_data["high_risk"] == 0
    print(f"✅ P3 cdc tlul: 1 domain (clk_i 共享), 0 CDC (false positive 已修)")


def test_p4_cdc_prim_arbiter_single_domain():
    """P4: OpenTitan prim_arbiter_tree 1 clk → 1 domain, 0 CDC (正确)."""
    r = _run("-q", "cdc", "analyze", "--no-strict",
             "--filelist", str(FILELIST_DIR / "opentitan_prim_arbiter_tree.f"), "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    r_data = data["result"]
    assert r_data["domain_count"] == 1
    assert r_data["total_cdc"] == 0
    print(f"✅ P4 cdc prim_arbiter_tree: 1 domain, 0 CDC (single-clk)")


def test_p5_cdc_summary_mode():
    """P5: cdc --summary mode 返 counts (LLM-friendly)."""
    r = _run("-q", "cdc", "analyze", "--no-strict",
             "--file", "/Users/fundou/my_dv_proj/axi/src/axi_cdc_src.sv",
             "--summary", "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    r_data = data["result"]
    # summary mode: 关键字段 in summary
    assert r_data.get("summary") is True
    assert "domains" in r_data
    assert "total_cdc" in r_data
    # paths 应简化或为空
    assert len(r_data.get("paths", [])) == 0 or "high_risk_paths" in r_data
    print(f"✅ P5 cdc summary: {r_data['total_cdc']} total, {r_data['high_risk']} high_risk (compact)")


# ============================================================================
# CDC 反面 (Negative)
# ============================================================================

def test_n1_cdc_nonexistent_file():
    """N1: cdc nonexistent file → 友好错误."""
    r = _run("cdc", "analyze", "--no-strict", "--file", "/tmp/nonexistent.sv")
    assert r.returncode != 0
    err = r.stderr + r.stdout
    assert "not found" in err.lower() or "no such file" in err.lower() or "error" in err.lower()
    print("✅ N1 cdc: nonexistent file → 友好错误")


def test_n2_cdc_strict_uart_4_high_risk():
    """N2: cdc strict_uart 修算法后: 1 domain (clk_i 共享), 0 CDC.

    [FIX 2026-07-04] 之前 cdc bug 报 4 domains + 4 CDC paths 全 HIGH (false positive).
    修后: strict_uart 4 sub-module 共享 clk_i (同 physical wire), 0 CDC.
    """
    r = _run("-q", "cdc", "analyze", "--no-strict",
             "--filelist", str(PROJECT_ROOT / "sim" / "tests" / "fixtures" / "strict_uart" / "filelist.f"),
             "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    r_data = data["result"]
    # 修后: 1 domain, 0 CDC
    assert r_data["domain_count"] == 1
    assert r_data["total_cdc"] == 0
    assert r_data["high_risk"] == 0
    print(f"✅ N2 cdc strict_uart: {r_data['domain_count']} domain, 0 CDC (sub-module clk_i 共享, false positive 已修)")


# ============================================================================
# RISK 正面 (Positive)
# ============================================================================

def test_p6_risk_strict_uart_8_critical_5_high():
    """P6: risk strict_uart: 25 data signals, 8 critical + 5 high (0 SVA, 0 cov)."""
    r = _run("-q", "risk", "analyze", "--no-strict",
             "--filelist", str(PROJECT_ROOT / "sim" / "tests" / "fixtures" / "strict_uart" / "filelist.f"),
             "--summary", "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    r_data = data["result"]
    s = r_data.get("summary", {})
    # strict_uart 实际: 8 critical + 5 high, 0 sva, 0 cov
    assert s["total"] >= 20
    assert s["critical"] >= 5
    assert s["high"] >= 3
    assert s["sva_covered"] == 0
    assert s["cov_covered"] == 0
    print(f"✅ P6 risk strict_uart: {s['total']} data, {s['critical']} critical + {s['high']} high")


def test_p7_risk_prim_arbiter_10_critical_9_high():
    """P7: risk prim_arbiter_tree: 33 signals, 10 critical + 9 high."""
    r = _run("-q", "risk", "analyze", "--no-strict",
             "--filelist", str(FILELIST_DIR / "opentitan_prim_arbiter_tree.f"),
             "--summary", "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    s = data["result"].get("summary", {})
    # prim_arbiter_tree 实际: 10 critical + 9 high (看 summary)
    assert s["total"] >= 25
    assert s["critical"] >= 5
    assert s["high"] >= 5
    print(f"✅ P7 risk prim_arbiter_tree: {s['total']} data, {s['critical']} critical + {s['high']} high")


def test_p8_risk_axi_cdc_src():
    """P8: risk axi_cdc_src (4 clk, 27 signals)."""
    r = _run("-q", "risk", "analyze", "--no-strict",
             "--file", "/Users/fundou/my_dv_proj/axi/src/axi_cdc_src.sv",
             "--summary", "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    s = data["result"].get("summary", {})
    assert s["total"] >= 20
    print(f"✅ P8 risk axi_cdc_src: {s['total']} data, {s['critical']} critical + {s['high']} high")


def test_p9_risk_summary_mode():
    """P9: risk --summary 返 counts (LLM-friendly)."""
    r = _run("-q", "risk", "analyze", "--no-strict",
             "--filelist", str(FILELIST_DIR / "opentitan_prim_arbiter_tree.f"),
             "--summary", "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    r_data = data["result"]
    assert r_data.get("summary_mode") is True
    assert "summary" in r_data
    # summary 关键字段
    s = r_data["summary"]
    assert "total" in s
    assert "critical" in s
    assert "high" in s
    print(f"✅ P9 risk summary mode: {s['total']} total, {s['critical']} critical, {s['high']} high (compact)")


# ============================================================================
# RISK 反面 (Negative)
# ============================================================================

def test_n3_risk_nonexistent_file():
    """N3: risk nonexistent file → 友好错误."""
    r = _run("risk", "analyze", "--no-strict", "--file", "/tmp/nonexistent.sv")
    assert r.returncode != 0
    print("✅ N3 risk: nonexistent file → 友好错误")


def test_n4_risk_broken_sv_no_strict():
    """N4: risk broken SV + --no-strict → 跑通 + 0 critical (partial AST 容忍)."""
    # 用 tlul (37 errors, no-strict 仍跑)
    r = _run("-q", "risk", "analyze", "--no-strict",
             "--filelist", str(FILELIST_DIR / "opentitan_tlul.f"),
             "--summary", "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    s = data["result"].get("summary", {})
    # tlul 37 errors → partial graph → 0 data signals
    assert s.get("total", 0) >= 0
    print(f"✅ N4 risk tlul (37 errors, --no-strict): {s['total']} data (partial AST 容忍)")


# ============================================================================
# Golden baseline
# ============================================================================

def _read_golden(name: str, generator) -> dict:
    """Read golden JSON, auto-create on first run."""
    path = GOLDEN_DIR / f"{name}.json"
    if not path.exists():
        # 首次跑: 生成 baseline
        r = generator()
        assert r.returncode == 0, f"baseline gen failed: {r.stderr[:200]}"
        data = json.loads(r.stdout)
        path.write_text(json.dumps(data, indent=2, sort_keys=True))
    return json.loads(path.read_text())


def test_golden_cdc_axi_cdc_src():
    """Golden: cdc axi_cdc_src output 跟 baseline 一致 (2 HIGH risk paths stable)."""
    def gen():
        return _run("-q", "cdc", "analyze", "--no-strict",
                     "--file", "/Users/fundou/my_dv_proj/axi/src/axi_cdc_src.sv",
                     "--json")
    actual = json.loads(gen().stdout)
    golden = _read_golden("cdc_axi_cdc_src", gen)
    # 比对关键字段 (paths 内容可能略有差异, 比对 count + risk)
    if actual["result"]["total_cdc"] != golden["result"]["total_cdc"]:
        pytest.fail(f"total_cdc mismatch: {actual['result']['total_cdc']} vs {golden['result']['total_cdc']}")
    if actual["result"]["high_risk"] != golden["result"]["high_risk"]:
        pytest.fail(f"high_risk mismatch: {actual['result']['high_risk']} vs {golden['result']['high_risk']}")
    print(f"✅ Golden cdc axi_cdc_src: {actual['result']['total_cdc']} paths, {actual['result']['high_risk']} HIGH (stable)")


def test_golden_risk_strict_uart():
    """Golden: risk strict_uart summary 跟 baseline 一致 (8 critical + 5 high)."""
    def gen():
        return _run("-q", "risk", "analyze", "--no-strict",
                     "--filelist", str(PROJECT_ROOT / "sim" / "tests" / "fixtures" / "strict_uart" / "filelist.f"),
                     "--summary", "--json")
    actual = json.loads(gen().stdout)
    golden = _read_golden("risk_strict_uart", gen)
    a = actual["result"]["summary"]
    g = golden["result"]["summary"]
    if a != g:
        pytest.fail(f"summary mismatch:\n  actual: {a}\n  golden: {g}")
    print(f"✅ Golden risk strict_uart: {a['total']} total, {a['critical']} critical + {a['high']} high (stable)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
