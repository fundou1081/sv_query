"""[iter_280 / P0.1] 图快照基线回归。

保护对象：`_trace_drivers_recursive` 与 `GraphBuilder` 后处理 pass 的重构
（PLAN.md P0.2 / P0.3）。基线 = `sim/tests/golden/graph_baseline/*.json`。

规则
----
- 基线**不会被自动 bless**：缺失时本测试失败并提示如何生成。
- 有意改变图语义时，用 `python3 tools/graph_snapshot.py capture ...` 重新生成基线，
  并在迭代记录里写明"为什么变"。
- 覆盖: 单文件层次 / filelist 多模块 / wrapper 直通 / generate 三种形式 / 调度器。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))

from graph_snapshot import build_snapshot, diff_snapshots, format_diff  # noqa: E402

BASELINE_DIR = REPO / "sim" / "tests" / "golden" / "graph_baseline"
FIXTURES = REPO / "sim" / "tests" / "fixtures"

# name → build_snapshot kwargs（路径都相对 REPO）
CASES: dict[str, dict] = {
    "inst_demo": {"files": ["sim/tests/fixtures/golden_mini/inst_demo.sv"]},
    "minimal_3module": {"filelist": "sim/tests/fixtures/minimal_3module/filelist.f"},
    "minimal_arbiter": {"filelist": "sim/tests/fixtures/minimal_arbiter/filelist.f"},
    "wrapper_chain": {"filelist": "sim/tests/fixtures/wrapper_chain/filelist.f"},
    "generate_forms": {"filelist": "sim/tests/fixtures/generate_forms/filelist.f"},
    "scheduler_minimal": {"filelist": "sim/tests/fixtures/scheduler_minimal/filelist.f"},
}


def _kwargs(spec: dict) -> dict:
    out = {}
    if "filelist" in spec:
        out["filelist"] = str(REPO / spec["filelist"])
    if "files" in spec:
        out["files"] = [str(REPO / f) for f in spec["files"]]
    if "target" in spec:
        out["target"] = spec["target"]
    return out


def _baseline_path(name: str) -> Path:
    return BASELINE_DIR / f"{name}.json"


def _capture(name: str) -> dict:
    return build_snapshot(name, **_kwargs(CASES[name]))


@pytest.mark.parametrize("name", sorted(CASES))
def test_graph_matches_baseline(name: str):
    path = _baseline_path(name)
    if not path.exists():
        pytest.fail(
            f"缺少图基线 {path.relative_to(REPO)}\n"
            f"生成: python3 tools/graph_snapshot.py capture --name {name} "
            f"--{'filelist' if 'filelist' in CASES[name] else 'file'} "
            f"{CASES[name].get('filelist') or CASES[name]['files'][0]} --out {path}"
        )
    baseline = json.loads(path.read_text(encoding="utf-8"))
    current = _capture(name)
    diff = diff_snapshots(baseline, current)
    assert diff["ok"], f"{name} 图与基线不一致:\n{format_diff(diff)}"


def test_snapshot_is_deterministic():
    """同一输入采两次必须逐字段一致（排序/属性抽取无随机性）。"""
    a = _capture("generate_forms")
    b = _capture("generate_forms")
    assert a == b, "图快照不确定：两次采集结果不同"


def test_diff_detects_node_removal():
    """自校验：删一个节点后 diff 必须报 removed（防止工具本身失效）。"""
    snap = _capture("inst_demo")
    mutated = json.loads(json.dumps(snap))
    dropped = mutated["nodes"].pop()["id"]
    diff = diff_snapshots(snap, mutated)
    assert not diff["ok"]
    assert dropped in diff["nodes"]["removed"]


def test_diff_detects_edge_kind_change():
    """自校验：改一条边的 kind 后 diff 必须报边增删。"""
    snap = _capture("inst_demo")
    mutated = json.loads(json.dumps(snap))
    mutated["edges"][0]["kind"] = "MUTATED"
    diff = diff_snapshots(snap, mutated)
    assert not diff["ok"]
    assert diff["edges"]["added"] and diff["edges"]["removed"]


def test_baseline_files_are_normalized():
    """基线里不能出现绝对路径 / 时间戳（保证可提交、可复现）。"""
    for path in sorted(BASELINE_DIR.glob("*.json")):
        text = path.read_text(encoding="utf-8")
        assert "/Users/" not in text, f"{path.name} 含绝对路径"
        assert "/home/" not in text, f"{path.name} 含绝对路径"
