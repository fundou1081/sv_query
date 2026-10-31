"""[iter_334 / PLAN P38.1] class relations: 继承/成员/实例/约束/方法调用。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "sim" / "tests" / "fixtures" / "json_contract" / "class_rel.sv"
OOP = ROOT / "sim" / "tests" / "fixtures" / "golden_mini" / "golden_dataflow_35_class_oop.sv"


def _run(*args):
    return subprocess.run(["sv_query", *args], capture_output=True, text=True,
                          timeout=60, cwd=str(ROOT))


def _json(*args):
    r = _run(*args, "--json")
    assert r.returncode == 0, r.stderr[-300:]
    return json.loads(r.stdout)


def test_inheritance_relations():
    rel = _json("class", "child", "--relations", "-f", str(FIXTURE))["relations"]
    assert rel["extends"] == "base"
    assert rel["ancestors"] == ["base"]
    assert {m["name"] for m in rel["members"]} >= {"x", "y"}
    base = _json("class", "base", "--relations", "-f", str(FIXTURE))["relations"]
    assert base["subclasses"] == ["child"]


def test_method_call_chain():
    rel = _json("class", "child", "--relations", "-f", str(FIXTURE))["relations"]
    methods = {m["name"]: m for m in rel["methods"]}
    assert "bar" in methods
    calls = methods["bar"]["calls"]
    assert calls[0]["method"] == "foo"
    assert calls[0]["target_class"] == "base"


def test_oop_relations_methods_and_instances():
    rel = _json("class", "packet", "--relations", "-f", str(OOP))["relations"]
    assert {m["name"] for m in rel["methods"]} >= {"set_addr"}
    assert len(rel["instances"]) == 1
    assert rel["instances"][0]["id"] == "top.pkt"


def test_unknown_class_is_explicit():
    r = _run("class", "nope", "--relations", "-f", str(FIXTURE), "--json")
    assert r.returncode == 1
    d = json.loads(r.stdout)
    assert d["ok"] is False
    assert "class not found" in d["error"]
