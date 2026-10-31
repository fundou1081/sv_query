"""[iter_330 / PLAN P34.1] verify consistency + claim (verified/contradicted/unknown)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STRUCT = ROOT / "sim" / "tests" / "fixtures" / "json_contract" / "struct.sv"
BITSLICE = ROOT / "sim" / "tests" / "fixtures" / "json_contract" / "bitslice.sv"


def _run(*args):
    return subprocess.run(["sv_query", *args], capture_output=True, text=True,
                          timeout=120, cwd=str(ROOT))


def _json(*args):
    r = _run(*args, "--json")
    assert r.returncode == 0, r.stderr[-400:]
    return json.loads(r.stdout)


def _claim(fixture: Path, **claim):
    return _json("verify", "claim", "--file", str(fixture),
                 "--claim", json.dumps(claim))


def test_consistency_clean_design():
    d = _json("verify", "consistency", "--file", str(STRUCT))
    r = d["result"]
    assert d["ok"] is True
    assert r["verified"] is True
    assert r["total_violations"] == 0
    assert {c["check"] for c in r["checks"]} == {"reciprocity", "bit_mapping", "connection"}
    assert all(c["status"] == "pass" for c in r["checks"])


def test_consistency_bit_mapping_specific_signal():
    d = _json("verify", "consistency", "--file", str(BITSLICE),
              "--checks", "bit", "--signal", "top.y[3]")
    r = d["result"]
    assert r["verified"] is True
    check = r["checks"][0]
    assert check["check"] == "bit_mapping"
    assert check["checked"] >= 1


def test_driver_claim_verified_and_contradicted():
    d = _claim(STRUCT, type="driver", signal="top.u.y", driver="top.u.a")
    assert d["result"]["status"] == "verified"
    d = _claim(STRUCT, type="driver", signal="top.u.y", driver="top.u.y")
    assert d["result"]["status"] == "contradicted"


def test_path_claim_verified_and_missing_edge():
    d = _claim(STRUCT, type="path", **{"from": "top.u.a", "to": "top.u.y"})
    assert d["result"]["status"] == "verified"
    d = _claim(STRUCT, type="path", **{"from": "top.u.a", "to": "top.u.y",
                                        "nodes": ["top.u.a", "top.u.y", "top.u.a"]})
    assert d["result"]["status"] == "contradicted"


def test_connection_claim_verified_and_contradicted():
    d = _claim(STRUCT, type="connection", instance="top.u", port="a",
               internal="top.u.a")
    assert d["result"]["status"] == "verified"
    d = _claim(STRUCT, type="connection", instance="top.u", port="a",
               internal="top.u.y")
    assert d["result"]["status"] == "contradicted"


def test_bit_claim_verified_and_contradicted():
    d = _claim(BITSLICE, type="bit", target="top.y[3]", source="top.a[7]")
    assert d["result"]["status"] == "verified"
    d = _claim(BITSLICE, type="bit", target="top.y[3]", source="top.a[4]")
    assert d["result"]["status"] == "contradicted"


def test_bit_claim_unknown_when_only_parent_bus():
    d = _claim(STRUCT, type="bit", target="top.u.y[3]", source="top.u.a[3]")
    assert d["result"]["status"] == "unknown"


def test_invalid_claim_is_explicit_error():
    r = _run("verify", "claim", "--file", str(STRUCT), "--claim", '{"type":"nope"}', "--json")
    assert r.returncode == 1
    d = json.loads(r.stdout)
    assert d["ok"] is False
    assert "unknown claim type" in d["error"]


def test_path_claim_bidirectional_detects_missing_reverse():
    d = _claim(STRUCT, type="path", **{"from": "top.u.a", "to": "top.u.y",
                                        "nodes": ["top.u.a", "top.u.y"],
                                        "bidirectional": True})
    assert d["result"]["status"] == "contradicted"
    assert any(x.get("direction") == "reverse"
               for x in d["result"]["counterevidence"])
