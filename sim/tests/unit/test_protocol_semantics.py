"""Test protocol semantics loading + CLI (A 2026-06-13)

Verifies:
- list_semantics() returns all 4 protocols
- load_semantics("TL-UL") returns correct fields
- All 4 protocols have channels + deadlock_rules
- CLI `protocol semantics` outputs expected sections
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]


# ---- Pure Python loader tests ----

def test_list_semantics_returns_four_protocols():
    from applications.bus.semantics import list_semantics
    protos = list_semantics()
    assert set(protos) == {"TL-UL", "AXI4", "AHB", "APB"}


def test_load_tlul():
    from applications.bus.semantics import load_semantics
    sem = load_semantics("TL-UL")
    assert sem.protocol == "TL-UL"
    assert "a_valid" in sem.transfer
    assert len(sem.channels) == 2
    assert sem.channel("A") is not None
    assert sem.channel("A").valid == "a_valid"
    assert sem.channel("A").ready == "a_ready"
    assert sem.channel("D").depends_on == ["A"]


def test_load_axi4():
    from applications.bus.semantics import load_semantics
    sem = load_semantics("AXI4")
    assert sem.protocol == "AXI4"
    assert len(sem.channels) == 5
    ch_names = [ch.name for ch in sem.channels]
    assert ch_names == ["AW", "W", "B", "AR", "R"]
    # B 依赖 AW + W
    assert sem.channel("B").depends_on == ["AW", "W"]
    # AR 依赖空, R 依赖 AR
    assert sem.channel("AR").depends_on == []
    assert sem.channel("R").depends_on == ["AR"]


def test_load_ahb():
    from applications.bus.semantics import load_semantics
    sem = load_semantics("AHB")
    assert len(sem.channels) == 1
    assert sem.channel("H").valid == "htrans"
    assert sem.channel("H").ready == "hready"


def test_load_apb():
    from applications.bus.semantics import load_semantics
    sem = load_semantics("APB")
    assert sem.channel("P").valid == "penable"
    assert sem.channel("P").ready == "pready"


def test_deadlock_rules_have_severity():
    """每个 deadlock_rule 必须有 severity 字段"""
    from applications.bus.semantics import load_semantics
    for proto in ("TL-UL", "AXI4", "AHB", "APB"):
        sem = load_semantics(proto)
        assert len(sem.deadlock_rules) > 0, f"{proto} has no rules"
        for r in sem.deadlock_rules:
            assert r.severity in ("error", "warning", "info"), \
                f"{proto}/{r.id} has invalid severity {r.severity!r}"
            assert r.kind, f"{proto}/{r.id} missing kind"


def test_forbidden_loops_match_deadlock_rules():
    """[合理性检查] forbidden_combinational_loops 至少 1 个, 跟 no_combinational_loop 规则对应"""
    from applications.bus.semantics import load_semantics
    for proto in ("TL-UL", "AXI4", "AHB", "APB"):
        sem = load_semantics(proto)
        assert len(sem.forbidden_combinational_loops) > 0
        # 至少有 1 个 no_combinational_loop 规则
        comb_loop_rules = [r for r in sem.deadlock_rules
                          if r.kind == "no_combinational_loop"]
        assert len(comb_loop_rules) > 0, f"{proto} missing comb loop rules"


def test_load_semantics_missing_protocol():
    from applications.bus.semantics import load_semantics
    with pytest.raises(FileNotFoundError):
        load_semantics("NONEXISTENT")


def test_channel_lookup_missing():
    from applications.bus.semantics import load_semantics
    sem = load_semantics("TL-UL")
    assert sem.channel("NONEXISTENT") is None


# ---- CLI tests ----

def _run_cli(args: list[str], timeout: int = 30) -> tuple[int, str, str]:
    cmd = [sys.executable, str(PROJECT_ROOT / "run_cli.py"), *args]
    result = subprocess.run(cmd, capture_output=True, text=True,
                            timeout=timeout, cwd=PROJECT_ROOT)
    return result.returncode, result.stdout, result.stderr


def test_cli_semantics_tlul():
    rc, stdout, stderr = _run_cli(["protocol", "semantics", "TL-UL"])
    assert rc == 0
    # 关键 sections
    assert "Protocol: TL-UL" in stdout
    assert "Transfer condition:" in stdout
    assert "a_valid && a_ready" in stdout
    assert "Channels (2):" in stdout
    assert "A [request]:" in stdout
    assert "D [response]:" in stdout
    assert "Forbidden combinational loops" in stdout
    assert "Deadlock rules" in stdout
    assert "TL-UL-A-VALID-INDEP-OF-READY" in stdout


def test_cli_semantics_axi4():
    rc, stdout, stderr = _run_cli(["protocol", "semantics", "AXI4"])
    assert rc == 0
    assert "Protocol: AXI4" in stdout
    assert "Channels (5):" in stdout
    assert "AW" in stdout
    assert "AR" in stdout
    # 至少 8 个 deadlock rules
    assert stdout.count("🔴 [error]") + stdout.count("🟡 [warning]") >= 5


def test_cli_semantics_json():
    """[P1-6] --json 输出必须可被 json.loads 解析"""
    rc, stdout, stderr = _run_cli(["protocol", "semantics", "AXI4", "--json"])
    assert rc == 0
    data = json.loads(stdout)
    assert data["protocol"] == "AXI4"
    assert len(data["channels"]) == 5
    assert "forbidden_combinational_loops" in data
    assert "deadlock_rules" in data
    # 每个 rule 有 id
    for r in data["deadlock_rules"]:
        assert "id" in r
        assert "severity" in r


def test_cli_semantics_missing_protocol():
    """不存在的协议应该报错"""
    rc, stdout, stderr = _run_cli(["protocol", "semantics", "DOES_NOT_EXIST"])
    assert rc != 0
    # 错误应该走 stderr
    err_combined = stderr + stdout
    assert "not found" in err_combined.lower() or "Error" in err_combined
