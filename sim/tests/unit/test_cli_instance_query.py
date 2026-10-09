"""
test_cli_instance_query.py — [iter_236 1a] 实例/层级查询 + graph 组 filelist 支持

背景 (方豆指出的能力缺口): 库侧 `get_instances()` / MIG 早已就绪, 但 CLI **零暴露** ——
agent 只能看图, 没法问"这设计里有哪些实例、它们怎么连"。本文件锁定新增的 4 个命令
(`instances` / `instance` / `connections` / `hierarchy`) 的 JSON 契约, 以及
`graph` 组补上的 `--filelist` 支持 (真实多文件项目)。

同时锁定本轮修掉的 **pre-existing bug #6**: `UnifiedTracer.get_instances()` 双重包装
adapter + 按原始 InstanceSymbol 形状解析 (与生产返回的 SemanticInstanceWrapper 不符)
→ 该 API 此前调用必炸/必空。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUN_CLI = str(PROJECT_ROOT / "run_cli.py")
SRC = str(PROJECT_ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

INST_DEMO = "sim/tests/fixtures/golden_mini/inst_demo.sv"            # sub_adder / sub_mult 两实例
SCHED_FL = "sim/tests/fixtures/scheduler_minimal/filelist.f"          # 真实多文件 filelist


def _run(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["python3", RUN_CLI, *args], cwd=str(PROJECT_ROOT),
                          capture_output=True, text=True, timeout=300)


def _json(*args) -> dict:
    r = _run(*args)
    assert r.returncode == 0, f"rc={r.returncode}\n{r.stdout[:300]}\n{r.stderr[:300]}"
    return json.loads(r.stdout)


# ---------------------------------------------------------------------------
# 1. instances
# ---------------------------------------------------------------------------
class TestInstances:
    def test_lists_instances_with_paths(self):
        d = _json("instances", "-f", INST_DEMO, "--json")
        assert d["ok"] is True and d["count"] == 2
        paths = {i["full_path"] for i in d["instances"]}
        assert paths == {"inst_demo.u_adder", "inst_demo.u_mult"}
        first = next(i for i in d["instances"] if i["full_path"] == "inst_demo.u_adder")
        assert first["name"] == "u_adder"
        assert first["module_type"] == "sub_adder"      # 模块类型 (非实例名)
        assert first["parent"] == "inst_demo"           # 父实例路径

    def test_module_filter(self):
        d = _json("instances", "-f", INST_DEMO, "--module", "inst_demo", "--json")
        assert d["count"] == 2
        d2 = _json("instances", "-f", INST_DEMO, "--module", "no_such", "--json")
        assert d2["count"] == 0

    def test_human_readable_mode(self):
        r = _run("instances", "-f", INST_DEMO)
        assert r.returncode == 0 and "count" in r.stdout


# ---------------------------------------------------------------------------
# 2. hierarchy / instance
# ---------------------------------------------------------------------------
class TestHierarchyAndInstance:
    def test_hierarchy_tree(self):
        d = _json("hierarchy", "-f", INST_DEMO, "--json")
        assert d["ok"] is True and d["instance_count"] == 2
        assert len(d["tree"]) == 2
        node = next(n for n in d["tree"] if n["full_path"] == "inst_demo.u_adder")
        assert node["module_type"] == "sub_adder" and node["children"] == []

    def test_instance_detail_has_ports(self):
        d = _json("instance", "inst_demo.u_adder", "-f", INST_DEMO, "--json")
        assert d["ok"] is True and d["full_path"] == "inst_demo.u_adder"
        assert d["has_mig_data"] is True
        ports = {p["port"]: p for p in d["ports"]}
        assert ports["a"]["direction"] == "input"
        assert ports["a"]["width"] == [7, 0]            # 位宽结构化 (list, 不是字符串)
        assert ports["sum"]["direction"] == "output"
        assert ports["a"]["internal_signal"]             # 端口↔内部信号映射存在

    def test_instance_not_found_is_structured_error(self):
        r = _run("instance", "inst_demo.nope", "-f", INST_DEMO, "--json")
        assert r.returncode != 0
        d = json.loads(r.stdout)
        assert d["ok"] is False and "hint" in d


# ---------------------------------------------------------------------------
# 3. connections (双语义 + resolved_as 明确)
# ---------------------------------------------------------------------------
class TestConnections:
    def test_connections_for_instance_returns_port_mapping(self):
        d = _json("connections", "inst_demo.u_adder", "-f", INST_DEMO, "--json")
        assert d["resolved_as"] == "instance"
        assert d["module_type"] == "sub_adder"
        assert d["port_count"] == 3
        assert all({"port", "direction", "width", "internal_signal"} <= set(p)
                   for p in d["ports"])

    def test_connections_for_module_returns_edge_classes(self):
        d = _json("connections", "sub_adder", "-f", INST_DEMO, "--json")
        assert d["resolved_as"] == "module"
        assert {"inputs", "outputs", "internals", "cross_module", "confidence", "caveats"} <= set(d)

    def test_connections_unknown_target_fails_loudly(self):
        r = _run("connections", "no_such_thing", "-f", INST_DEMO, "--json")
        assert r.returncode != 0
        assert json.loads(r.stdout)["ok"] is False


# ---------------------------------------------------------------------------
# 4. graph 组: --filelist 支持 (本轮补; 之前只能单文件 → 真实项目不可用)
# ---------------------------------------------------------------------------
class TestGraphFilelist:
    def test_graph_nodes_with_filelist(self):
        d = _json("graph", "nodes", "--filelist", SCHED_FL, "--json")
        assert d["ok"] is True
        assert len(d["result"]["nodes"]) > 50, "多文件项目应能枚举到节点"
        assert d["params"]["filelist"] == SCHED_FL
        assert d["params"]["file"] is None            # 不再输出字符串 "None"

    def test_graph_edges_and_find_with_filelist(self):
        d = _json("graph", "edges", "--filelist", SCHED_FL, "--json")
        assert d["ok"] is True and len(d["result"]["edges"]) > 0
        d2 = _json("graph", "find", "clk", "--filelist", SCHED_FL, "--json")
        assert d2["ok"] is True

    def test_graph_single_file_still_works(self):
        d = _json("graph", "nodes", "-f", INST_DEMO, "--json")
        assert d["ok"] is True and d["params"]["file"] is not None

    def test_graph_requires_a_source(self):
        r = _run("graph", "nodes", "--json")
        assert r.returncode != 0, "既没 --file 也没 --filelist 应报错 (不是静默空图)"


# ---------------------------------------------------------------------------
# 5. 修掉的 pre-existing bug #6: get_instances() 的契约
# ---------------------------------------------------------------------------
class TestGetInstancesApiFixed:
    def test_get_instances_returns_wrapper_shape(self):
        """`UnifiedTracer.get_instances()` 必须能在生产 wrapper 形状上工作。

        历史 bug: ① `SemanticAdapter(adapter)` 双重包装 → `.topInstances` AttributeError;
        ② 解析函数按原始 InstanceSymbol 形状写 (`hasattr(node,'kind')`) → 永远解析不出东西。
        """
        from trace.unified_tracer import UnifiedTracer

        src = (PROJECT_ROOT / INST_DEMO).read_text()
        t = UnifiedTracer(sources={"inst_demo.sv": src})
        t.build_graph()
        insts = t.get_instances()
        assert [i.full_path for i in insts] == ["inst_demo.u_adder", "inst_demo.u_mult"]
        assert all(i.parent == "inst_demo" for i in insts)
        assert {i.module_type for i in insts} == {"sub_adder", "sub_mult"}
