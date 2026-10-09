"""
test_cli_semantic_queries.py — [iter_237] 语义查询补全: params / ports / paths / classes / class

补齐的 4 类能力 (方豆: "先把上面做好"):
  1. 参数 override 查询 —— `#(.WIDTH(8))` 实际生效值 (并区分 override vs 默认)
  2. 端口总览 —— per-module 端口表 (方向/位宽/入边/出边)
  3. 跨模块路径 —— PathResolver; **本轮同时修了它的跨模块缺陷** (旧实现只"进模块"不"出模块")
  4. class 查询 —— list_classes / trace_class_members / trace_class_instances / trace_member_instances
     (四个库 API 此前零 CLI 暴露)

并锁定 PathResolver 的自洽性不变式: `find_path` 找得到的路径必须出现在 `find_all_paths` 里。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# [iter_239 1b] 快照默认目录已在缓存目录 → 测试隔离 (否则写用户 home / 受限环境失败)
os.environ.setdefault("SVQ_SNAPSHOT_DIR", tempfile.mkdtemp(prefix="svq_snap_"))
os.environ["SVQ_SNAPSHOT_DIR"] = os.environ["SVQ_SNAPSHOT_DIR"]
RUN_CLI = str(PROJECT_ROOT / "run_cli.py")
SRC = str(PROJECT_ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

INST_DEMO = "sim/tests/fixtures/golden_mini/inst_demo.sv"
GEN_LOOP = "sim/tests/fixtures/golden_mini/golden_dataflow_27_generate_loop.sv"
CLASS_FIX = "sim/tests/fixtures/mixed_corpus/param_class_nested.sv"


def _run(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["python3", RUN_CLI, *args], cwd=str(PROJECT_ROOT),
                          capture_output=True, text=True, timeout=300)


def _json(*args) -> dict:
    r = _run(*args)
    assert r.returncode == 0, f"rc={r.returncode}\n{r.stdout[:300]}\n{r.stderr[:300]}"
    return json.loads(r.stdout)


@pytest.fixture(scope="module")
def param_fixture(tmp_path_factory) -> str:
    """带参数化实例的临时 fixture (child #(W, DEPTH), 一个 override 一个用默认)。"""
    d = tmp_path_factory.mktemp("paramq")
    f = d / "p.sv"
    f.write_text('''module child #(parameter W = 8, parameter DEPTH = 2) (
  input  logic [W-1:0] a,
  output logic [W-1:0] y
);
  assign y = a;
endmodule

module top (input logic [3:0] i, output logic [3:0] o);
  child #(.W(4), .DEPTH(3)) u_child (.a(i), .y(o));
  child #(.W(4))            u_child_default (.a(i), .y());
endmodule
''')
    return str(f)


# ---------------------------------------------------------------------------
# 1. params
# ---------------------------------------------------------------------------
class TestParams:
    def test_reports_effective_values(self, param_fixture):
        d = _json("params", "top.u_child", "-f", param_fixture, "--json")
        assert d["ok"] is True and d["module_type"] == "child"
        vals = {p["name"]: p for p in d["parameters"]}
        assert vals["W"]["value"] == "4" and vals["W"]["is_overridden"] is True
        assert vals["DEPTH"]["value"] == "3" and vals["DEPTH"]["is_overridden"] is True

    def test_distinguishes_default_from_overridden(self, param_fixture):
        """默认值场景: W 被 override, DEPTH 用默认 (is_overridden=False)。"""
        d = _json("params", "top.u_child_default", "-f", param_fixture, "--json")
        vals = {p["name"]: p for p in d["parameters"]}
        assert vals["W"]["is_overridden"] is True
        assert vals["DEPTH"]["value"] == "2" and vals["DEPTH"]["is_overridden"] is False

    def test_unknown_instance_fails_loudly(self, param_fixture):
        r = _run("params", "top.nope", "-f", param_fixture, "--json")
        assert r.returncode != 0
        d = json.loads(r.stdout)
        assert d["ok"] is False and "hint" in d


# ---------------------------------------------------------------------------
# 2. ports
# ---------------------------------------------------------------------------
class TestPorts:
    def test_port_table(self):
        d = _json("ports", "generate_loop", "-f", GEN_LOOP, "--json")
        assert d["ok"] is True and d["count"] == 3
        assert d["by_direction"] == {"input": 2, "output": 1}
        by = {p["port"]: p for p in d["ports"]}
        assert by["data"]["direction"] == "input" and by["data"]["width"] == [7, 0]
        assert by["sum_out"]["direction"] == "output"
        # 字段名是精确的图邻接计数 (不冒充语义 driver/load)
        assert {"in_edges", "out_edges"} <= set(by["data"])

    def test_unknown_module_fails_loudly(self):
        r = _run("ports", "no_such_module", "-f", GEN_LOOP, "--json")
        assert r.returncode != 0 and json.loads(r.stdout)["ok"] is False


# ---------------------------------------------------------------------------
# 3. paths (跨模块) + PathResolver 自洽性
# ---------------------------------------------------------------------------
class TestPaths:
    def test_cross_module_path_found(self):
        """跨模块路径可查 (旧实现恒 None → iter_237 修)。

        `find_path` 返回**最短跳数**的那条 (可能经由实例节点); 走模块内部的路线在 `--all` 里。
        因此这里同时验证: ① 单路径可达且端点正确; ② `--all` 里存在穿越模块内部的路线。
        """
        d = _json("paths", "inst_demo.in_a", "inst_demo.add_out", "-f", INST_DEMO, "--json")
        assert d["ok"] is True and d["found"] is True
        path = d["path"]
        assert path[0] == "inst_demo.in_a" and path[-1] == "inst_demo.add_out"
        assert d["hop_count"] == len(path) - 1

        allp = _json("paths", "inst_demo.in_a", "inst_demo.add_out", "--all",
                     "-f", INST_DEMO, "--json")
        assert path in allp["all_paths"], "find_path 结果必须在 all_paths 中"
        assert any("sub_adder.a" in p for p in allp["all_paths"]), \
            "应存在穿越模块内部的跨模块路径 (端口↔内部信号映射跳转)"

    def test_all_paths_and_truncation_flag(self):
        d = _json("paths", "inst_demo.in_a", "inst_demo.add_out", "--all", "-f", INST_DEMO, "--json")
        assert d["ok"] is True and d["count"] >= 1
        assert d["truncated"] is False

    def test_unknown_signal_fails_loudly(self):
        r = _run("paths", "nope.a", "inst_demo.add_out", "-f", INST_DEMO, "--json")
        assert r.returncode != 0
        d = json.loads(r.stdout)
        assert d["ok"] is False and "nope.a" in d["unknown"]

    def test_find_path_is_subset_of_find_all_paths(self):
        """不变式: find_path 的路径必然出现在 find_all_paths 里 (两者共用邻接定义)。"""
        from trace.unified_tracer import UnifiedTracer

        src = (PROJECT_ROOT / INST_DEMO).read_text()
        t = UnifiedTracer(sources={"inst_demo.sv": src})
        t.build_graph()
        pr = t.get_path_resolver()
        assert pr is not None
        for a, b in [("inst_demo.in_a", "inst_demo.add_out"), ("sub_adder.a", "sub_adder.sum")]:
            one = pr.find_path(a, b)
            allp = pr.find_all_paths(a, b)
            assert one is not None
            assert one in allp, f"{a}->{b}: find_path 结果不在 all_paths 中"

    def test_mig_maps_both_directions(self):
        """MIG 双向映射是跨模块跳转的基础 (进模块 + 出模块)。"""
        from trace.unified_tracer import UnifiedTracer

        src = (PROJECT_ROOT / INST_DEMO).read_text()
        t = UnifiedTracer(sources={"inst_demo.sv": src})
        t.build_graph()
        mig = t.get_module_graph()
        assert mig.get_internal_signal("inst_demo.u_adder.a") == "sub_adder.a"
        assert mig.get_port_path("sub_adder.a") == "inst_demo.u_adder.a"


# ---------------------------------------------------------------------------
# 4. classes / class
# ---------------------------------------------------------------------------
class TestClasses:
    def test_list_classes(self):
        d = _json("classes", "-f", CLASS_FIX, "--json")
        assert d["ok"] is True and "packet" in d["classes"] and "inner" in d["classes"]

    def test_class_members_and_instances(self):
        d = _json("class", "inner", "-f", CLASS_FIX, "--json")
        assert d["ok"] is True
        assert any(m["id"] == "inner.val" and m["kind"] == "CLASS_PROPERTY" for m in d["members"])
        assert any(i["kind"] == "CLASS_INSTANCE" for i in d["instances"])

    def test_class_member_instances_query(self):
        """--member 查实例级成员 (只含图内已存在节点)。"""
        d = _json("class", "inner", "--member", "val", "-f", CLASS_FIX, "--json")
        assert d["ok"] is True and d["class"] == "inner" and d["member"] == "val"
        assert "note" in d

    def test_unknown_class_fails_loudly(self):
        r = _run("class", "no_such_class", "-f", CLASS_FIX, "--json")
        assert r.returncode != 0 and json.loads(r.stdout)["ok"] is False


# ---------------------------------------------------------------------------
# 5. 覆盖补强 (审计发现的空白): 多级嵌套 / 空结果 / 上限接线
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def nested_fixture(tmp_path_factory) -> str:
    """三级嵌套 (top → mid → leaf), 用于验证 full_path/parent 的**多层**推导。"""
    d = tmp_path_factory.mktemp("nestedq")
    f = d / "n.sv"
    f.write_text('''module leaf (input logic a, output logic y);
  assign y = a;
endmodule
module mid (input logic a, output logic y);
  leaf u_leaf (.a(a), .y(y));
endmodule
module top (input logic a, output logic y);
  mid u_mid (.a(a), .y(y));
endmodule
''')
    return str(f)


class TestNestedHierarchy:
    def test_multi_level_parent_chain(self, nested_fixture):
        """bug #6 修复的深层验证: parent 由 full_path 去尾段推导, 多层也要对。"""
        d = _json("instances", "-f", nested_fixture, "--json")
        by = {i["full_path"]: i for i in d["instances"]}
        assert "top.u_mid" in by and "top.u_mid.u_leaf" in by, f"应枚举到两级实例: {list(by)}"
        assert by["top.u_mid"]["parent"] == "top"
        assert by["top.u_mid"]["module_type"] == "mid"
        assert by["top.u_mid.u_leaf"]["parent"] == "top.u_mid"
        assert by["top.u_mid.u_leaf"]["module_type"] == "leaf"

    def test_hierarchy_tree_is_nested(self, nested_fixture):
        d = _json("hierarchy", "-f", nested_fixture, "--json")
        roots = d["tree"]
        assert len(roots) == 1 and roots[0]["full_path"] == "top"       # 合成根 = 顶层模块
        assert roots[0].get("synthetic") is True
        mid = roots[0]["children"][0]
        assert mid["full_path"] == "top.u_mid"
        assert mid["children"][0]["full_path"] == "top.u_mid.u_leaf"    # 三级都出来了
        assert d["instance_count"] == 2                                 # 真实实例 2 个


class TestEmptyResultsAreNotFailures:
    def test_instance_without_parameters(self, nested_fixture):
        """无参数模块: count=0 且 ok=true (不是错误 —— 与"找不到实例"区分开)。"""
        d = _json("params", "top.u_mid", "-f", nested_fixture, "--json")
        assert d["ok"] is True and d["count"] == 0 and d["parameters"] == []

    def test_design_without_classes(self):
        """无 class 的设计: classes 返回空列表而不是报错。"""
        d = _json("classes", "-f", INST_DEMO, "--json")
        assert d["ok"] is True and d["count"] == 0 and d["classes"] == []


class TestPathsCliBounds:
    def test_max_flag_wires_truncation(self):
        """CLI --max 必须接到 find_all_paths 的上限并标注 truncated。"""
        full = _json("paths", "inst_demo.in_a", "inst_demo.add_out", "--all", "-f", INST_DEMO, "--json")
        assert full["count"] >= 2 and full["truncated"] is False
        capped = _json("paths", "inst_demo.in_a", "inst_demo.add_out", "--all", "--max", "1",
                       "-f", INST_DEMO, "--json")
        assert capped["count"] == 1 and capped["truncated"] is True

    def test_unknown_dst_reported(self):
        r = _run("paths", "inst_demo.in_a", "nope.out", "-f", INST_DEMO, "--json")
        assert r.returncode != 0
        d = json.loads(r.stdout)
        assert d["ok"] is False and "nope.out" in d["unknown"]

    def test_same_src_dst_single_node_path(self):
        d = _json("paths", "inst_demo.in_a", "inst_demo.in_a", "-f", INST_DEMO, "--json")
        assert d["found"] is True and d["path"] == ["inst_demo.in_a"] and d["hop_count"] == 0
