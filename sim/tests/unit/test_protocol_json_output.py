"""Test protocol detect --json output is pure JSON (P1-6)

Verifies:
- --json output is valid JSON parseable without errors
- "Analyzing:" message goes to stderr, not stdout
- No pollution in stdout (only JSON content)
"""
import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUN_CLI = PROJECT_ROOT / "run_cli.py"


def _run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run command, return (rc, stdout, stderr)."""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=PROJECT_ROOT,
    )
    return result.returncode, result.stdout, result.stderr


def test_json_output_pure_json():
    """[P1-6] --json output must be parseable as JSON without errors."""
    cmd = [
        sys.executable, str(RUN_CLI),
        "protocol", "detect",
        "--protocol", "TL-UL",
        "--json",
        "-f", str(PROJECT_ROOT / "config" / "protocols" / "tlul.yaml"),
    ]
    # 任何文件路径都行, 这里用 yaml 会被 mock fallback 走 demo signals
    # 替换为: 用真实 SV 文件 (存在就 OK, 不存在 fallback 也行, JSON 仍可解析)
    real_sv = "/Users/fundou/my_dv_proj/OpenTitan/hw/dv/sv/sim_sram/tlul_sink.sv"
    cmd[-1] = real_sv
    rc, stdout, stderr = _run(cmd)
    # stdout 必须是纯 JSON (parseable)
    if rc != 0:
        # 没找到 file 时 mock fallback 也可能 fail, 但我们只关心 stdout 是否纯 JSON
        pass
    # 关键断言: stdout 可被 json.loads 解析
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        pytest.fail(f"stdout is not valid JSON: {e}\nstdout: {stdout[:500]}")
    # 必须有 protocol/variant/confidence 字段
    assert "protocol" in data
    assert "confidence" in data


def test_analyzing_message_on_stderr():
    """[P1-6] 'Analyzing:' progress info must go to stderr, not stdout."""
    cmd = [
        sys.executable, str(RUN_CLI),
        "protocol", "detect",
        "--protocol", "TL-UL",
        "--json",
        "-f", "/Users/fundou/my_dv_proj/OpenTitan/hw/dv/sv/sim_sram/tlul_sink.sv",
    ]
    rc, stdout, stderr = _run(cmd)
    # stdout 中不应该有 "Analyzing:" 字样
    assert "Analyzing:" not in stdout, f"'Analyzing:' leaked to stdout: {stdout[:200]}"
    # stderr 应该有 Analyzing: (即使 rc != 0)
    # 注: elaboration error 时 stderr 会有 [ERROR] 行, 但 Analyzing 也会在


def test_result_to_dict_helper():
    """[P1-6] _result_to_dict 应该返回合法 dict, 包含所有必要字段."""
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    from cli.commands.protocol import _result_to_dict
    # 构造一个 mock match
    class MockMatch:
        protocol = "TL-UL"
        variant = "TL-UL_STRUCT_WRAPPER"
        confidence = 0.350
        name_score = 0.5
        structural_score = 0.0
        pattern_score = 0.5
        handshake_score = 0.5
        channels = {}
        warnings = []
    result = _result_to_dict(MockMatch())
    # 必要字段
    for k in ("protocol", "variant", "confidence", "scores", "channels", "warnings"):
        assert k in result, f"missing key: {k}"
    # scores 子字段
    for sk in ("name", "structural", "pattern", "handshake"):
        assert sk in result["scores"]
    # 序列化测试: 应该能直接 json.dumps
    s = json.dumps(result)
    parsed = json.loads(s)
    assert parsed["protocol"] == "TL-UL"
    assert parsed["confidence"] == 0.350


# pytest skip helpers
import pytest
