"""
[Stage 6] pyslang 10/11 双版本烟雾测试

不依赖任何 v10/v11 specific 行为, 只验证:
1. 5 个主 CLI 命令 (trace/cdc/verify/risk/dataflow/controlflow)
2. 都能 import + 跑出预期结果
3. 在当前安装的 pyslang 版本上 work

这个测试在 v10 和 v11 上都应该过。
"""
import json
import subprocess
import sys
from pathlib import Path

# [Stage 6] 顶层 import 之前 sys.path, 避免 stdlib 'trace' 抢占
_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "src"))

import pytest  # noqa: E402

# [Stage 6] parents[3] = repo root (sim/tests/integration/test_*.py → sim → repo)
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
    """Detect installed pyslang version"""
    try:
        from trace.core._pyslang_compat import _detect_version
        return _detect_version()
    except ImportError:
        return "unknown"


class TestPyslangDualVersion:
    """[Stage 6] 主命令在当前 pyslang 版本上 smoke test"""

    def test_version_detected(self):
        v = _detect_pyslang_version()
        # v10 / v11+ / unknown, unknown 通常说明 pyslang 没装
        assert v in ("v10", "v11+"), f"Unexpected pyslang version: {v}"

    def test_trace_evidence_text(self):
        """trace evidence text 输出"""
        rc, out, _ = _run_cli("trace", "evidence", "--file", TEST_FILE, "top.data")
        assert rc == 0
        assert "data = din" in out or "Source:" in out

    def test_trace_evidence_json(self):
        """trace evidence JSON 输出"""
        rc, out, _ = _run_cli("trace", "evidence", "--file", TEST_FILE, "top.data", "--json")
        assert rc == 0
        d = json.loads(out)
        assert d["ok"] is True
        assert d["evidence"]["source_text"] == "data = din;"

    def test_verify_gap_evidence(self):
        """verify gap --evidence JSON 包含 evidence 字段"""
        rc, out, _ = _run_cli("verify", "gap", "-f", TEST_FILE, "--evidence", "--json")
        assert rc == 0
        d = json.loads(out)
        for sig in d["top_signals"]:
            if "evidence" in sig and sig["evidence"]:
                assert "credibility_score" in sig["evidence"]
                return  # 至少找到一个
        pytest.fail("Expected at least one signal with evidence")

    def test_risk_analyze_evidence(self):
        """risk analyze --evidence JSON"""
        rc, out, _ = _run_cli("risk", "analyze", "-f", TEST_FILE, "--evidence", "--json")
        assert rc == 0
        d = json.loads(out)
        with_ev = [s for s in d["result"]["data_signals"] if s.get("evidence")]
        assert len(with_ev) >= 1

    def test_dataflow_evidence(self):
        """dataflow analyze --evidence"""
        rc, out, _ = _run_cli("dataflow", "analyze", "top.din", "top.dout", "-f", TEST_FILE, "--evidence", "--json")
        assert rc == 0
        d = json.loads(out)
        segs = d["result"]["paths"][0]["segments"]
        for seg in segs:
            assert "evidence" in seg

    def test_controlflow_evidence(self):
        """controlflow analyze --evidence"""
        rc, out, _ = _run_cli("controlflow", "analyze", "top.dout", "-f", TEST_FILE, "--evidence", "--json")
        assert rc == 0
        d = json.loads(out)
        cds = d["result"]["conditioned_drivers"]
        with_ev = [c for cd in cds for c in cd["conditions"] if c.get("evidence")]
        assert len(with_ev) >= 1

    def test_cdc_analyze_evidence(self):
        """cdc analyze --evidence (需 CDC 路径)"""
        rc, out, _ = _run_cli("cdc", "analyze", "-f", TEST_CDC_FILE, "--evidence", "--json")
        assert rc == 0
        d = json.loads(out)
        paths = d["result"]["paths"]
        assert len(paths) >= 1
        for p in paths:
            assert p.get("source_evidence") is not None
            assert p.get("target_evidence") is not None
