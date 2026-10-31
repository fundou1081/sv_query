"""[iter_323 / PLAN P27] capabilities.json_contract 与真实 JSON 一致。

契约是 agent 的字段真相源：字段类型/含义必须与 fanin/fanout 实际输出一致；
新增字段必须登记，否则测试失败（防止静默漂移）。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

FIXTURE = """
module top(input sel, input [7:0] a,b, output reg [7:0] y, output [7:0] z);
  always_comb if (sel) y = a; else y = b;
  assign z = y;
endmodule
"""


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["sv_query", *args], capture_output=True, text=True,
                          timeout=60, cwd=str(PROJECT_ROOT))


def _contract() -> dict:
    d = json.loads(_run(["capabilities", "--json"]).stdout)
    return d, d["json_contract"]


def test_top_level_contract_shape():
    data, c = _contract()
    assert c["schema_version"] == data["schema_version"] == "1"
    assert set(c["top_level"]) >= {"ok", "command", "params", "result", "errors"}
    assert c["precision_values"] == ["bit", "bus", "unknown"]
    assert "policy" in c and "notes" in c


def test_contract_fields_have_type_and_desc():
    _, c = _contract()
    skip = {"commands", "bit_normalization", "paths_modes"}
    for section, fields in c.items():
        if section in skip or section in ("schema_version", "policy", "scope",
                                          "precision_values", "notes"):
            continue
        if not isinstance(fields, dict):
            continue
        for name, spec in fields.items():
            if not isinstance(spec, dict):
                continue
            assert "type" in spec, f"{section}.{name} missing type"
            assert "desc" in spec, f"{section}.{name} missing desc"
    item = c["trace_node"]["condition_paths"]["item"]
    assert item == {"condition": "string", "path": "array<string>"}
    assert "null" in c["trace_signal"]["cycles_detected"]["type"]


def test_fanin_output_matches_contract(tmp_path):
    p = tmp_path / "t.sv"
    p.write_text(FIXTURE)
    data = json.loads(_run(["trace", "fanin", "top.y", "--file", str(p),
                            "--json", "--no-cache"]).stdout)
    _, c = _contract()
    cmd = c["commands"]["trace fanin"]
    allowed_signal = set(c["trace_signal"]) | set(cmd["signal_fields"]) | {cmd["node_array"]}
    assert set(data) == set(c["top_level"])
    sig = data["result"]["signals"][0]
    assert set(sig) == allowed_signal
    assert set(sig[cmd["node_array"]][0]) == set(c["trace_node"])


def test_fanout_output_matches_contract(tmp_path):
    p = tmp_path / "t.sv"
    p.write_text(FIXTURE)
    data = json.loads(_run(["trace", "fanout", "top.a", "--file", str(p),
                            "--json", "--no-cache"]).stdout)
    _, c = _contract()
    cmd = c["commands"]["trace fanout"]
    allowed_signal = set(c["trace_signal"]) | set(cmd["signal_fields"]) | {cmd["node_array"]}
    sig = data["result"]["signals"][0]
    assert set(sig) == allowed_signal
    assert set(sig[cmd["node_array"]][0]) == set(c["trace_node"])


PATH_SRC = """
module top(input [7:0] a, output [7:0] y);
  assign y[7:4] = a[7:4];
endmodule
"""

IMPACT_SRC = """
module top(input [7:0] a, output [7:0] y);
  assign y = a;
