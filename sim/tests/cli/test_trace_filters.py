"""
test_trace_filters.py - Tests for trace filters (--type/--module/--width-min/max/--exclude)
========================================================================================
[ADD 2026-07-03 B2] trace fanin/fanout 加 5 filters (fnmatch, NOT regex).

**正反面测试** (项目纪律):
- 正面 (positive): 有效 filter → 正确子集
  - P1: --type REG,WIRE 只返 REG/WIRE
  - P2: --module "sync_*" glob 匹配
  - P3: --width-min N 只返位宽 >= N
  - P4: --width-max N 只返位宽 <= N
  - P5: --exclude glob 排除
  - P6: 5 filter 组合
  - P7: filter + batch 组合
  - P8: 4 子命令 (fanin/fanout) 都支持
- 反面 (negative): 无效 filter → 友好错误 / 空结果
  - N1: --type 不存在的 enum → 静默空 list
  - N2: --module glob 不匹配 → 静默空 list
  - N3: --width-min > --width-max → 空 list (合法)
  - N4: --exclude 排除所有 → 空 list

**Golden**: 严格_uart fixture (3 SV, 自洽).
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
STRICT_UART_FILELIST = str(PROJECT_ROOT / "sim" / "tests" / "fixtures" / "strict_uart" / "filelist.f")
GOLDEN_DIR = PROJECT_ROOT / "sim" / "tests" / "golden" / "trace_filters"
GOLDEN_DIR.mkdir(parents=True, exist_ok=True)


def _run(*args, timeout=60) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["sv_query", "trace", *args],
        capture_output=True, text=True, timeout=timeout,
        cwd=str(PROJECT_ROOT),
    )


# ============================================================================
# 正面测试 (Positive)
# ============================================================================

def test_p1_type_filter():
    """P1: --type REG,PORT_IN 只返 REG 或 PORT_IN."""
    r = _run(
        "fanin", "uart_top.rx_data_o",
        "--filelist", STRICT_UART_FILELIST,
        "--type", "REG,PORT_IN",
        "--json",
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    drivers = data["result"]["signals"][0]["drivers"]
    kinds = {d["kind"] for d in drivers}
    assert kinds <= {"REG", "PORT_IN"}, f"unexpected kinds: {kinds}"
    print(f"✅ P1 --type REG,PORT_IN: {len(drivers)} drivers, kinds={kinds}")


def test_p2_module_glob():
    """P2: --module 'sync_*' 只返 module 名匹配 glob."""
    r = _run(
        "fanin", "uart_top.rx_data_o",
        "--filelist", STRICT_UART_FILELIST,
        "--module", "sync_*",
        "--json",
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    drivers = data["result"]["signals"][0]["drivers"]
    for d in drivers:
        assert d["module"].startswith("sync_"), f"module={d['module']}"
    print(f"✅ P2 --module 'sync_*': {len(drivers)} drivers, all sync_*")


def test_p3_width_min():
    """P3: --width-min N 只返位宽 >= N."""
    r = _run(
        "fanin", "uart_top.rx_data_o",
        "--filelist", STRICT_UART_FILELIST,
        "--width-min", "8",
        "--json",
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    drivers = data["result"]["signals"][0]["drivers"]
    for d in drivers:
        assert d["width"] >= 8, f"width={d['width']} id={d['id']}"
    print(f"✅ P3 --width-min 8: {len(drivers)} drivers, all width>=8")


def test_p4_width_max():
    """P4: --width-max N 只返位宽 <= N."""
    r = _run(
        "fanin", "uart_top.rx_data_o",
        "--filelist", STRICT_UART_FILELIST,
        "--width-max", "1",
        "--json",
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    drivers = data["result"]["signals"][0]["drivers"]
    for d in drivers:
        assert d["width"] <= 1, f"width={d['width']} id={d['id']}"
    print(f"✅ P4 --width-max 1: {len(drivers)} drivers, all width<=1")


def test_p5_exclude_glob():
    """P5: --exclude glob 排除信号 id."""
    r = _run(
        "fanin", "uart_top.rx_data_o",
        "--filelist", STRICT_UART_FILELIST,
        "--exclude", "*_o",
        "--json",
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    drivers = data["result"]["signals"][0]["drivers"]
    for d in drivers:
        assert not d["id"].endswith("_o"), f"id={d['id']} should be excluded"
    print(f"✅ P5 --exclude '*_o': {len(drivers)} drivers, no _o suffix")


def test_p6_combined_filters():
    """P6: 5 filter 组合."""
    r = _run(
        "fanin", "uart_top.rx_data_o",
        "--filelist", STRICT_UART_FILELIST,
        "--type", "REG",
        "--module", "sync_*",
        "--width-min", "2",
        "--width-max", "8",
        "--exclude", "*_int*",
        "--json",
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    drivers = data["result"]["signals"][0]["drivers"]
    for d in drivers:
        assert d["kind"] == "REG"
        assert d["module"].startswith("sync_")
        assert 2 <= d["width"] <= 8
        assert "_int" not in d["id"]
    print(f"✅ P6 5 filters combined: {len(drivers)} drivers all match")


def test_p7_filter_with_batch():
    """P7: filter + batch 组合."""
    r = _run(
        "fanin",
        "--batch", "uart_top.rx_data_o,sync_fifo.count_q",
        "--filelist", STRICT_UART_FILELIST,
        "--type", "REG",
        "--json",
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    signals = data["result"]["signals"]
    assert len(signals) == 2
    for sig_entry in signals:
        drivers = sig_entry["drivers"]
        for d in drivers:
            assert d["kind"] == "REG", f"{sig_entry['signal']}: {d}"
    print(f"✅ P7 batch + --type REG: 2 signals all REG-only")


def test_p8_fanout_also_supports_filters():
    """P8: fanout 也支持 5 filters."""
    r = _run(
        "fanout", "sync_fifo.count_q",
        "--filelist", STRICT_UART_FILELIST,
        "--type", "REG",
        "--include-clock",
        "--json",
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    loads = data["result"]["signals"][0]["loads"]
    for d in loads:
        assert d["kind"] == "REG", f"{d}"
    print(f"✅ P8 fanout + --type REG: {len(loads)} loads all REG")


def test_p9_module_field_in_json():
    """P9: 验证 module 字段暴露在 JSON (filter 依赖)."""
    r = _run(
        "fanin", "uart_top.rx_data_o",
        "--filelist", STRICT_UART_FILELIST,
        "--json",
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    drivers = data["result"]["signals"][0]["drivers"]
    assert len(drivers) > 0
    for d in drivers:
        assert "module" in d, f"missing module in {d}"
        assert "width" in d, f"missing width in {d}"
        assert "width_msb" in d
        assert "width_lsb" in d
    print(f"✅ P9 module + width fields exposed: {len(drivers)} drivers")


# ============================================================================
# 反面测试 (Negative)
# ============================================================================

def test_n1_type_no_match():
    """N1: --type 不存在的 enum → 静默空 list (不报错)."""
    r = _run(
        "fanin", "uart_top.rx_data_o",
        "--filelist", STRICT_UART_FILELIST,
        "--type", "NONEXISTENT_KIND",
        "--json",
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["result"]["signals"][0]["count"] == 0
    print("✅ N1 --type non-existent: empty list, rc=0")


def test_n2_module_glob_no_match():
    """N2: --module glob 不匹配 → 空 list."""
    r = _run(
        "fanin", "uart_top.rx_data_o",
        "--filelist", STRICT_UART_FILELIST,
        "--module", "nonexistent_module_*",
        "--json",
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["result"]["signals"][0]["count"] == 0
    print("✅ N2 --module no match: empty list, rc=0")


def test_n3_width_min_greater_than_max():
    """N3: --width-min > --width-max → 空 list (合法, 不报错)."""
    r = _run(
        "fanin", "uart_top.rx_data_o",
        "--filelist", STRICT_UART_FILELIST,
        "--width-min", "16",
        "--width-max", "1",
        "--json",
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["result"]["signals"][0]["count"] == 0
    print("✅ N3 --width-min > --width-max: empty list, rc=0")


def test_n4_exclude_excludes_everything():
    """N4: --exclude 排除所有 → 空 list."""
    r = _run(
        "fanin", "uart_top.rx_data_o",
        "--filelist", STRICT_UART_FILELIST,
        "--exclude", "*",
        "--json",
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["result"]["signals"][0]["count"] == 0
    print("✅ N4 --exclude '*': empty list, rc=0")


# ============================================================================
# Golden baseline
# ============================================================================

def _normalize_json(data: dict) -> dict:
    """Normalize JSON for golden comparison (strip volatile parts)."""
    import copy, re
    data = copy.deepcopy(data)

    def clean(obj):
        if isinstance(obj, dict):
            return {k: clean(v) for k, v in obj.items() if k != "file"}
        if isinstance(obj, list):
            return [clean(x) for x in obj]
        if isinstance(obj, str):
            obj = re.sub(r"/Users/[^/]+/my_dv_proj/sv_query/", "PROJECT_ROOT/", obj)
            obj = re.sub(r"/home/[^/]+/my_dv_proj/sv_query/", "PROJECT_ROOT/", obj)
            return obj
        return obj

    return clean(data)


def _read_golden(name: str) -> dict:
    """Read golden JSON. Auto-create on first run."""
    path = GOLDEN_DIR / f"{name}.json"
    if not path.exists():
        # 首次跑: 生成 baseline (用 --type REG)
        r = _run(
            "fanin", "sync_fifo.count_q",
            "--filelist", STRICT_UART_FILELIST,
            "--type", "REG",
            "--width-min", "2",
            "--json",
        )
        assert r.returncode == 0, f"baseline gen failed: {r.stderr[:200]}"
        actual = _normalize_json(json.loads(r.stdout))
        path.write_text(json.dumps(actual, indent=2, sort_keys=True))
    return json.loads(path.read_text())


def test_golden_filter_type_and_width():
    """Golden: --type REG + --width-min 2 跟 baseline 一致."""
    r = _run(
        "fanin", "sync_fifo.count_q",
        "--filelist", STRICT_UART_FILELIST,
        "--type", "REG",
        "--width-min", "2",
        "--json",
    )
    assert r.returncode == 0
    actual = _normalize_json(json.loads(r.stdout))
    golden = _read_golden("type_REG_width_min_2")
    if actual != golden:
        import difflib
        diff = "\n".join(difflib.unified_diff(
            json.dumps(golden, indent=2, sort_keys=True).splitlines(),
            json.dumps(actual, indent=2, sort_keys=True).splitlines(),
            lineterm="",
            fromfile="golden",
            tofile="actual",
            n=3,
        ))
        pytest.fail(f"Golden mismatch:\n{diff[:2000]}")
    print("✅ Golden: --type REG + --width-min 2 matches baseline")


if __name__ == "__main__":
    tests = [
        test_p1_type_filter, test_p2_module_glob, test_p3_width_min,
        test_p4_width_max, test_p5_exclude_glob, test_p6_combined_filters,
        test_p7_filter_with_batch, test_p8_fanout_also_supports_filters,
        test_p9_module_field_in_json,
        test_n1_type_no_match, test_n2_module_glob_no_match,
        test_n3_width_min_greater_than_max, test_n4_exclude_excludes_everything,
        test_golden_filter_type_and_width,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"❌ {t.__name__}: {e}")
            sys.exit(1)
    print(f"\n🎉 All {len(tests)} filter tests passed!")
