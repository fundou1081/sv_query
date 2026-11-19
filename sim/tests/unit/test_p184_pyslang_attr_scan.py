"""P184.1 — pyslang 属性扫描器的类型分类与棘轮。

覆盖:
- 当前树 ratchet 通过, 且分类可信 (pyslang 只含真实 getter, unknown = 0);
- 注入新 pyslang 读取 / 新 unknown 读取 → ratchet 红;
- wrapper 读取不触发棘轮;
- 分类来自类型证据而非 receiver 名字;
- baseline 缺失 / 源码不可解析 → 显式失败 (不静默跳过);
- reviewed_wrappers 人工归类未知项。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))

import scan_pyslang_attrs as scan  # noqa: E402

BASELINE = REPO / "tools" / "pyslang_attr_baseline.json"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _tree(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "src"
    root.mkdir(parents=True)
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def _baseline_file(tmp_path: Path, known: list[dict] | None = None,
                   wrappers: list[dict] | None = None) -> Path:
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps({
        "schema": scan.BASELINE_SCHEMA,
        "known_pyslang": known or [],
        "reviewed_wrappers": wrappers or [],
    }), encoding="utf-8")
    return path


def _entry(file: str, receiver: str, attr: str, count: int = 1, **extra) -> dict:
    return {"file": file, "receiver": receiver, "attr": attr, "count": count, **extra}


def _hits(result: scan.ScanResult) -> list[scan.Hit]:
    return [h for h in result.unprotected]


# ---------------------------------------------------------------------------
# 当前树
# ---------------------------------------------------------------------------


def test_current_tree_ratchet_passes():
    baseline = scan.load_baseline(BASELINE)
    result = scan.scan_tree(REPO / "src", baseline=baseline)

    assert scan.evaluate_ratchet(result, baseline) == []
    counts = result.counts()
    # iter_182 heuristic hit set is the candidate scope; all of it is explained.
    assert len(result.unprotected) == 50
    assert counts["unknown"] == 0
    assert counts["pyslang"] == sum(
        int(e["count"]) for e in baseline.known_pyslang.values()
    )
    assert result.skipped == []


def test_current_tree_real_pyslang_hits_are_the_reviewed_ones():
    baseline = scan.load_baseline(BASELINE)
    result = scan.scan_tree(REPO / "src", baseline=baseline)

    actual: dict[str, int] = {}
    for hit in result.unprotected:
        if hit.classification in ("pyslang", "unknown"):
            actual[hit.key] = actual.get(hit.key, 0) + 1
    expected = {key: int(e["count"]) for key, e in baseline.known_pyslang.items()}
    assert actual == expected
    # pyslang 读取必须是少数, 不能被 50 处噪声淹没
    assert len(actual) < len(result.unprotected) / 2


def test_baseline_is_not_the_heuristic_hit_list():
    data = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert data["schema"] == scan.BASELINE_SCHEMA
    known_hits = sum(int(e["count"]) for e in data["known_pyslang"])
    assert known_hits < 50
    assert len(data["reviewed_wrappers"]) >= 1
    for entry in data["known_pyslang"]:
        assert entry.get("reason"), f"pyslang baseline 条目缺人工判据: {entry}"
        assert entry["attr"] in scan.RISKY


# ---------------------------------------------------------------------------
# 分类证据 (不是名字启发式)
# ---------------------------------------------------------------------------


def test_pyslang_annotation_wins_over_non_matching_name(tmp_path):
    root = _tree(tmp_path, {"a.py": (
        "import pyslang\n"
        "def f(s: pyslang.Symbol):\n"
        "    return s.name\n"
    )})
    result = scan.scan_tree(root)

    hits = [h for h in result.hits if h.attr == "name"]
    assert len(hits) == 1
    assert hits[0].classification == "pyslang"
    assert "annotation" in hits[0].evidence
    # 名字 `s` 不在 iter_182 候选表里, 但静态 pyslang 读取仍纳入候选
    assert hits[0].candidate is True


def test_repo_dataclass_receiver_is_wrapper_even_if_name_looks_pyslang(tmp_path):
    root = _tree(tmp_path, {"a.py": (
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class Node:\n"
        "    name: str\n"
        "    def label(self):\n"
        "        return self.name\n"
        "def use(instance: Node):\n"
        "    return instance.name\n"
    )})
    result = scan.scan_tree(root)

    hits = [h for h in result.hits if h.attr == "name"]
    assert hits, "expected hits"
    assert {h.classification for h in hits} == {"wrapper"}


def test_repo_constructor_and_method_return_propagate(tmp_path):
    root = _tree(tmp_path, {
        "model.py": (
            "from dataclasses import dataclass\n"
            "@dataclass\n"
            "class Blob:\n"
            "    name: str\n"
        ),
        "use.py": (
            "from .model import Blob\n"
            "class Factory:\n"
            "    def make(self) -> Blob:\n"
            "        return Blob('x')\n"
            "def run(factory):\n"
            "    item = factory.make()\n"
            "    return item.name\n"
        ),
    })
    result = scan.scan_tree(root)

    hits = [h for h in result.hits if h.attr == "name"]
    assert len(hits) == 1
    assert hits[0].classification == "wrapper"
    assert "make" in hits[0].evidence


def test_unknown_without_evidence_is_reported_as_unknown(tmp_path):
    root = _tree(tmp_path, {"a.py": (
        "def f(node):\n"
        "    return node.name\n"
    )})
    result = scan.scan_tree(root)

    hits = [h for h in result.hits if h.attr == "name"]
    assert [h.classification for h in hits] == ["unknown"]


# ---------------------------------------------------------------------------
# 棘轮
# ---------------------------------------------------------------------------


def test_new_pyslang_hit_fails_ratchet(tmp_path):
    root = _tree(tmp_path, {"a.py": (
        "import pyslang\n"
        "def f(sym: pyslang.Symbol):\n"
        "    return sym.name\n"
    )})
    baseline = scan.load_baseline(_baseline_file(tmp_path))
    result = scan.scan_tree(root, baseline=baseline)

    violations = scan.evaluate_ratchet(result, baseline)
    assert any("新增 pyslang 命中" in v for v in violations), violations


def test_new_unknown_candidate_fails_ratchet(tmp_path):
    root = _tree(tmp_path, {"a.py": (
        "def f(node):\n"
        "    return node.name\n"
    )})
    baseline = scan.load_baseline(_baseline_file(tmp_path))
    result = scan.scan_tree(root, baseline=baseline)

    violations = scan.evaluate_ratchet(result, baseline)
    assert any("unknown 命中未 review" in v for v in violations), violations


def test_wrapper_hit_does_not_fail_ratchet(tmp_path):
    root = _tree(tmp_path, {"a.py": (
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class Node:\n"
        "    name: str\n"
        "def f(node: Node):\n"
        "    return node.name\n"
    )})
    baseline = scan.load_baseline(_baseline_file(tmp_path))
    result = scan.scan_tree(root, baseline=baseline)

    assert result.counts()["wrapper"] == 1
    assert scan.evaluate_ratchet(result, baseline) == []


def test_ratchet_allows_known_hit_and_detects_count_growth(tmp_path):
    source = (
        "import pyslang\n"
        "def f(sym: pyslang.Symbol):\n"
        "    return sym.name\n"
    )
    root = _tree(tmp_path, {"a.py": source})
    baseline = scan.load_baseline(_baseline_file(
        tmp_path, known=[_entry("a.py", "sym", "name", 1, reason="test")],
    ))
    result = scan.scan_tree(root, baseline=baseline)
    assert scan.evaluate_ratchet(result, baseline) == []

    # 同一文件新增一处相同读取 → 计数增长即失败
    root2 = _tree(tmp_path / "second", {"a.py": source + (
        "def g(sym: pyslang.Symbol):\n"
        "    return sym.name\n"
    )})
    result2 = scan.scan_tree(root2, baseline=baseline)
    violations = scan.evaluate_ratchet(result2, baseline)
    assert any("baseline 1 → 现在 2" in v for v in violations), violations


def test_ratchet_allows_reduction(tmp_path):
    root = _tree(tmp_path, {"a.py": (
        "import pyslang\n"
        "def f(sym: pyslang.Symbol):\n"
        "    return sym.type\n"
    )})
    baseline = scan.load_baseline(_baseline_file(
        tmp_path, known=[
            _entry("a.py", "sym", "name", 1, reason="old"),
            _entry("a.py", "sym", "type", 1, reason="kept"),
        ],
    ))
    result = scan.scan_tree(root, baseline=baseline)
    assert scan.evaluate_ratchet(result, baseline) == []


def test_reviewed_wrapper_override_resolves_unknown(tmp_path):
    root = _tree(tmp_path, {"a.py": (
        "def f(node):\n"
        "    return node.name\n"
    )})
    baseline = scan.load_baseline(_baseline_file(
        tmp_path, wrappers=[_entry("a.py", "node", "name", 1, reason="reviewed")],
    ))
    result = scan.scan_tree(root, baseline=baseline)

    hit = next(h for h in result.unprotected if h.attr == "name")
    assert hit.classification == "wrapper"
    assert "reviewed wrapper" in hit.evidence
    assert scan.evaluate_ratchet(result, baseline) == []


def test_parse_error_is_not_silently_skipped(tmp_path):
    root = _tree(tmp_path, {"broken.py": "def f(:\n    pass\n"})
    baseline = scan.load_baseline(_baseline_file(tmp_path))
    result = scan.scan_tree(root, baseline=baseline)

    assert [f for f, _ in result.skipped] == ["broken.py"]
    violations = scan.evaluate_ratchet(result, baseline)
    assert any("无法解析" in v for v in violations), violations


# ---------------------------------------------------------------------------
# CLI 契约
# ---------------------------------------------------------------------------


def test_cli_json_schema_and_evidence(tmp_path, capsys):
    root = _tree(tmp_path, {"a.py": (
        "import pyslang\n"
        "def f(sym: pyslang.Symbol):\n"
        "    return sym.name\n"
    )})
    rc = scan.main(["--json", "--root", str(root)])
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == scan.SCAN_SCHEMA
    assert payload["by_classification"]["pyslang"] == 1
    hit = payload["hits"][0]
    for field in ("file", "line", "receiver", "attr", "classification", "evidence"):
        assert field in hit
    assert hit["receiver"] == "sym"
    assert hit["attr"] == "name"
    assert payload["baseline"]["checked"] is False


def test_cli_missing_baseline_fails_explicitly(tmp_path, capsys):
    root = _tree(tmp_path, {"a.py": "x = 1\n"})
    rc = scan.main(["--ratchet", str(tmp_path / "missing.json"), "--root", str(root)])
    assert rc == 1
    assert "baseline" in capsys.readouterr().err


def test_cli_ratchet_reports_failure(tmp_path, capsys):
    root = _tree(tmp_path, {"a.py": (
        "import pyslang\n"
        "def f(sym: pyslang.Symbol):\n"
        "    return sym.name\n"
    )})
    baseline = _baseline_file(tmp_path)
    rc = scan.main(["--ratchet", str(baseline), "--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "[ratchet] FAIL" in out


def test_write_baseline_refuses_unknowns(tmp_path):
    root = _tree(tmp_path, {"a.py": (
        "def f(node):\n"
        "    return node.name\n"
    )})
    target = tmp_path / "baseline.json"
    rc = scan.main(["--write-baseline", str(target), "--root", str(root)])
    assert rc == 1
    assert not target.exists()