endmodule
"""


def test_paths_contract_matches(tmp_path):
    p = tmp_path / "t.sv"
    p.write_text(PATH_SRC)
    _, c = _contract()
    cmd = c["commands"]["paths"]
    base = set(cmd["base_fields"])
    one = json.loads(_run(["paths", "top.a", "top.y", "--bits", "7:4,7:4",
                           "--directed", "--file", str(p), "--json"]).stdout)
    assert set(one) == base | set(cmd["modes"]["one"])
    assert set(one["bits"]) == set(c["bit_normalization"])
    assert set(one["bits"]["src"]) == set(c["bit_endpoint"])
    allp = json.loads(_run(["paths", "top.a", "top.y", "--bits", "7:4,7:4",
                            "--all", "--directed", "--file", str(p), "--json"]).stdout)
    assert set(allp) == base | set(cmd["modes"]["all"])


def test_dataflow_contract_matches(tmp_path):
    p = tmp_path / "t.sv"
    p.write_text(PATH_SRC)
    _, c = _contract()
    data = json.loads(_run(["dataflow", "analyze", "top.a", "top.y",
                            "--bits", "7:4,7:4", "--file", str(p), "--json"]).stdout)
    cmd = c["commands"]["dataflow analyze"]
    r = data["result"]
    assert set(r) == set(cmd["result_fields"])
    path = r["paths"][0]
    assert set(path) == set(c["dataflow_path"])
    seg = path["segments"][0]
    required = set(c["dataflow_segment"]) - {"evidence"}
    assert required <= set(seg) <= set(c["dataflow_segment"])


def test_impact_contract_matches(tmp_path):
    p = tmp_path / "t.sv"
    p.write_text(IMPACT_SRC)
    _, c = _contract()
    data = json.loads(_run(["trace", "impact", "top.a", "--file", str(p),
                            "--json", "--no-cache"]).stdout)
    cmd = c["commands"]["trace impact"]
    r = data["result"]
    assert set(r) == set(cmd["result_fields"])
    sig = r["signals"][0]
    assert set(sig) == set(c["impact_signal"])
    assert set(sig["paths"][0]) == set(c["impact_path"])


def test_graph_nodes_contract_matches(tmp_path):
    p = tmp_path / "t.sv"
    p.write_text(IMPACT_SRC)
    _, c = _contract()
    cmd = c["commands"]["graph nodes"]
    plain = json.loads(_run(["graph", "nodes", "--match", "top.y", "--file", str(p),
                             "--json"]).stdout)["result"]
    assert set(plain) == set(cmd["result_fields"])
    assert set(plain["nodes"][0]) == set(c["graph_node"])
    detail = json.loads(_run(["graph", "nodes", "--match", "top.y", "--detail",
                              "--file", str(p), "--json"]).stdout)["result"]
    expected = set(c["graph_node"]) | set(c["graph_node_detail"])
    assert set(detail["nodes"][0]) == expected


def test_error_entry_schema():
    _, c = _contract()
    assert set(c["error_entry"]) == {"signal", "index", "error", "error_code"}
    assert "error_entry" in c["top_level"]["errors"]["type"]


FIFO = str(PROJECT_ROOT / "sim" / "tests" / "integration" / "dataflow_fixtures" / "sync_fifo.sv")


def test_graph_edges_contract():
    _, c = _contract()
    data = json.loads(_run(["graph", "edges", "-f", FIFO, "--json"]).stdout)
    cmd = c["commands"]["graph edges"]
    assert set(data) == set(c["top_level"])
    assert set(data["result"]) == set(cmd["result_fields"])
    assert set(data["result"]["edges"][0]) == set(c["graph_edge"])


def test_search_contract():
    _, c = _contract()
    data = json.loads(_run(["search", "rd_en", "-f", FIFO, "--json"]).stdout)
    assert set(data) == set(c["search_result"])
    assert set(data["files"][0]) == set(c["search_file"])
    assert set(data["files"][0]["lines"][0]) == set(c["search_line"])


def test_stats_contract():
    _, c = _contract()
    data = json.loads(_run(["stats", "-f", FIFO, "--json"]).stdout)
    assert set(data) == set(c["top_level"])
    assert set(data["result"]) == set(c["commands"]["stats"]["result_fields"])


def test_evidence_contract():
    _, c = _contract()
    data = json.loads(_run(["trace", "evidence", "sync_fifo.reg_stage1",
                            "-f", FIFO, "--json"]).stdout)
    cmd = c["commands"]["trace evidence"]
    assert set(data) == set(c["top_level"]) | set(cmd["optional_top_level"])
    assert set(data["result"]) == set(cmd["result_fields"])
    sig = data["result"]["signals"][0]
    assert set(sig) == set(c["evidence_signal"])
    assert set(sig["evidence"]) == set(c["evidence_payload"])
    assert set(data["evidence"]) == set(c["evidence_payload"])


def test_controlflow_analyze_contract():
    _, c = _contract()
    data = json.loads(_run(["controlflow", "analyze", "sync_fifo.reg_stage1",
                            "-f", FIFO, "--json"]).stdout)
    cmd = c["commands"]["controlflow analyze"]
    r = data["result"]
    assert set(r) == set(cmd["result_fields"])
    drv = r["conditioned_drivers"][0]
    assert set(drv) == set(c["controlflow_driver"])
    cond = drv["conditions"][0]
    assert set(cond) == set(c["controlflow_condition"])
    assert set(cond["edge"]) == set(c["controlflow_edge"])


def test_controlflow_list_contract():
    _, c = _contract()
    data = json.loads(_run(["controlflow", "list-conditioned",
                            "-f", FIFO, "--json"]).stdout)
    cmd = c["commands"]["controlflow list-conditioned"]
    assert set(data) == set(c["top_level"]) | set(cmd["optional_top_level"])
    assert set(data["result"]) == set(cmd["result_fields"])
