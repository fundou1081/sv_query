"""[iter_344 / PLAN P44.3] scope 聚合 + canonical ID。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STRUCT = ROOT / "sim" / "tests" / "fixtures" / "json_contract" / "struct.sv"


def _run(*args):
    return subprocess.run(["sv_query", *args], capture_output=True, text=True,
                          timeout=60, cwd=str(ROOT))


def _json(*args):
    r = _run(*args, "--json")
    assert r.returncode == 0, r.stderr[-300:]
    return json.loads(r.stdout)


def test_scope_details_and_canonical_ids():
    d = _json("scope", "top.u", "-f", str(STRUCT))
    r = d["result"]
    assert r["scope"] == "top.u"
    assert r["canonical_id"] == "top.u"
    assert r["module_type"] == "child"
    assert r["parent"] == "top"
    assert {p["name"] for p in r["ports"]} == {"a", "y"}
    assert all(p["canonical_id"].startswith("top.u.") for p in r["ports"])
    assert r["parameters"][0]["name"] == "W"
    assert r["parameters"][0]["value"] == "4"
    assert r["parameters"][0]["is_overridden"] is True


def test_scope_children():
    d = _json("scope", "top", "-f", str(STRUCT))
    children = d["result"]["children"]
    assert [c["full_path"] for c in children] == ["top.u"]
    assert children[0]["canonical_id"] == "top.u"


def test_scope_unknown_is_explicit():
    r = _run("scope", "top.nope", "-f", str(STRUCT), "--json")
    assert r.returncode == 1
    d = json.loads(r.stdout)
    assert d["ok"] is False
    assert d["error"] == "scope not found"


def test_capabilities_mode_groups():
    d = _json("capabilities")
    modes = {c["name"]: c["mode"] for c in d["commands"]}
    assert modes["scope"] == "scope"
    assert modes["instances"] == "scope"
    assert modes["drivers"] == "trace"
    assert modes["verify claim"] == "verify"
    assert modes["stats"] == "locate"


IFACE = ROOT / "sim" / "tests" / "fixtures" / "json_contract" / "iface.sv"
GEN = ROOT / "sim" / "tests" / "fixtures" / "json_contract" / "generate_paths.sv"
CLS = ROOT / "sim" / "tests" / "fixtures" / "golden_mini" / "golden_dataflow_35_class_oop.sv"


def test_interface_scope_signals():
    r = _json("scope", "top.u_if", "-f", str(IFACE))["result"]
    assert r["module_type"] == "bus_if"
    names = {s["name"] for s in r["signals"]}
    assert {"clk", "data", "valid"} <= names
    assert all(s["canonical_id"] for s in r["signals"])


def test_generate_scope_signals():
    r = _json("scope", "top.genblk1[0]", "-f", str(GEN))["result"]
    assert r["kind"] == "generate"
    assert [s["name"] for s in r["signals"]] == ["x"]
    assert r["signals"][0]["canonical_id"] == "top.genblk1[0].x"


def test_class_scope_members_instances():
    r = _json("scope", "packet", "-f", str(CLS))["result"]
    assert r["kind"] == "class"
    assert {m["name"] for m in r["members"]} >= {"addr", "data"}
    assert len(r["instances"]) == 1
