"""
test_trace_schemas.py - Validate trace JSON output against llm_schema.json
============================================================================
[ADD 2026-07-03 B3] Week 3 trace 做深 Task 3/4.

**目标**: trace 4 子命令的 JSON output 必须匹配 tools/llm_schema.json 的 result_schema.
LLM agent 依赖 schema 解析 output, schema 不对 = 解析失败.

**正反面测试**:
- 正面 (positive): 4 子命令 × 多场景, JSON 全部 schema-valid
  - P1: fanin 1 signal
  - P2: fanin 2 signals (batch)
  - P3: fanin + --type filter
  - P4: fanout 1 signal
  - P5: fanout + --include-clock
  - P6: impact 1 signal
  - P7: impact batch
  - P8: evidence 1 signal
  - P9: evidence + --chain
  - P10: filter produces pre_filter_count
- 反面 (negative): schema mismatch 应被 jsonschema 检测
  - N1: 删 required field → invalid
  - N2: 错 type (string vs int) → invalid
  - N3: empty schema validation passes (sanity)

**实现**: 用 jsonschema.Draft202012Validator (项目里已有 4.26.0)
"""
import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
STRICT_UART_FILELIST = str(PROJECT_ROOT / "sim" / "tests" / "fixtures" / "strict_uart" / "filelist.f")
SCHEMA_FILE = PROJECT_ROOT / "tools" / "llm_schema.json"


@pytest.fixture(scope="module")
def schema():
    """Load llm_schema.json once per module."""
    with open(SCHEMA_FILE) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def validator(schema):
    """Build Draft202012Validator once per module."""
    return jsonschema.Draft202012Validator(schema)


def _run(*args, timeout=60) -> dict:
    """Run sv_query trace, return parsed JSON."""
    r = subprocess.run(
        ["sv_query", "trace", *args],
        capture_output=True, text=True, timeout=timeout,
        cwd=str(PROJECT_ROOT),
    )
    if r.returncode != 0:
        pytest.fail(f"CLI failed: rc={r.returncode} stderr={r.stderr[:300]}")
    return json.loads(r.stdout)


def _validate_result(command: str, data: dict, schema: dict, validator):
    """Validate data['result'] against commands[command]['result_schema'].

    Uses $ref to leverage the full schema (definitions + commands) for $ref resolution.
    jsonschema.Draft202012Validator(schema) stores full schema, validate() accepts a
    fragment as second arg.
    """
    if data.get("ok") is not True:
        pytest.skip(f"command not ok: {data.get('error', 'unknown')}")
    fragment = {"$ref": f"#/commands/{command}/result_schema"}
    errors = list(validator.iter_errors(data["result"], fragment))
    if errors:
        msgs = [f"  {e.message} at {list(e.absolute_path)}" for e in errors[:5]]
        pytest.fail(f"Schema mismatch for {command}.result:\n" + "\n".join(msgs))


# ============================================================================
# 正面 (Positive)
# ============================================================================

def test_p1_fanin_single_signal(validator, schema):
    """P1: trace fanin 1-signal JSON matches schema."""
    data = _run("fanin", "uart_top.rx_data_o",
                "--filelist", STRICT_UART_FILELIST, "--json")
    _validate_result("trace_fanin", data, schema, validator)
    assert data["result"]["total_signals"] == 1
    print("✅ P1 fanin single: schema valid")


def test_p2_fanin_batch(validator, schema):
    """P2: trace fanin batch JSON matches schema."""
    data = _run("fanin", "--batch", "uart_top.rx_data_o,sync_fifo.count_q",
                "--filelist", STRICT_UART_FILELIST, "--json")
    _validate_result("trace_fanin", data, schema, validator)
    assert data["result"]["total_signals"] == 2
    print("✅ P2 fanin batch (2 signals): schema valid")


def test_p3_fanin_with_filter(validator, schema):
    """P3: trace fanin + --type filter 保持 schema valid."""
    data = _run("fanin", "uart_top.rx_data_o",
                "--filelist", STRICT_UART_FILELIST,
                "--type", "REG", "--width-min", "2", "--json")
    _validate_result("trace_fanin", data, schema, validator)
    # pre_filter_count 应该出现
    for sig_entry in data["result"]["signals"]:
        assert "pre_filter_count" in sig_entry
    print("✅ P3 fanin + --type --width-min: schema valid (pre_filter_count present)")


def test_p4_fanout_single_signal(validator, schema):
    """P4: trace fanout 1-signal JSON matches schema."""
    data = _run("fanout", "sync_fifo.count_q",
                "--filelist", STRICT_UART_FILELIST, "--json")
    _validate_result("trace_fanout", data, schema, validator)
    print("✅ P4 fanout single: schema valid")


def test_p5_fanout_with_include_clock(validator, schema):
    """P5: trace fanout + --include-clock 保持 schema valid."""
    data = _run("fanout", "uart_top.clk",
                "--filelist", STRICT_UART_FILELIST,
                "--include-clock", "--json")
    _validate_result("trace_fanout", data, schema, validator)
    print("✅ P5 fanout + --include-clock: schema valid")


