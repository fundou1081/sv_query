"""
[Stage 5] evidence 集成测试 - 验证 verify / risk 命令的 --evidence flag

覆盖:
1. verify gap --evidence: JSON 含 evidence 字段, 文本含 summary
2. verify gap 默认: 无 evidence 字段, 无 summary
3. risk analyze --evidence: JSON 含 evidence 字段, 文本含 summary
4. risk analyze 默认: 无 evidence 字段
5. credibility_score 有效
"""
import json
import subprocess
import sys
import os
from pathlib import Path

# [Stage 5] sys.path 必须在所有项目 import 之前设置,避免被 stdlib 'trace' 抢占
# __file__ = sim/tests/integration/test_*.py, parents[3] = repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "src"))

import pytest  # noqa: E402

REPO_ROOT = _REPO_ROOT
TEST_FILE = str(REPO_ROOT / "sim" / "test_simple.sv")
RUN_CLI = "python3"


def _run_cli(*args):
    """运行 run_cli.py 并返回 (returncode, stdout, stderr)"""
    result = subprocess.run(
        [RUN_CLI, "run_cli.py", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.returncode, result.stdout, result.stderr


# ----------------------------------------------------------------------------
# verify gap
# ----------------------------------------------------------------------------

class TestVerifyGapEvidence:
    """verify gap --evidence flag"""

    def test_default_no_evidence_field(self):
        """默认 (无 --evidence): top_signals[].evidence 字段不存在"""
        rc, out, err = _run_cli("verify", "gap", "-f", TEST_FILE, "--json")
        assert rc == 0, f"CLI failed: {err}"
        data = json.loads(out)
        for sig in data["top_signals"]:
            assert "evidence" not in sig, (
                f"Default mode should not include evidence, got: {sig.get('evidence')}"
            )

    def test_with_flag_evidence_in_json(self):
        """--evidence: top_signals[].evidence 字段存在, 含 source_text + score"""
        rc, out, err = _run_cli("verify", "gap", "-f", TEST_FILE, "--evidence", "--json")
        assert rc == 0, f"CLI failed: {err}"
        data = json.loads(out)
        # 至少 1 个信号有 evidence
        with_ev = [s for s in data["top_signals"] if s.get("evidence")]
        assert len(with_ev) >= 1, "Expected at least 1 signal with evidence"
        for sig in with_ev:
            ev = sig["evidence"]
            assert "source_text" in ev
            assert "credibility_score" in ev
            assert 0.0 <= ev["credibility_score"] <= 1.0

    def test_with_flag_evidence_in_text(self):
        """--evidence: 文本输出含 '└─' 缩进 summary"""
        rc, out, err = _run_cli("verify", "gap", "-f", TEST_FILE, "--evidence")
        assert rc == 0, f"CLI failed: {err}"
        assert "└─" in out, f"Expected indented summary in text output, got:\n{out}"

    def test_default_no_text_summary(self):
        """默认: 文本输出不含 '└─' summary"""
        rc, out, err = _run_cli("verify", "gap", "-f", TEST_FILE)
        assert rc == 0, f"CLI failed: {err}"
        assert "└─" not in out, "Default mode should not show evidence summary"


# ----------------------------------------------------------------------------
# risk analyze
# ----------------------------------------------------------------------------

class TestRiskAnalyzeEvidence:
    """risk analyze --evidence flag"""

    def test_default_no_evidence_field(self):
        """默认: data_signals[].evidence 字段不存在"""
        rc, out, err = _run_cli("risk", "analyze", "-f", TEST_FILE, "--json")
        assert rc == 0, f"CLI failed: {err}"
        data = json.loads(out)
        for sig in data["result"]["data_signals"]:
            assert "evidence" not in sig

    def test_with_flag_evidence_in_json(self):
        """--evidence: data_signals[].evidence 字段存在, credibility_score 有效"""
        rc, out, err = _run_cli("risk", "analyze", "-f", TEST_FILE, "--evidence", "--json")
        assert rc == 0, f"CLI failed: {err}"
        data = json.loads(out)
        with_ev = [s for s in data["result"]["data_signals"] if s.get("evidence")]
        assert len(with_ev) >= 1
        for sig in with_ev:
            ev = sig["evidence"]
            assert "source_text" in ev
            assert "source_location" in ev
            assert "credibility_score" in ev
            assert 0.0 <= ev["credibility_score"] <= 1.0
            # node_id 应保留 (向后兼容)
            assert "node_id" in sig

    def test_with_flag_evidence_in_text(self):
        """--evidence: 文本输出含 '└─' summary"""
        rc, out, err = _run_cli("risk", "analyze", "-f", TEST_FILE, "--evidence")
        assert rc == 0, f"CLI failed: {err}"
        assert "└─" in out

    def test_known_signals_have_meaningful_evidence(self):
        """特定信号 (dout, data) 应有有意义的 evidence, 不是空"""
        rc, out, err = _run_cli("risk", "analyze", "-f", TEST_FILE, "--evidence", "--json")
        assert rc == 0
        data = json.loads(out)
        by_name = {s["name"]: s for s in data["result"]["data_signals"]}

        # dout: 在 always 块内, source_text 应是 if condition
        dout_ev = by_name["dout"]["evidence"]
        assert dout_ev["source_text"], "dout should have non-empty source_text"
        assert dout_ev["enclosing_always"] is not None
        assert dout_ev["enclosing_if"] is not None

        # data: 在 assign, source_text 应是 assign 整行
        data_ev = by_name["data"]["evidence"]
        assert "data" in data_ev["source_text"]
        assert data_ev["enclosing_assign"] is not None


# ----------------------------------------------------------------------------
# helper 单元测试
# ----------------------------------------------------------------------------

class TestEvidenceSummaryInputs:
    """evidence_summary_line 应同时接受 Evidence 对象和 dict"""

    def test_dict_input(self):
        """dict 输入: 走 dict 路径"""
        from cli._evidence_helpers import evidence_summary_line
        ev_dict = {
            "source_location": {"file": "x.sv", "line_start": 12, "line_end": 12, "column": 5},
            "source_text": "data = din;",
        }
        line = evidence_summary_line(ev_dict)
        assert line == "x.sv:12: data = din;"

    def test_evidence_object_input(self):
        """Evidence 对象输入: 走属性路径"""
        from trace.core.trace_evidence import TraceEvidenceResolver
        from trace.unified_tracer import UnifiedTracer
        from cli._evidence_helpers import evidence_summary_line

        with open(TEST_FILE) as f:
            source = f.read()
        tracer = UnifiedTracer(sources={TEST_FILE: source}, log_level="ERROR")
        graph = tracer.build_graph()
        adapter = tracer._get_adapter()
        resolver = TraceEvidenceResolver(graph=graph, adapter=adapter)
        ev = resolver.resolve("top.data")
        line = evidence_summary_line(ev)
        assert line is not None
        assert "test_simple.sv" in line
        assert "data = din" in line

    def test_none_input(self):
        """None 输入: 返回 None"""
        from cli._evidence_helpers import evidence_summary_line
        assert evidence_summary_line(None) is None

    def test_empty_dict(self):
        """source_location=None 的 dict: 返回 None"""
        from cli._evidence_helpers import evidence_summary_line
        assert evidence_summary_line({"source_location": None, "source_text": ""}) is None


# ----------------------------------------------------------------------------
# dataflow analyze
# ----------------------------------------------------------------------------

class TestDataflowEvidence:
    """dataflow analyze --evidence flag"""

    def test_default_no_evidence(self):
        """默认: paths[].segments[].evidence 字段不存在"""
        rc, out, err = _run_cli("dataflow", "analyze", "top.din", "top.dout", "-f", TEST_FILE, "--json")
        assert rc == 0, f"CLI failed: {err}"
        data = json.loads(out)
        for path in data["result"]["paths"]:
            for seg in path["segments"]:
                assert "evidence" not in seg

    def test_with_flag_evidence_per_segment(self):
        """--evidence: 每个 segment 加 evidence 字段 (to_signal 独立解析)"""
        rc, out, err = _run_cli("dataflow", "analyze", "top.din", "top.dout", "-f", TEST_FILE, "--evidence", "--json")
        assert rc == 0, f"CLI failed: {err}"
        data = json.loads(out)
        segments = data["result"]["paths"][0]["segments"]
        assert len(segments) >= 1
        for seg in segments:
            assert "evidence" in seg, f"Missing evidence in segment {seg.get('to_signal')}"
            ev = seg["evidence"]
            assert ev is not None
            assert "source_text" in ev
            assert 0.0 <= ev["credibility_score"] <= 1.0

    def test_with_flag_evidence_in_text(self):
        """--evidence: 文本输出含 '└─' summary"""
        rc, out, err = _run_cli("dataflow", "analyze", "top.din", "top.dout", "-f", TEST_FILE, "--evidence")
        assert rc == 0, f"CLI failed: {err}"
        assert "└─" in out


# ----------------------------------------------------------------------------
# controlflow analyze
# ----------------------------------------------------------------------------

class TestControlflowEvidence:
    """controlflow analyze --evidence flag"""

    def test_default_no_evidence(self):
        """默认: conditions[].evidence 字段不存在"""
        rc, out, err = _run_cli("controlflow", "analyze", "top.dout", "-f", TEST_FILE, "--json")
        assert rc == 0, f"CLI failed: {err}"
        data = json.loads(out)
        for cd in data["result"]["conditioned_drivers"]:
            for cond in cd["conditions"]:
                assert "evidence" not in cond

    def test_with_flag_evidence_per_condition(self):
        """--evidence: 每个 condition 加 evidence 字段 (to_node 独立解析)"""
        rc, out, err = _run_cli("controlflow", "analyze", "top.dout", "-f", TEST_FILE, "--evidence", "--json")
        assert rc == 0, f"CLI failed: {err}"
        data = json.loads(out)
        with_ev = []
        for cd in data["result"]["conditioned_drivers"]:
            for cond in cd["conditions"]:
                if cond.get("evidence"):
                    with_ev.append(cond)
        assert len(with_ev) >= 1
        for cond in with_ev:
            ev = cond["evidence"]
            assert "source_text" in ev
            assert "credibility_score" in ev

    def test_with_flag_evidence_in_text(self):
        """--evidence: 文本输出含 '└─' summary"""
        rc, out, err = _run_cli("controlflow", "analyze", "top.dout", "-f", TEST_FILE, "--evidence")
        assert rc == 0, f"CLI failed: {err}"
        assert "└─" in out


# ----------------------------------------------------------------------------
# cdc analyze
# ----------------------------------------------------------------------------

# [Stage 5] CDC 需要跨时钟域场景, sim/test_cdc.sv 是专用的 minimal CDC fixture
CDC_TEST_FILE = str(REPO_ROOT / "sim" / "test_cdc.sv")


class TestCdcEvidence:
    """cdc analyze --evidence flag"""

    def test_default_no_evidence(self):
        """默认: paths[].source_evidence / target_evidence 字段不存在"""
        rc, out, err = _run_cli("cdc", "analyze", "-f", CDC_TEST_FILE, "--json")
        assert rc == 0, f"CLI failed: {err}"
        data = json.loads(out)
        for p in data["result"]["paths"]:
            assert "source_evidence" not in p
            assert "target_evidence" not in p

    def test_with_flag_evidence_in_json(self):
        """--evidence: 每条 CDC 路径的 source/target 都有 evidence"""
        rc, out, err = _run_cli("cdc", "analyze", "-f", CDC_TEST_FILE, "--evidence", "--json")
        assert rc == 0, f"CLI failed: {err}"
        data = json.loads(out)
        paths = data["result"]["paths"]
        assert len(paths) >= 1, "test_cdc.sv should have at least 1 CDC path"
        for p in paths:
            assert "source_evidence" in p
            assert "target_evidence" in p
            assert p["source_evidence"] is not None
            assert p["target_evidence"] is not None
            assert "source_text" in p["source_evidence"]
            assert "credibility_score" in p["source_evidence"]

    def test_with_flag_evidence_in_text(self):
        """--evidence: 文本输出含 source/target summary"""
        rc, out, err = _run_cli("cdc", "analyze", "-f", CDC_TEST_FILE, "--evidence")
        assert rc == 0, f"CLI failed: {err}"
        assert "source:" in out
        assert "target:" in out
        assert "test_cdc.sv" in out

    def test_high_risk_path_evidence_works(self):
        """高风险路径的 source/target evidence 都应有效 (包含 enclosing 上下文)"""
        rc, out, err = _run_cli("cdc", "analyze", "-f", CDC_TEST_FILE, "--evidence", "--json")
        assert rc == 0, f"CLI failed: {err}"
        data = json.loads(out)
        high_risk = [p for p in data["result"]["paths"] if p["risk"] == "HIGH"]
        assert len(high_risk) >= 1
        for p in high_risk:
            # 同步器缺失 → 高风险, evidence 应指向 always_ff 内的 if 块
            assert p["source_evidence"]["source_text"]
            assert p["target_evidence"]["source_text"]

    def test_json_no_tuple_key_error(self):
        """[Stage 5] domain_pairs 以前用 tuple key 报错, 现在应能正常 JSON 序列化"""
        rc, out, err = _run_cli("cdc", "analyze", "-f", CDC_TEST_FILE, "--json")
        assert rc == 0, f"cdc --json should not crash: {err}"
        data = json.loads(out)
        assert data["ok"] is True
