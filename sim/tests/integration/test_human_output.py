"""
[Stage 6] --human friendly arrow-based output tests

验证 6 个命令 (trace fanin/fanout/impact + dataflow + controlflow + cdc)
加 --human flag 后输出:
1. 包含箭头 (→ ⇢ ⤷) 表示前后关系
2. 包含关键信号名 (from, to, signal)
3. 不破坏现有 text/json 行为
"""
import json
import subprocess
from pathlib import Path

import pytest

# [Stage 6] parents[3] = repo root (sim/tests/integration/test_*.py → sim → repo)
REPO_ROOT = Path(__file__).resolve().parents[3]
TEST_FILE = str(REPO_ROOT / "sim" / "test_simple.sv")
TEST_CDC_FILE = str(REPO_ROOT / "sim" / "test_cdc.sv")


def _run_cli(*args, timeout=60):
    result = subprocess.run(
        ["python3", "run_cli.py", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


class TestHumanOutput:
    """[Stage 6] --human flag arrow-based output"""

    def test_trace_fanin_human_has_arrow(self):
        rc, out, _ = _run_cli("trace", "fanin", "-f", TEST_FILE, "top.dout", "--human")
        assert rc == 0
        assert "→" in out, f"Expected arrow in output: {out!r}"
        assert "top.dout" in out
        assert "top.data" in out or "top.din" in out  # 至少一个 driver

    def test_trace_fanout_human_has_arrow(self):
        rc, out, _ = _run_cli("trace", "fanout", "-f", TEST_FILE, "top.din", "--human")
        assert rc == 0
        assert "→" in out
        assert "top.din" in out
        assert "top.data" in out or "top.dout" in out

    def test_trace_impact_human_has_arrow(self):
        rc, out, _ = _run_cli("trace", "impact", "-f", TEST_FILE, "top.din", "--human")
        assert rc == 0
        assert "→" in out
        assert "top.din" in out
        # 应标 risk (HIGH/MEDIUM/LOW)
        assert any(r in out for r in ("HIGH", "MEDIUM", "LOW"))

    def test_dataflow_human_has_arrow(self):
        rc, out, _ = _run_cli(
            "dataflow", "analyze",
            "-f", TEST_FILE, "top.din", "top.dout",
            "--human",
        )
        assert rc == 0
        assert "→" in out
        assert "top.din" in out
        assert "top.dout" in out
        # 应有路径信息
        assert "Path" in out or "path" in out.lower()

    def test_controlflow_human_has_arrow(self):
        rc, out, _ = _run_cli(
            "controlflow", "analyze",
            "-f", TEST_FILE, "top.dout",
            "--human",
        )
        assert rc == 0
        # 应有箭头 (→) 或 tree 字符 (+--, |--)
        assert any(s in out for s in ("→", "+--", "|--")), f"No arrow/tree in: {out!r}"
        assert "top.dout" in out
        # 应有 when 条件
        assert "when" in out

    def test_cdc_human_has_arrow(self):
        rc, out, _ = _run_cli("cdc", "analyze", "-f", TEST_CDC_FILE, "--human")
        assert rc == 0
        assert "→" in out
        # 应有 NO SYNC / SYNC 标
        assert "NO SYNC" in out or "SYNC" in out
        # 应有风险
        assert "HIGH" in out or "LOW" in out

    def test_human_preserves_json_mode(self):
        """--human 和 --json 不能同时用 (应报错或忽略 --human)"""
        # 实际行为: typer 通常 mutual exclusive, 这里只检查 --json 仍工作
        rc, out, _ = _run_cli("trace", "fanin", "-f", TEST_FILE, "top.dout", "--json")
        assert rc == 0
        d = json.loads(out)
        assert d["ok"] is True

    def test_human_preserves_text_mode(self):
        """不加 --human 时, 输出跟以前一样 (不破坏 backward compat)"""
        rc, out, _ = _run_cli("trace", "fanin", "-f", TEST_FILE, "top.dout")
        assert rc == 0
        # 旧格式: "Fanin of 'top.dout':"
        assert "Fanin of 'top.dout'" in out
        # 旧格式没有 "→" 箭头 (或者至少有 drivers 列表)
        assert "[1]" in out or "[2]" in out  # 旧的 [distance] format

    def test_human_with_evidence_works(self):
        """--human + --evidence 同时给, 应都生效"""
        rc, out, _ = _run_cli(
            "cdc", "analyze", "-f", TEST_CDC_FILE,
            "--human", "--evidence",
        )
        assert rc == 0
        assert "→" in out
        assert "NO SYNC" in out
        # evidence 提供的 source_location 信息
        assert "test_cdc.sv" in out  # 至少 1 个 file 引用

    def test_human_output_is_multiline(self):
        """--human 输出应该多行, 适合人看"""
        rc, out, _ = _run_cli("dataflow", "analyze", "-f", TEST_FILE, "top.din", "top.dout", "--human")
        assert rc == 0
        assert out.count("\n") >= 3, f"Expected multiline output: {out!r}"
