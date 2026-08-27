"""
v11-only: CLI smoke test (D5 实施后)

[Stage 6] 旧版本来测 v10/v11 双版本都能跑. D5 锁定 v11 only 后, 本测试简化为:
1. 验证 pyslang v11 已安装
2. 验证 7 个主 CLI 命令 (trace/verify/risk/dataflow/controlflow/cdc) 在 v11 上 work

CLI 测试保留 (跟 v10/v11 兼容无关, 是 sv_query 自身功能的验证).
"""
import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "src"))

import pytest  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
TEST_FILE = str(REPO_ROOT / "sim" / "test_simple.sv")
TEST_CDC_FILE = str(REPO_ROOT / "sim" / "test_cdc.sv")


def _run_cli(*args, timeout=60):
    """Run CLI and return (rc, stdout, stderr)"""
    result = subprocess.run(
        ["python3", "run_cli.py", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


def _detect_pyslang_version() -> str:
    """D5 后: 直接测 pyslang 版本号 (绕过 trace/__init__.py 的 alias bridge).

    注意: 不能用 'from pyslang import SyntaxKind' 来探测, 因为我们的 alias bridge
    会把 SyntaxKind 注入回顶层 — 那会让 v11 看起来像 v10.

    方法: 用 pyslang 顶层 uppercase class 数 (v11 ~34, v10 ~250+) — 这不受 alias
    bridge 影响, 因为 alias bridge 只在 trace import 时生效.
    """
    import pyslang
    top = [a for a in dir(pyslang) if not a.startswith("_") and a[0].isupper()]
    if len(top) < 50:
        return "v11+"  # v11 顶层少 (大部分移到子模块)
    return "v10"  # v10 顶层多

class TestV11Installation:
    """[D5] v11 only — 验证环境装的是 v11+"""

    def test_pyslang_v11_installed(self):
        v = _detect_pyslang_version()
        assert v == "v11+", f"D5 requires pyslang v11+, but got: {v}"


class TestV11CLISmoke:
    """主命令在 v11 上 smoke test (跟原 test_pyslang_version_compat 一致)"""

    def test_trace_evidence_text(self):
        rc, out, _ = _run_cli("trace", "evidence", "--file", TEST_FILE, "top.data")
        assert rc == 0
        assert "data = din" in out or "Source:" in out

    def test_trace_evidence_json(self):
        rc, out, _ = _run_cli("trace", "evidence", "--file", TEST_FILE, "top.data", "--json")
        assert rc == 0
        d = json.loads(out)
        assert d["ok"] is True
        assert d["evidence"]["source_text"] == "data = din;"

    def test_verify_gap_evidence(self):
        rc, out, _ = _run_cli("verify", "gap", "-f", TEST_FILE, "--evidence", "--json")
        assert rc == 0
        d = json.loads(out)
        for sig in d["top_signals"]:
            if "evidence" in sig and sig["evidence"]:
                assert "credibility_score" in sig["evidence"]
                return  # 至少找到一个
        pytest.fail("Expected at least one signal with evidence")

    def test_risk_analyze_evidence(self):
        rc, out, _ = _run_cli("risk", "analyze", "-f", TEST_FILE, "--evidence", "--json")
        assert rc == 0
        d = json.loads(out)
        with_ev = [s for s in d["result"]["data_signals"] if s.get("evidence")]
        assert len(with_ev) >= 1

    def test_dataflow_evidence(self):
        rc, out, _ = _run_cli("dataflow", "analyze", "top.din", "top.dout", "-f", TEST_FILE, "--evidence", "--json")
        assert rc == 0
        d = json.loads(out)
        segs = d["result"]["paths"][0]["segments"]
        for seg in segs:
            assert "evidence" in seg

    def test_controlflow_evidence(self):
        rc, out, _ = _run_cli("controlflow", "analyze", "top.dout", "-f", TEST_FILE, "--evidence", "--json")
        assert rc == 0
        d = json.loads(out)
        cds = d["result"]["conditioned_drivers"]
        with_ev = [c for cd in cds for c in cd["conditions"] if c.get("evidence")]
        assert len(with_ev) >= 1

    def test_cdc_analyze_evidence(self):
        rc, out, _ = _run_cli("cdc", "analyze", "-f", TEST_CDC_FILE, "--evidence", "--json")
        assert rc == 0
        d = json.loads(out)
        paths = d["result"]["paths"]
        assert len(paths) >= 1
        for p in paths:
            assert p.get("source_evidence") is not None
            assert p.get("target_evidence") is not None