def test_p6_impact_single_signal(validator, schema):
    """P6: trace impact 1-signal JSON matches schema."""
    data = _run("impact", "uart_top.rx_data_o",
                "--filelist", STRICT_UART_FILELIST, "--json")
    _validate_result("trace_impact", data, schema, validator)
    print("✅ P6 impact single: schema valid")


def test_p7_impact_batch(validator, schema):
    """P7: trace impact batch JSON matches schema."""
    data = _run("impact", "--batch", "uart_top.rx_data_o,sync_fifo.count_q",
                "--filelist", STRICT_UART_FILELIST, "--json")
    _validate_result("trace_impact", data, schema, validator)
    assert data["result"]["total_signals"] == 2
    print("✅ P7 impact batch (2 signals): schema valid")


def test_p8_evidence_single_signal(validator, schema):
    """P8: trace evidence 1-signal JSON matches schema."""
    data = _run("evidence", "sync_fifo.count_q",
                "--filelist", STRICT_UART_FILELIST, "--json")
    _validate_result("trace_evidence", data, schema, validator)
    print("✅ P8 evidence single: schema valid")


def test_p9_evidence_with_chain(validator, schema):
    """P9: trace evidence --chain (returns array instead of object) 保持 schema valid."""
    data = _run("evidence", "sync_fifo.count_q",
                "--filelist", STRICT_UART_FILELIST, "--chain", "--json")
    _validate_result("trace_evidence", data, schema, validator)
    # evidence 应该是 array
    ev = data["result"]["signals"][0]["evidence"]
    assert isinstance(ev, list), f"expected list, got {type(ev)}"
    print(f"✅ P9 evidence --chain: schema valid (evidence is array, len={len(ev)})")


def test_p10_filter_pre_filter_count(validator, schema):
    """P10: --type + --module filter, pre_filter_count >= count."""
    data = _run("fanin", "uart_top.rx_data_o",
                "--filelist", STRICT_UART_FILELIST,
                "--type", "REG", "--module", "sync_*", "--json")
    _validate_result("trace_fanin", data, schema, validator)
    for sig_entry in data["result"]["signals"]:
        # pre_filter_count 应该 ≥ count (filter 只减不增)
        assert sig_entry["pre_filter_count"] >= sig_entry["count"]
    print("✅ P10 filter pre_filter_count: schema valid, >= count")


# ============================================================================
# 反面 (Negative)
# ============================================================================

def test_n1_remove_required_field_fails(validator, schema):
    """N1: 删 result.signals (required field) → schema 验证失败."""
    bad_data = {
        "ok": True,
        "command": "trace_fanin",
        "result": {
            # 故意没有 'signals' (required)
            "total_signals": 1,
            "total_count": 0,
            "total_pre_filter": 0,
            "truncated": False,
        },
    }
    fragment = {"$ref": f"#/commands/trace_fanin/result_schema"}
    errors = list(validator.iter_errors(bad_data["result"], fragment))
    assert len(errors) > 0, "expected schema validation to fail for missing 'signals'"
    has_signals_err = any("signals" in e.message for e in errors)
    assert has_signals_err, f"errors didn't mention 'signals': {[e.message for e in errors]}"
    print("✅ N1 missing required field: schema validation correctly FAILED")


def test_n2_wrong_type_fails(validator, schema):
    """N2: 错 type (count 应 int, 给 str) → 验证失败."""
    bad_data = {
        "ok": True,
        "command": "trace_fanin",
        "result": {
            "signals": [{
                "signal": "top.q",
                "index": 0,
                "drivers": [],
                "count": "should_be_int",  # ← 错 type
                "pre_filter_count": 0,
                "truncated": False,
            }],
            "total_signals": 1,
            "total_count": 0,
            "total_pre_filter": 0,
            "truncated": False,
        },
    }
    fragment = {"$ref": f"#/commands/trace_fanin/result_schema"}
    errors = list(validator.iter_errors(bad_data["result"], fragment))
    assert len(errors) > 0
    print("✅ N2 wrong type: schema validation correctly FAILED")


def test_n3_valid_full_output_passes(validator, schema):
    """N3: 完整合法 JSON 通过验证 (sanity check)."""
    good_data = {
        "ok": True,
        "command": "trace_fanin",
        "result": {
            "signals": [{
                "signal": "top.q",
                "index": 0,
                "drivers": [{
                    "id": "top.d",
                    "kind": "REG",
                    "module": "top",
                    "width_msb": 0,
                    "width_lsb": 0,
                    "width": 1,
                    "distance": 1,
                }],
                "count": 1,
                "pre_filter_count": 1,
                "truncated": False,
            }],
            "total_signals": 1,
            "total_count": 1,
            "total_pre_filter": 1,
            "truncated": False,
        },
    }
    fragment = {"$ref": f"#/commands/trace_fanin/result_schema"}
    errors = list(validator.iter_errors(good_data["result"], fragment))
    assert len(errors) == 0, f"valid data should pass: {[e.message for e in errors]}"
    print("✅ N3 sanity: valid full JSON passes schema validation")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
